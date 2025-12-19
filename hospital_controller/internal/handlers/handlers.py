import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from hospital_controller.internal.admin_provider.admin_provider import AdminProvider
from hospital_controller.internal.domain import requests as domain
from hospital_controller.internal.regulator_repo.repo import HospitalRepo


class Handler:
    """Бизнес-логика hospital_controller.

    Внимание: здесь мы НЕ трогаем взаимодействие с пациентом.
    Мы обрабатываем только:
    - соединение с регулятором
    - present-proof-2.0 запросы регулятора на подтверждение владения/статуса
    - получение VC-разрешений от регулятора (issue-credential-2.0)
    - дальнейшую регистрацию схем/cred-def только при наличии разрешения
    """

    def __init__(self, admin_provider: AdminProvider, repo: Optional[HospitalRepo], regulator_did: str, regulator_alias: str = "REGULATOR"):
        self.admin_provider = admin_provider
        self.repo = repo
        self.regulator_did = regulator_did
        self.regulator_alias = regulator_alias

        # active_connections: {their_did_or_alias: connection_id}
        self.active_connections: Dict[str, str] = {}

        # pending permission requests: {request_id: {vc_type, created_at, status}}
        self.pending_permissions: Dict[str, Dict[str, Any]] = {}

    # -------------------- Webhooks --------------------
    def handle_connection_webhook(self, message: dict) -> bool:
        try:
            req = domain.ConnectionWebhookRequest.model_validate(message)
        except Exception:
            # без строгой типизации
            req = None

        state = message.get("state")
        connection_id = message.get("connection_id")
        their_label = message.get("their_label")
        their_did = message.get("their_did")

        logging.info(f"[Hospital Connection] state={state} their_label={their_label} their_did={their_did} conn={connection_id}")

        if state == "request":
            return self.admin_provider.accept_connection(connection_id)

        if state in ("active", "response", "completed"):
            # Запоминаем соединение с регулятором по DID, если он известен, иначе по label
            if their_did:
                self.active_connections[their_did] = connection_id
            if their_label:
                self.active_connections[their_label] = connection_id

            # Удобный алиас для регулятора
            if their_label == self.regulator_alias or their_did == self.regulator_did:
                self.active_connections["REGULATOR"] = connection_id

            return True

        if state in ("abandoned", "error"):
            # чистим
            for k in [their_did, their_label, "REGULATOR"]:
                if k and k in self.active_connections and self.active_connections[k] == connection_id:
                    self.active_connections.pop(k, None)
            return True

        return True

    def handle_basic_message_webhook(self, message: dict) -> bool:
        """Поддерживаем структурированные сообщения через basicmessages.

        От регулятора ожидаем:
        - DID_REGISTRATION_APPROVED / DID_REGISTRATION_REJECTED
        - CREDENTIAL_TYPE_PERMISSION_REJECTED (если отказ по типу)
        """
        try:
            req = domain.MessageWebhookRequest.model_validate(message)
            raw = req.content
        except Exception:
            raw = message.get("content", "")

        try:
            data = json.loads(raw)
        except Exception:
            logging.info(f"[Hospital Message] Non-JSON message: {raw}")
            return True

        msg_type = data.get("type")
        logging.info(f"[Hospital Message] type={msg_type} data={data}")

        if msg_type == "DID_REGISTRATION_APPROVED":
            did = data.get("did")
            verkey = data.get("verkey")
            alias = data.get("alias", "Hospital")
            if did and verkey and self.repo:
                self.repo.upsert_institution_did(did=did, verkey=verkey, alias=alias, is_public=False)
                ok = self.admin_provider.set_public_did(did)
                if ok:
                    self.repo.set_institution_public(did)
                return ok
            return False

        if msg_type in ("DID_REGISTRATION_REJECTED", "CREDENTIAL_TYPE_PERMISSION_REJECTED"):
            request_id = data.get("request_id")
            if request_id and request_id in self.pending_permissions:
                self.pending_permissions[request_id]["status"] = "rejected"
                self.pending_permissions[request_id]["reason"] = data.get("reason")
            return True

        if msg_type == "CREDENTIAL_TYPE_PERMISSION_REQUEST_RECEIVED":
            request_id = data.get("request_id")
            if request_id and request_id in self.pending_permissions:
                self.pending_permissions[request_id]["status"] = "pending_review"
            return True

        return True

    def handle_present_proof_webhook(self, message: dict) -> bool:
        """Regulator -> Hospital: запрос present-proof-2.0 для подтверждения владения/статуса учреждения.

        Логика:
        - на state=request-received автоматически подбираем подходящие creds из кошелька больницы
        - отправляем presentation назад регулятору.
        """
        state = message.get("state")
        pres_ex_id = message.get("pres_ex_id")

        logging.info(f"[Hospital Proof] state={state} pres_ex_id={pres_ex_id}")

        if state == "presentation-received":
            record, ok = self.admin_provider.proof_verify_presentation(pres_ex_id)
            if not ok:
                logging.error(f"Failed to send proof_verify_presentation issue for {pres_ex_id}")
                return False

            return True

        # В разных сборках ACA-Py может быть: request-received / presentation-request-received
        if state not in ("request-received", "presentation-request-received", "request_sent", "request-sent"):
            return True

        if not pres_ex_id:
            return False

        creds, ok = self.admin_provider.proof_get_credentials(pres_ex_id)
        if not ok:
            logging.error(f"Cannot fetch credentials for proof exchange {pres_ex_id}: {creds}")
            return False

        # creds может быть списком, где каждый элемент — кандидат по referent
        requested_attributes: Dict[str, Any] = {}
        requested_predicates: Dict[str, Any] = {}

        # ожидаемый формат: [{"cred_info": {...}, "presentation_referents": ["attr1_referent", ...]}, ...]
        try:
            for item in creds:
                cred_info = item.get("cred_info", {})
                cred_id = cred_info.get("referent") or cred_info.get("cred_id")
                for ref in item.get("presentation_referents", []) or []:
                    # по умолчанию раскрываем
                    requested_attributes[ref] = {"cred_id": cred_id, "revealed": True}
        except Exception:
            # fallback: попробуем выбрать первый cred для каждого referent, если вернулся словарь
            pass

        # если не получилось собрать по presentation_referents, попробуем другой формат:
        if not requested_attributes and isinstance(creds, dict):
            for referent, items in creds.items():
                if items:
                    cred_info = items[0].get("cred_info", {})
                    cred_id = cred_info.get("referent")
                    requested_attributes[referent] = {"cred_id": cred_id, "revealed": True}

        presentation = {
            "comment": "auto-presentation from hospital_controller",
            "presentation": {
                "indy": {
                    "requested_attributes": requested_attributes,
                    "requested_predicates": requested_predicates,
                    "self_attested_attributes": {},
                }
            },
        }

        resp, ok = self.admin_provider.proof_send_presentation(pres_ex_id, presentation)
        if not ok:
            logging.error(f"Failed to send presentation: {resp}")
        return ok

    def handle_issue_credential_webhook(self, message: dict) -> bool:
        """Regulator -> Hospital: выдача VC-разрешения.

        Мы — holder:
        - offer-received => send-request
        - credential-received => сохраняем в БД (vc_type пытаемся извлечь из preview)
        """
        state = message.get("state")
        cred_ex_id = message.get("cred_ex_id")

        logging.info(f"[Hospital Credential] state={state} cred_ex_id={cred_ex_id}")

        if not cred_ex_id:
            return False

        if state in ("offer-received", "proposal-received"):
            _, ok = self.admin_provider.credential_send_request(cred_ex_id)
            return ok

        if state in ("credential-received", "done"):
            record, ok = self.admin_provider.credential_get_record(cred_ex_id)
            if not ok:
                logging.error(f"Failed to get cred record for {cred_ex_id}: {record}")
                return False

            vc_type = self._extract_vc_type_from_cred_record(record) or "unknown"
            credential_id = record.get("credential_id")

            if self.repo:
                saved = self.repo.save_permission_vc(vc_type=vc_type, cred_ex_id=cred_ex_id, raw_record=record, credential_id=credential_id)
                return saved

            return True

        if state == "request-received":
            record, ok = self.admin_provider.credential_issue(cred_ex_id)
            if not ok:
                logging.error(f"Failed to send cred issue for {cred_ex_id}")
                return False

            return True

        return True

    # -------------------- Public API (called from HttpAdapter) --------------------
    def create_invitation(self, alias: str = "City Hospital") -> Tuple[dict, bool]:
        data, ok = self.admin_provider.create_invitation(alias=alias)
        if not ok:
            return {"error": data}, False
        return {
            "invitation": data.get("invitation"),
            "invitation_url": data.get("invitation_url"),
            "connection_id": data.get("connection_id"),
        }, True

    def set_regulator_connection(self, connection_id: str) -> Tuple[dict, bool]:
        """Ручная привязка connection_id к ключу REGULATOR."""
        self.active_connections["REGULATOR"] = connection_id
        return {"ok": True, "connection_id": connection_id}, True

    def register_institution_did(self, alias: str) -> Tuple[dict, bool]:
        """Шаг 1: больница создаёт локальный DID и просит регулятора зарегистрировать NYM в блокчейне.

        Реализация (типовой паттерн):
        1) создаём DID в кошельке больницы
        2) отправляем регулятору structured basic message DID_REGISTRATION_REQUEST с did+verkey
        3) регулятор вносит NYM и отправляет обратно DID_REGISTRATION_APPROVED
        4) больница делает DID public.
        """
        regulator_conn = self.active_connections.get("REGULATOR")
        if not regulator_conn:
            return {"error": "No active connection with regulator"}, False

        did_res, ok = self.admin_provider.create_local_did(seed=self.admin_provider.cfg.DIDSeed)
        if not ok:
            return {"error": "Cannot create local DID", "details": did_res}, False

        did = did_res.get("result", {}).get("did") or did_res.get("did")
        verkey = did_res.get("result", {}).get("verkey") or did_res.get("verkey")
        if not did or not verkey:
            return {"error": "Unexpected /wallet/did/create response", "details": did_res}, False

        if self.repo:
            self.repo.upsert_institution_did(did=did, verkey=verkey, alias=alias, is_public=False)

        msg = {
            "type": "DID_REGISTRATION_REQUEST",
            "hospital_did": did,
            "verkey": verkey,
            "alias": alias,
            "timestamp": datetime.now().isoformat(),
        }
        resp, ok = self.admin_provider.send_message(regulator_conn, msg)
        if not ok:
            return {"error": "Failed to send request to regulator", "details": resp}, False

        return {"ok": True, "did": did, "verkey": verkey, "sent": True}, True

    def request_permission_for_vc_type(self, vc_type: str) -> Tuple[dict, bool]:
        """Шаг 3: запрос регулятору на проверку/разрешение выпускать данный тип VC.

        Ожидаемый протокол:
        - hospital -> regulator: basic message CREDENTIAL_TYPE_PERMISSION_REQUEST
        - regulator -> hospital: present-proof-2.0 request (подтверждение владения/статуса)
        - hospital -> regulator: presentation
        - regulator -> hospital: issue-credential-2.0 (VC-разрешение)
        """
        regulator_conn = self.active_connections.get("REGULATOR")
        if not regulator_conn:
            return {"error": "No active connection with regulator"}, False

        if self.repo:
            has, ok = self.repo.has_permission(vc_type)
            if ok and has:
                return {"ok": True, "already_authorized": True, "vc_type": vc_type}, True

        request_id = str(uuid.uuid4())
        self.pending_permissions[request_id] = {
            "vc_type": vc_type,
            "created_at": datetime.now().isoformat(),
            "status": "sent",
        }

        inst = None
        if self.repo:
            inst, _ = self.repo.get_institution()

        msg = {
            "type": "CREDENTIAL_TYPE_PERMISSION_REQUEST",
            "request_id": request_id,
            "credential_type": vc_type,
            "hospital_did": (inst or {}).get("did"),
            "timestamp": datetime.now().isoformat(),
        }

        resp, ok = self.admin_provider.send_message(regulator_conn, msg)
        if not ok:
            self.pending_permissions[request_id]["status"] = "failed_to_send"
            return {"error": "Failed to send request to regulator", "details": resp, "request_id": request_id}, False

        return {"ok": True, "request_id": request_id, "vc_type": vc_type}, True

    def create_schema_and_cred_def(self, vc_type: str, schema_name: str, schema_version: str, attributes: list) -> Tuple[dict, bool]:
        """Шаг 2: регистрация schema+cred-def в блокчейне (Indy).

        Критично: выполняем ТОЛЬКО если есть VC-разрешение от регулятора.
        """
        if self.repo:
            has, ok = self.repo.has_permission(vc_type)
            if not ok or not has:
                return {
                    "error": "Not authorized for this vc_type. Request permission first.",
                    "vc_type": vc_type,
                }, False

        # 1) schema find/create
        schema_find, ok = self.admin_provider.schema_created(schema_name)
        if ok and schema_find.get("schema_ids"):
            schema_id = schema_find["schema_ids"][0]
        else:
            schema_body = {
                "schema_name": schema_name,
                "schema_version": schema_version,
                "attributes": attributes,
            }
            schema_resp, ok = self.admin_provider.schema_create(schema_body)
            if not ok:
                return {"error": "Schema create failed", "details": schema_resp}, False
            schema_id = schema_resp.get("schema_id")

        if not schema_id:
            return {"error": "No schema_id"}, False

        # 2) cred-def find/create
        cred_def_find, ok = self.admin_provider.cred_def_created(schema_id)
        if ok and cred_def_find.get("credential_definition_ids"):
            cred_def_id = cred_def_find["credential_definition_ids"][0]
        else:
            cred_def_body = {
                "schema_id": schema_id,
                "support_revocation": False,
                "tag": vc_type,
            }
            cred_def_resp, ok = self.admin_provider.cred_def_create(cred_def_body)
            if not ok:
                return {"error": "CredDef create failed", "details": cred_def_resp}, False
            cred_def_id = cred_def_resp.get("credential_definition_id")

        return {"ok": True, "vc_type": vc_type, "schema_id": schema_id, "cred_def_id": cred_def_id}, True

    def list_permissions(self) -> Tuple[dict, bool]:
        if not self.repo:
            return {"permissions": []}, True
        rows, ok = self.repo.list_permissions()
        if not ok:
            return {"error": "DB error"}, False
        return {"permissions": rows}, True

    # -------------------- Helpers --------------------
    @staticmethod
    def _extract_vc_type_from_cred_record(record: dict) -> Optional[str]:
        """Пытаемся извлечь vc_type из cred preview (регуляторский VC-разрешение)."""
        # Вариант 1: cred_preview.attributes
        preview = record.get("cred_preview") or record.get("credential_preview")
        attrs = None
        if isinstance(preview, dict):
            attrs = preview.get("attributes")

        if isinstance(attrs, list):
            for a in attrs:
                if a.get("name") in ("vc_type", "credential_type", "type"):
                    return a.get("value")

        # Вариант 2: by_format/... может содержать предложенный атрибутный словарь
        by_format = record.get("by_format") or {}
        indy = None
        try:
            indy = by_format.get("cred_offer", {}).get("indy")
        except Exception:
            indy = None
        if isinstance(indy, dict):
            # иногда есть "schema_id" и "cred_def_id" только
            pass

        return None

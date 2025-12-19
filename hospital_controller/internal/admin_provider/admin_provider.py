import logging
from typing import Any, Dict, Optional, Tuple

import requests

from hospital_controller.internal.domain.config import AdminProvider as ConfigAdminProvider


def send_request(method: str, url: str, headers: Dict[str, str], json_body: Optional[dict] = None) -> Tuple[Any, bool]:
    """Небольшой враппер над requests.request.

    Возвращает (content, ok). content — json (если возможно) или текст ошибки.
    """
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_body if method.upper() not in ("GET", "DELETE") else None,
        )

        if 200 <= response.status_code < 300:
            logging.info(f"Send request to {url} completed")
            try:
                return response.json(), True
            except Exception:
                return response.text, True

        logging.error(f"Send request error: {url} {response.status_code} {response.text}")
        try:
            return response.json(), False
        except Exception:
            return response.text, False

    except Exception as e:
        logging.error(f"Send request exception: {url} {e}")
        return None, False


class AdminProvider:
    """Провайдер исходящих HTTP-запросов к ACA-Py Admin API агента больницы."""

    def __init__(self, cfg: ConfigAdminProvider):
        self.url = f"{cfg.Host}:{cfg.Port}"
        self.headers = {"X-API-Key": cfg.APIKey, "Content-Type": "application/json"}
        self.cfg = cfg

    # --- Connections ---
    def accept_connection(self, connection_id: str) -> bool:
        path = self.cfg.Endpoints.AcceptConnection.Path.replace("{connection_id}", connection_id)
        _, ok = send_request(self.cfg.Endpoints.AcceptConnection.Method, self.url + path, self.headers, {})
        return ok

    def create_invitation(self, alias: str, use_did_method: str = "did:peer:4") -> Tuple[Any, bool]:
        body = {
            "use_did_method": use_did_method,
            "handshake_protocols": ["https://didcomm.org/didexchange/1.1"],
            "alias": alias,
            "auto_accept": True,
        }
        _, ok = send_request(self.cfg.Endpoints.CreateInvitation.Method, self.url + self.cfg.Endpoints.CreateInvitation.Path,
                             self.headers, body)
        return _, ok

    # --- Wallet DID ---
    def create_local_did(self, seed: str) -> Tuple[Any, bool]:
        body = {
            "method": "sov",
            "options": {"key_type": "ed25519"},
            "seed": seed,
        }
        return send_request(self.cfg.Endpoints.WalletCreateDID.Method, self.url + self.cfg.Endpoints.WalletCreateDID.Path,
                           self.headers, body)

    def set_public_did(self, did: str) -> bool:
        path = self.cfg.Endpoints.WalletSetPublicDID.Path.replace("{did}", did)
        _, ok = send_request(self.cfg.Endpoints.WalletSetPublicDID.Method, self.url + path, self.headers, {})
        return ok

    # --- DIDComm basicmessages ---
    def send_message(self, connection_id: str, request: dict) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.SendMessage.Path.replace("{connection_id}", connection_id)
        return send_request(self.cfg.Endpoints.SendMessage.Method, self.url + path, self.headers, request)

    # --- present-proof-2.0 (prover side) ---
    def proof_get_credentials(self, pres_ex_id: str) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.ProofGetCredentials.Path.replace("{pres_ex_id}", pres_ex_id)
        return send_request(self.cfg.Endpoints.ProofGetCredentials.Method, self.url + path, self.headers)

    def proof_send_presentation(self, pres_ex_id: str, presentation: dict) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.ProofSendPresentation.Path.replace("{pres_ex_id}", pres_ex_id)
        return send_request(self.cfg.Endpoints.ProofSendPresentation.Method, self.url + path, self.headers, presentation)

    # --- issue-credential-2.0 (holder side) ---
    def credential_send_request(self, cred_ex_id: str) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.CredentialSendRequest.Path.replace("{cred_ex_id}", cred_ex_id)
        return send_request(self.cfg.Endpoints.CredentialSendRequest.Method, self.url + path, self.headers, {})

    def credential_get_record(self, cred_ex_id: str) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.CredentialGetRecord.Path.replace("{cred_ex_id}", cred_ex_id)
        return send_request(self.cfg.Endpoints.CredentialGetRecord.Method, self.url + path, self.headers)

    # --- Indy ledger operations (use only after regulator permission) ---
    def schema_created(self, schema_name: str) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.SchemaCreated.Path.replace("{schema_name}", schema_name)
        return send_request(self.cfg.Endpoints.SchemaCreated.Method, self.url + path, self.headers)

    def schema_create(self, schema_body: dict) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.SchemaCreate.Path
        return send_request(self.cfg.Endpoints.SchemaCreate.Method, self.url + path, self.headers, schema_body)

    def cred_def_created(self, schema_id: str) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.CredDefCreated.Path.replace("{schema_id}", schema_id)
        return send_request(self.cfg.Endpoints.CredDefCreated.Method, self.url + path, self.headers)

    def cred_def_create(self, cred_def_body: dict) -> Tuple[Any, bool]:
        path = self.cfg.Endpoints.CredDefCreate.Path
        return send_request(self.cfg.Endpoints.CredDefCreate.Method, self.url + path, self.headers, cred_def_body)

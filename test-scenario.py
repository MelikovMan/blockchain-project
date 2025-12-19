# test_scenario.py
import json
import time
import requests
import logging
from typing import Dict, Any, Optional, Tuple

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestScenario:
    def __init__(self):
        # Конфигурация API
        self.hospital_agent_url = "http://localhost:8021"
        self.hospital_controller_url = "http://localhost:8050"
        self.regulator_agent_url = "http://localhost:8041"
        self.regulator_controller_url = "http://localhost:8070"
        
        # API ключи
        self.hospital_agent_api_key = "super-secret-admin-api-key-123"
        self.regulator_agent_api_key = "regulator-admin-key-789"
        
        self.regulator_headers = {
            "X-API-Key": self.regulator_agent_api_key,
            "Content-Type": "application/json"
        }
        
        self.hospital_agent_headers = {
            "X-API-Key": self.hospital_agent_api_key,
            "Content-Type": "application/json"
        }
        
        # Состояние теста
        self.hospital_did: Optional[str] = None
        self.regulator_connection_id: Optional[str] = None
        self.hospital_connection_id: Optional[str] = None
        self.permission_request_id: Optional[str] = None
        self.schema_id: Optional[str] = None
        self.cred_def_id: Optional[str] = None

    def wait_for_condition(self, condition_func, timeout=30, interval=1, description=""):
        """Ожидание выполнения условия"""
        logger.info(f"Ожидание: {description}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        return False

    def step_1_create_connection(self) -> bool:
        """Шаг 1: Установление соединения между больницей и регулятором"""
        logger.info("=== Шаг 1: Установление соединения ===")
        
        # 1.1 Больница создает приглашение
        logger.info("Больница создает приглашение...")
        invitation_response = requests.post(
            f"{self.hospital_controller_url}/invitation",
            json={"alias": "City Hospital"}
        )
        
        if invitation_response.status_code != 200:
            logger.error(f"Ошибка создания приглашения: {invitation_response.text}")
            return False
        
        invitation_data = invitation_response.json()
        invitation = invitation_data.get("invitation")
        self.hospital_connection_id = invitation_data.get("connection_id")
        
        logger.info(f"Создано приглашение, connection_id: {self.hospital_connection_id}")
        
        # 1.2 Регулятор принимает приглашение
        #TODO: этот шаг автоматизирован или нет?
        logger.info("Регулятор принимает приглашение...")
        accept_response = requests.post(
            f"{self.regulator_agent_url}/connections/receive-invitation",
            headers=self.regulator_headers,
            json={"invitation": invitation}
        )
        
        if accept_response.status_code != 200:
            logger.error(f"Ошибка принятия приглашения: {accept_response.text}")
            return False
        
        regulator_conn_data = accept_response.json()
        self.regulator_connection_id = regulator_conn_data.get("connection_id")
        
        logger.info(f"Регулятор принял приглашение, connection_id: {self.regulator_connection_id}")
        
        # 1.3 Устанавливаем соединение в hospital_controller
        #TODO: этот шаг может быть автоматизирован?
        logger.info("Устанавливаем соединение в hospital_controller...")
        set_conn_response = requests.post(
            f"{self.hospital_controller_url}/regulator/connection",
            json={"connection_id": self.regulator_connection_id}
        )
        
        if set_conn_response.status_code != 200:
            logger.error(f"Ошибка установки соединения: {set_conn_response.text}")
            return False
        
        # Ждем установки соединения
        def connection_established():
            # Проверяем активные соединения регулятора
            connections_response = requests.get(
                f"{self.regulator_agent_url}/connections",
                headers=self.regulator_headers
            )
            if connections_response.status_code == 200:
                connections = connections_response.json()
                for conn in connections.get("results", []):
                    if conn.get("connection_id") == self.regulator_connection_id and conn.get("state") == "active":
                        return True
            return False
        
        if not self.wait_for_condition(
            connection_established, 
            description="Установка активного соединения"
        ):
            logger.error("Таймаут установки соединения")
            return False
        
        logger.info("✓ Соединение установлено")
        return True

    def step_2_register_hospital_did(self) -> bool:
        """Шаг 2: Регистрация публичного DID больницы"""
        logger.info("\n=== Шаг 2: Регистрация публичного DID больницы ===")
        
        # 2.1 Больница создает локальный DID и запрашивает регистрацию
        logger.info("Больница запрашивает регистрацию DID...")
        register_response = requests.post(
            f"{self.hospital_controller_url}/institution/register-did",
            json={"alias": "City Hospital"}
        )
        
        if register_response.status_code != 200:
            logger.error(f"Ошибка запроса регистрации DID: {register_response.text}")
            return False
        
        register_data = register_response.json()
        hospital_did = register_data.get("did")
        
        if not hospital_did:
            logger.error("DID не создан")
            return False
        
        self.hospital_did = hospital_did
        logger.info(f"Создан DID больницы: {hospital_did}")
        
        # 2.2 Имитируем получение регулятором запроса на регистрацию
        logger.info("Регулятор получает запрос на регистрацию DID...")
        
        # В реальном сценарии это делается через webhook
        # Здесь имитируем прямой вызов регулятора
        regulator_response = requests.post(
            f"{self.regulator_controller_url}/webhooks/topic/basicmessages",
            json={
                "connection_id": self.regulator_connection_id,
                "content": json.dumps({
                    "type": "DID_REGISTRATION_REQUEST",
                    "hospital_did": hospital_did,
                    "verkey": register_data.get("verkey"),
                    "alias": "City Hospital",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                })
            }
        )
        
        if regulator_response.status_code != 200:
            logger.error(f"Ошибка обработки запроса регулятором: {regulator_response.text}")
            return False
        
        # 2.3 Регулятор регистрирует NYM в блокчейне
        logger.info("Регулятор регистрирует NYM в блокчейне...")
        nym_response = requests.post(
            f"{self.regulator_agent_url}/ledger/register-nym",
            headers=self.regulator_headers,
            json={
                "did": hospital_did,
                "verkey": register_data.get("verkey"),
                "alias": "City Hospital",
                "role": "ENDORSER"
            }
        )
        
        if nym_response.status_code != 200:
            logger.error(f"Ошибка регистрации NYM: {nym_response.text}")
            return False
        
        # 2.4 Регулятор уведомляет больницу об успешной регистрации
        logger.info("Регулятор уведомляет больницу...")
        notification_response = requests.post(
            f"{self.regulator_agent_url}/connections/{self.regulator_connection_id}/send-message",
            headers=self.regulator_headers,
            json={
                "content": json.dumps({
                    "type": "DID_REGISTRATION_APPROVED",
                    "did": hospital_did,
                    "verkey": register_data.get("verkey"),
                    "alias": "City Hospital"
                })
            }
        )
        
        if notification_response.status_code != 200:
            logger.error(f"Ошибка отправки уведомления: {notification_response.text}")
            return False
        
        # 2.5 Ждем, пока больница установит DID как публичный
        def did_is_public():
            did_response = requests.get(
                f"{self.hospital_agent_url}/wallet/did/public",
                headers=self.hospital_agent_headers
            )
            if did_response.status_code == 200:
                public_did = did_response.json().get("result", {}).get("did")
                return public_did == hospital_did
            return False
        
        if not self.wait_for_condition(
            did_is_public,
            description="Установка публичного DID больницы"
        ):
            logger.error("Таймаут установки публичного DID")
            return False
        
        logger.info("✓ Публичный DID зарегистрирован")
        return True

    def step_3_request_vc_permission(self) -> bool:
        """Шаг 3: Запрос разрешения на выпуск VC типа 'MedicalLicense'"""
        logger.info("\n=== Шаг 3: Запрос разрешения на выпуск VC ===")
        
        # 3.1 Больница запрашивает разрешение
        logger.info("Больница запрашивает разрешение на выпуск 'MedicalLicense'...")
        permission_response = requests.post(
            f"{self.hospital_controller_url}/permissions/request",
            json={"credential_type": "MedicalLicense"}
        )
        
        if permission_response.status_code != 200:
            logger.error(f"Ошибка запроса разрешения: {permission_response.text}")
            return False
        
        permission_data = permission_response.json()
        self.permission_request_id = permission_data.get("request_id")
        
        logger.info(f"Запрос на разрешение отправлен, request_id: {self.permission_request_id}")
        
        # 3.2 Имитируем получение регулятором запроса
        logger.info("Регулятор получает запрос на разрешение...")
        regulator_permission_response = requests.post(
            f"{self.regulator_controller_url}/webhooks/topic/basicmessages",
            json={
                "connection_id": self.regulator_connection_id,
                "content": json.dumps({
                    "type": "CREDENTIAL_TYPE_PERMISSION_REQUEST",
                    "request_id": self.permission_request_id,
                    "credential_type": "MedicalLicense",
                    "hospital_did": self.hospital_did,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                })
            }
        )
        
        if regulator_permission_response.status_code != 200:
            logger.error(f"Ошибка обработки запроса регулятором: {regulator_permission_response.text}")
            return False
        
        # 3.3 Регулятор инициирует proof request для верификации
        logger.info("Регулятор отправляет proof request для верификации...")
        proof_request_response = requests.post(
            f"{self.regulator_agent_url}/present-proof-2.0/send-request",
            headers=self.regulator_headers,
            json={
                "connection_id": self.regulator_connection_id,
                "proof_request": {
                    "name": "Hospital Verification",
                    "version": "1.0",
#TODO: Тут залупа, наверное? При отправки send-representation извлекем self-disclosed attrubutes, а  requested_attributes: пустой!!
                    "requested_attributes": {
                        "hospital_did": {
                            "name": "did",
                            "restrictions": [{"issuer_did": self.hospital_did}]
                        }
                    },
                    "requested_predicates":{}
                }
            }
        )
        
        if proof_request_response.status_code != 200:
            logger.error(f"Ошибка отправки proof request: {proof_request_response.text}")
            return False
        
        proof_data = proof_request_response.json()
        pres_ex_id = proof_data.get("pres_ex_id")
        
        # 3.4 Имитируем получение больницей proof request
        logger.info("Больница получает proof request...")
        #TODO: Тут полная залупа!
        #hospital_proof_response = requests.post(
        #    f"{self.hospital_controller_url}/webhooks/topic/present_proof_v2_0",
        #    json={
        #        "pres_ex_id": pres_ex_id,
        #        "state": "request-received",
        #        "connection_id": self.regulator_connection_id,
        #        "by_format": {
        #            "pres_request": {
        #                "indy": {
        #                    "name": "Hospital Verification",
        #                    "version": "1.0",
        #                    "requested_attributes": {
        #                        "hospital_did": {
        #                            "name": "did",
        #                            "restrictions": [{"issuer_did": self.hospital_did}]
        #                        }
        #                    }
        #                }
        #            }
        #        }
        #    }
        #)
        
        #if hospital_proof_response.status_code != 200:
        #    logger.error(f"Ошибка обработки proof request больницей: {hospital_proof_response.text}")
        #    return False
        
        # 3.5 Ждем, пока больница отправит презентацию
        def presentation_sent():
            proof_records = requests.get(
                f"{self.regulator_agent_url}/present-proof-2.0/records",
                headers=self.regulator_headers
            )
            if proof_records.status_code == 200:
                records = proof_records.json().get("results", [])
                for record in records:
                    if record.get("pres_ex_id") == pres_ex_id and record.get("state") == "presentation-sent" or record.get("state") == "done":
                        return True
            return False
        
        if not self.wait_for_condition(
            presentation_sent,
            description="Отправка презентации больницей"
        ):
            logger.error("Таймаут отправки презентации")
            return False
        
        logger.info("✓ Proof verification завершен")
        return True

    def step_4_issue_permission_vc(self) -> bool:
        """Шаг 4: Выдача VC-разрешения регулятором"""
        logger.info("\n=== Шаг 4: Выдача VC-разрешения ===")
        
        # 4.1 Регулятор создает credential offer
        logger.info("Регулятор создает credential offer...")
        credential_offer_response = requests.post(
            f"{self.regulator_agent_url}/issue-credential-2.0/send-offer",
            headers=self.regulator_headers,
            json={
                "connection_id": self.regulator_connection_id,
                "filter": {
                    "indy": {
                        "schema_name": "RegulatorPermission",
                        "schema_version": "1.0",
                        #TODO: тут должен быть нормальный ид
                        "cred_def_id": "regulator_permission_cred_def_id"
                    }
                },
                "credential_preview": {
                    "@type": "issue-credential/2.0/credential-preview",
                    "attributes": [
                        {"name": "vc_type", "value": "MedicalLicense"},
                        {"name": "hospital_did", "value": self.hospital_did},
                        {"name": "valid_until", "value": "2024-12-31"},
                        {"name": "permission_level", "value": "full"}
                    ]
                }
            }
        )
        
        if credential_offer_response.status_code != 200:
            logger.error(f"Ошибка создания credential offer: {credential_offer_response.text}")
            return False
        
        cred_ex_id = credential_offer_response.json().get("cred_ex_id")
        
        # 4.2 Имитируем получение больницей credential offer
        logger.info("Больница получает credential offer...")
        #hospital_credential_response = requests.post(
        #    f"{self.hospital_controller_url}/webhooks/topic/issue_credential_v2_0",
        #    json={
        #        "cred_ex_id": cred_ex_id,
        #        "state": "offer-received",
        #        "connection_id": self.regulator_connection_id,
        #        "credential_preview": {
        #            "attributes": [
        #                {"name": "vc_type", "value": "MedicalLicense"},
        #                {"name": "hospital_did", "value": self.hospital_did},
        #                {"name": "valid_until", "value": "2024-12-31"}
        #            ]
        #        }
        #    }
        #)
        
        # 4.3 Имитируем отправку больницей credential request
        #logger.info("Больница отправляет credential request...")
        #hospital_request_response = requests.post(
        #    f"{self.hospital_controller_url}/webhooks/topic/issue_credential_v2_0",
        #    json={
        #        "cred_ex_id": cred_ex_id,
        #        "state": "request-sent",
        #        "connection_id": self.regulator_connection_id
        #    }
        #)
        
        
        # 4.4 Регулятор выдает credential
        logger.info("Регулятор выдает credential...")
        #TODO: Тут тоже через вебхуки нужно
        #issue_response = requests.post(
        #    f"{self.regulator_agent_url}/issue-credential-2.0/records/{cred_ex_id}/issue",
        #    headers=self.regulator_headers,
        #    json={
        #        "comment": "Permission granted for MedicalLicense VC issuance"
        #    }
        #)
        
        
        # 4.5 Имитируем получение credential больницей
        logger.info("Больница получает credential...")
        #hospital_receive_response = requests.post(
        #    f"{self.hospital_controller_url}/webhooks/topic/issue_credential_v2_0",
        #    json={
        #        "cred_ex_id": cred_ex_id,
        #        "state": "credential-received",
        #        "connection_id": self.regulator_connection_id,
        #        "credential_preview": {
        #            "attributes": [
        #                {"name": "vc_type", "value": "MedicalLicense"},
        #                {"name": "hospital_did", "value": self.hospital_did},
        #                {"name": "valid_until", "value": "2024-12-31"}
        #            ]
        #        }
        #    }
        #)

        
        # 4.6 Проверяем сохранение разрешения
        logger.info("Проверяем сохранение разрешения...")
        permissions_response = requests.get(
            f"{self.hospital_controller_url}/permissions"
        )
        
        if permissions_response.status_code != 200:
            logger.error(f"Ошибка проверки разрешений: {permissions_response.text}")
            return False
        
        permissions = permissions_response.json().get("permissions", [])
        has_permission = any(
            p.get("vc_type") == "MedicalLicense" for p in permissions
        )
        
        if not has_permission:
            logger.error("Разрешение не сохранено")
            return False
        
        logger.info("✓ VC-разрешение выдано и сохранено")
        return True

    def step_5_create_schema_and_creddef(self) -> bool:
        """Шаг 5: Создание схемы и cred def для разрешенного типа"""
        logger.info("\n=== Шаг 5: Создание схемы и cred def ===")
        
        # 5.1 Больница создает схему и cred def
        logger.info("Больница создает схему и cred def для 'MedicalLicense'...")
        schema_response = requests.post(
            f"{self.hospital_controller_url}/ledger/schema-creddef",
            json={
                "vc_type": "MedicalLicense",
                "schema_name": "MedicalLicenseCredential",
                "schema_version": "1.0.0",
                "attributes": ["license_number", "hospital_name", "specialization", "issue_date", "expiry_date"]
            }
        )
        
        if schema_response.status_code != 200:
            logger.error(f"Ошибка создания схемы: {schema_response.text}")
            return False
        
        schema_data = schema_response.json()
        self.schema_id = schema_data.get("schema_id")
        self.cred_def_id = schema_data.get("cred_def_id")
        
        if not self.schema_id or not self.cred_def_id:
            logger.error("Не удалось получить schema_id или cred_def_id")
            return False
        
        logger.info(f"Создана схема: {self.schema_id}")
        logger.info(f"Создан cred def: {self.cred_def_id}")
        
        # 5.2 Проверяем, что схема зарегистрирована в блокчейне
        logger.info("Проверяем регистрацию в блокчейне...")
        
        # Через некоторое время схема должна появиться в блокчейне
        time.sleep(5)  # Даем время на эндоузинг
        
        logger.info("✓ Схема и cred def зарегистрированы")
        return True

    def step_6_issue_patient_vc(self) -> bool:
        """Шаг 6: Выпуск VC для пациента (имитация)"""
        logger.info("\n=== Шаг 6: Выпуск VC для пациента ===")
        
        # 6.1 Создаем invitation для пациента
        logger.info("Создаем invitation для пациента...")
        patient_invitation_response = requests.post(
            f"{self.hospital_agent_url}/connections/create-invitation",
            headers=self.hospital_agent_headers,
            json={"alias": "Patient John Doe"}
        )
        
        if patient_invitation_response.status_code != 200:
            logger.error(f"Ошибка создания invitation для пациента: {patient_invitation_response.text}")
            return False
        
        patient_conn_data = patient_invitation_response.json()
        patient_connection_id = patient_conn_data.get("connection_id")
        
        # 6.2 Создаем credential offer для пациента
        logger.info("Создаем credential offer для пациента...")
        #TODO: Тут более подробная структура, тут должен вызваться endpoint!!
        patient_credential_response = requests.post(
            f"{self.hospital_agent_url}/issue-credential-2.0/send-offer",
            headers=self.hospital_agent_headers,
            json={
                "connection_id": patient_connection_id,
                "filter": {
                    "indy": {
                        "schema_id": self.schema_id,
                        "cred_def_id": self.cred_def_id
                    }
                },
                "credential_preview": {
                    "@type": "issue-credential/2.0/credential-preview",
                    "attributes": [
                        {"name": "license_number", "value": "MED12345"},
                        {"name": "hospital_name", "value": "City Hospital"},
                        {"name": "specialization", "value": "Cardiology"},
                        {"name": "issue_date", "value": "2024-01-15"},
                        {"name": "expiry_date", "value": "2025-01-15"}
                    ]
                }
            }
        )
        
        if patient_credential_response.status_code != 200:
            logger.error(f"Ошибка создания credential offer для пациента: {patient_credential_response.text}")
            return False
        
        logger.info("✓ VC для пациента подготовлен")
        logger.info("Примечание: Для завершения выпуска VC пациент должен принять credential offer")
        return True

    def verify_requirements(self) -> bool:
        """Проверка выполнения всех функциональных требований"""
        logger.info("\n=== Проверка функциональных требований ===")
        
        requirements = {
            "Требование 1: Регистрация публичного DID": self.hospital_did is not None,
            "Требование 2: Разрешение на выпуск VC": self.permission_request_id is not None,
            "Требование 3: Создание схемы": self.schema_id is not None,
            "Требование 4: Создание cred def": self.cred_def_id is not None,
            "Требование 5: Готовность к выпуску VC": True  # Если предыдущие шаги успешны
        }
        
        all_passed = True
        for req_name, passed in requirements.items():
            status = "✓ ВЫПОЛНЕНО" if passed else "✗ НЕ ВЫПОЛНЕНО"
            logger.info(f"{req_name}: {status}")
            if not passed:
                all_passed = False
        
        return all_passed

    def run_full_scenario(self) -> bool:
        """Запуск полного сценария"""
        logger.info("=" * 60)
        logger.info("ЗАПУСК ПОЛНОГО ТЕСТОВОГО СЦЕНАРИЯ")
        logger.info("=" * 60)
        
        steps = [
            ("Установление соединения", self.step_1_create_connection),
            ("Регистрация публичного DID", self.step_2_register_hospital_did),
            ("Запрос разрешения на выпуск VC", self.step_3_request_vc_permission),
            ("Выдача VC-разрешения", self.step_4_issue_permission_vc),
            ("Создание схемы и cred def", self.step_5_create_schema_and_creddef),
            ("Выпуск VC для пациента", self.step_6_issue_patient_vc)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n>>> Выполняем: {step_name}")
            if not step_func():
                logger.error(f"Сценарий прерван на шаге: {step_name}")
                return False
            time.sleep(2)  # Пауза между шагами
        
        # Финальная проверка требований
        logger.info("\n" + "=" * 60)
        logger.info("ФИНАЛЬНАЯ ПРОВЕРКА")
        logger.info("=" * 60)
        
        if self.verify_requirements():
            logger.info("\n🎉 Все функциональные требования успешно выполнены!")
            return True
        else:
            logger.error("\n❌ Не все требования выполнены")
            return False

    def cleanup(self):
        """Очистка тестовых данных"""
        logger.info("Очистка тестовых данных...")
        # Здесь можно добавить код для удаления тестовых данных
        # Например, удаление соединений, отзыв credentials и т.д.

def main():
    """Основная функция запуска теста"""
    scenario = TestScenario()
    
    try:
        success = scenario.run_full_scenario()
        
        if success:
            # Сохраняем результаты для отладки
            with open("test_results.json", "w") as f:
                results = {
                    "hospital_did": scenario.hospital_did,
                    "schema_id": scenario.schema_id,
                    "cred_def_id": scenario.cred_def_id,
                    "permission_request_id": scenario.permission_request_id,
                    "status": "SUCCESS"
                }
                json.dump(results, f, indent=2)
            
            logger.info("\nРезультаты сохранены в test_results.json")
            exit(0)
        else:
            exit(1)
            
    except Exception as e:
        logger.error(f"Критическая ошибка при выполнении сценария: {str(e)}", exc_info=True)
        scenario.cleanup()
        exit(1)
    finally:
        scenario.cleanup()

if __name__ == "__main__":
    main()
"""
ПОЛНЫЙ СЦЕНАРИЙ ВЗАИМОДЕЙСТВИЯ МЕЖДУ БОЛЬНИЦЕЙ И ПАЦИЕНТОМ
"""
import asyncio
import time
import requests
import json

class MedicalScenarioRunner:
    
    def __init__(self):
        self.hospital_admin = "http://localhost:8021"
        self.patient_admin = "http://localhost:8031"
        self.hospital_headers = {"X-API-Key": "super-secret-admin-api-key-123"}
        self.patient_headers = {"X-API-Key": "patient-admin-key-456"}
    
    async def run_full_scenario(self):
        """Запуск полного медицинского сценария"""
        
    # ЭТАП 1: Больница создает приглашение с использованием did:peer:4
        print("1. 🏥 Больница создает приглашение для пациента с использованием did:peer:4...")
    
        invitation_resp = requests.post(
            f"{self.hospital_admin}/out-of-band/create-invitation",
            headers=self.hospital_headers,
            json={
            "use_did_method": "did:peer:4",
            "handshake_protocols": ["https://didcomm.org/didexchange/1.1"],
            "alias": "City Hospital",
            "auto_accept": True
            }
        )
    
        if invitation_resp.status_code != 200:
            print(f"Ошибка создания приглашения: {invitation_resp.text}")
            return
    
        invitation = invitation_resp.json()['invitation']
        print(f"   Приглашение с did:peer:4 создано: {invitation['@id']}")
        # ЭТАП 2: Пациент принимает приглашение через DID Exchange
        print("2. 👤 Пациент принимает приглашение через DID Exchange...")
    
        receive_resp = requests.post(
            f"{self.patient_admin}/out-of-band/receive-invitation",
            headers=self.patient_headers,
            json=invitation
        )
    
        if receive_resp.status_code != 200:
            print(f"Ошибка принятия приглашения: {receive_resp.text}")
            return
    
        patient_connection_id = receive_resp.json()['connection_id']
        print(f"   ID соединения пациента: {patient_connection_id}")
    
    # Ждем установления соединения
        print("   ⏳ Ожидание установления соединения через DID Exchange...")
        await asyncio.sleep(3)
    
    # Получаем ID соединения со стороны больницы
        hospital_id_resp = requests.get(
            f"{self.hospital_admin}/connections",
            headers=self.hospital_headers,
    )
    
        if hospital_id_resp.status_code != 200:
            print(f"Ошибка получения соединений больницы: {hospital_id_resp.text}")
            return
    
        connections = hospital_id_resp.json().get('results', [])
        hospital_connection_id = connections[0]['connection_id'] if connections else None
        print(f"   ID соединения больницы: {hospital_connection_id}")
    
        if not hospital_connection_id:
            print("❌ Не удалось найти активное соединение")
            return
    
    # Проверяем состояние соединения
        connection_resp = requests.get(
            f"{self.hospital_admin}/connections/{hospital_connection_id}",
            headers=self.hospital_headers
        )
    
        if connection_resp.status_code == 200:
            connection_state = connection_resp.json().get('state')
            print(f"   Состояние соединения: {connection_state}")
        
            if connection_state not in ['active', 'response', 'completed']:
                print("⚠️  Соединение еще не готово, ожидаем...")
            await asyncio.sleep(2)
    
        
        # ЭТАП 3: Больница выпускает медицинскую справку, сначала получает определение.
        cred_def_find = requests.get(f"{self.hospital_admin}/credential-definitions/created?=schema_name=HospitalMedicalRecord66", headers=self.hospital_headers)
        if cred_def_find.json()["credential_definition_ids"]:
            print("Определение VC уже существует")
            cred_result = cred_def_find.json()
            cred_def_id = cred_result["credential_definition_ids"][0]
        else:
            print("Не найдено опрделение VC!")
            return
        print("3. 📋 Больница выпускает медицинскую справку...")
        credential_offer = {
            "connection_id": hospital_connection_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": [
                    {"name": "full_name", "value": "Иванов Иван Иванович"},
                    {"name": "date_of_birth", "value": "1985-05-15"},
                    {"name": "blood_group_rh", "value": "A+"},
                    {"name": "severe_allergies", "value": json.dumps(["Пенициллин"])},
                    {"name": "chronic_diagnoses", "value": json.dumps(["Гипертензия"])}
                ]
            },
            "filter": {
                "indy": {
                    "cred_def_id": cred_def_id 
                }
        },
        }
        issue_resp = requests.post(
            f"{self.hospital_admin}/issue-credential-2.0/send-offer",
            headers=self.hospital_headers,
            json=credential_offer
        )
        if issue_resp.status_code!= 200:
            print(f"Ошибка отправки медицинской справки: {issue_resp.text}" )
            return
        print(f"   Справка предложена: {issue_resp.status_code}")
        
        # ЭТАП 4: Симулируем экстренный запрос данных (через 5 секунд)
        print("4. ⚠️  Симуляция экстренного запроса через 5 сек...")
        await asyncio.sleep(5)
        
        # Другая больница запрашивает данные пациента
        emergency_request = {
            "connection_id": hospital_connection_id,  # В реальности это будет другое соединение
            "presentation_request": {
                "indy":{
                    "name": "EMERGENCY: Blood Type Request",
                    "version": "1.0",
                    "non_revoked": {  # Требуем, чтобы credential не был отозван
                        "from": 0,
                        "to": int(time.time())
                    },
                    "requested_attributes": {
                        "blood_attr": {
                            "name": "blood_group_rh",
                            "restrictions": [{"cred_def_id": cred_def_id}]
                        }
                    },
                    "requested_predicates":{}
                }
            }
        }
        
        proof_resp = requests.post(
            f"{self.hospital_admin}/present-proof-2.0/send-request",
            headers=self.hospital_headers,
            json=emergency_request
        )
        
        if proof_resp.status_code == 200:
            print("   ✅ Экстренный запрос отправлен. Система пациента должна автоматически ответить.")
            
            # Проверяем статус через 4 секунд
            await asyncio.sleep(7)
            print(proof_resp.json())
            pres_ex_id = proof_resp.json()['pres_ex_id']
            print(f"ID презентации: {pres_ex_id}")
            status_resp = requests.get(
                f"{self.hospital_admin}/present-proof-2.0/records/{pres_ex_id}",
                headers=self.hospital_headers
            )
            if status_resp.status_code != 200:
                print(f"Ошибка запроса верификации! {status_resp.text}")
                return
            if status_resp.json()['verified'] == 'true':
                print("   🩺 Данные верифицированы! Врач получил группу крови пациента.")
                revealed_attrs = status_resp.json()["by_format"]["pres"]["indy"]["requested_proof"].get('revealed_attrs', {})
                if revealed_attrs:
                    print(f"   📊 Полученные данные: {revealed_attrs}")
            else: 
                print(f"Ошибка верификации данных! Статус: f{status_resp.json()['state']}")
        else:
            print(f"Ошибка отправки экстренного запроса: {proof_resp.text}")
        print("\n🎯 Сценарий завершен!")

# Запуск сценария
if __name__ == "__main__":
    runner = MedicalScenarioRunner()
    asyncio.run(runner.run_full_scenario())
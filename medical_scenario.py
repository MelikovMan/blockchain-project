"""
ПОЛНЫЙ СЦЕНАРИЙ ВЗАИМОДЕЙСТВИЯ МЕЖДУ БОЛЬНИЦЕЙ И ПАЦИЕНТОМ
"""
import asyncio
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
        
        # ЭТАП 1: Больница создает приглашение для пациента
        print("1. 🏥 Больница создает приглашение для пациента...")
        invitation_resp = requests.post(
            f"{self.hospital_admin}/connections/create-invitation",
            headers=self.hospital_headers,
            json={"auto_accept": True}
        )
        invitation = invitation_resp.json()['invitation']
        print(f"   Приглашение создано: {invitation['@id']}")
        
        # ЭТАП 2: Пациент принимает приглашение
        print("2. 👤 Пациент принимает приглашение...")
        receive_resp = requests.post(
            f"{self.patient_admin}/connections/receive-invitation",
            headers=self.patient_headers,
            json=invitation
        )
        if receive_resp.status_code != 200:
            print(f"Ошибка принятия приглашения: {receive_resp.text}")
            return
        patient_connection_id = receive_resp.json()['connection_id']
        print(f"Id соедиения пациента: {patient_connection_id}")
        # Ждем установления соединения

        hospital_id_resp = requests.get(
            f"{self.hospital_admin}/connections",
            headers=self.hospital_headers,
        )
        if hospital_id_resp.status_code != 200:
            print(f"Ошибка получения id: {hospital_id_resp.text}")
            return
        hospital_connection_id = hospital_id_resp.json()['results'][0]['connection_id']
        print(f"Id соедиения больницы: {hospital_connection_id}")
        #req_resp = requests.post(
        #    f"{self.hospital_admin}/connections/{hospital_connection_id}/accept-request",
        #    headers=self.hospital_headers,
        #)
        #if req_resp.status_code != 200:
        #    print(f"Ошибка установки соедиения: {req_resp.text}")
        #    return
        #await asyncio.sleep(5)
        
        # ЭТАП 3: Больница выпускает медицинскую справку
        print("3. 📋 Больница выпускает медицинскую справку...")
        credential_offer = {
            "connection_id": hospital_connection_id,
            "credential_preview": {
                "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview",
                "attributes": [
                    {"name": "full_name", "value": "Иванов Иван Иванович"},
                    {"name": "date_of_birth", "value": "1985-05-15"},
                    {"name": "blood_group_rh", "value": "A+"},
                    {"name": "severe_allergies", "value": json.dumps(["Пенициллин"])},
                    {"name": "chronic_diagnoses", "value": json.dumps(["Гипертензия"])}
                ]
            },
            "cred_def_id": "M2yeapcDR9P7pi7mETjBui:3:CL:20:default"  # Должен быть реальный ID
        }
        
        issue_resp = requests.post(
            f"{self.hospital_admin}/issue-credential/send-offer",
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
            "proof_request": {
                "name": "EMERGENCY: Blood Type Request",
                "version": "1.0",
                "requested_attributes": {
                    "blood_attr": {
                        "name": "blood_group_rh",
                        "restrictions": [{"cred_def_id": "M2yeapcDR9P7pi7mETjBui:3:CL:20:default"}]
                    }
                },
                "requested_predicates":{}
            }
        }
        
        proof_resp = requests.post(
            f"{self.hospital_admin}/present-proof/send-request",
            headers=self.hospital_headers,
            json=emergency_request
        )
        
        if proof_resp.status_code == 200:
            print("   ✅ Экстренный запрос отправлен. Система пациента должна автоматически ответить.")
            
            # Проверяем статус через 3 секунды
            await asyncio.sleep(5)
            pres_ex_id = proof_resp.json()['presentation_exchange_id']
            print(f"ID презентации: {pres_ex_id}")
            status_resp = requests.get(
                f"{self.hospital_admin}/present-proof/records/{pres_ex_id}",
                headers=self.hospital_headers
            )
            if status_resp.status_code != 200:
                print(f"Ошибка запроса верификации! {status_resp.text}")
                return
            if status_resp.json()['state'] == 'verified':
                print("   🩺 Данные верифицированы! Врач получил группу крови пациента.")
                revealed_attrs = status_resp.json().get('revealed_attrs', {})
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
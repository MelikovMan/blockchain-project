"""
ПОЛНЫЙ СЦЕНАРИЙ С ХРАНЕНИЕМ ССЫЛОК В VC
"""
import asyncio
import requests
import json
import time

class VCStorageScenario:
    
    def __init__(self):
        self.hospital_admin = "http://localhost:8021"
        self.patient_admin = "http://localhost:8031"
        self.regulator_admin = "http://localhost:8041"
        self.hospital_controller = "http://localhost:8050"
        self.patient_controller = "http://localhost:8060"
        
        self.headers = {
            "hospital": {"X-API-Key": "super-secret-admin-api-key-123"},
            "patient": {"X-API-Key": "patient-admin-key-456"},
            "regulator": {"X-API-Key": "regulator-admin-key-789"}
        }
    
    async def run_scenario(self):
        """Запуск сценария с хранением ссылок в VC"""
        
        print("\n" + "="*60)
        print("🎯 СЦЕНАРИЙ: Хранение blockchain-ссылок в VC пациента")
        print("="*60)
        
        # ЭТАП 1: Установление соединения
        print("\n1. 🤝 Установление соединения больница-пациент...")
        
        invitation_resp = requests.post(
            f"{self.hospital_admin}/connections/create-invitation",
            headers=self.headers["hospital"],
            json={"auto_accept": True}
        )
        
        invitation = invitation_resp.json()['invitation']
        
        # Пациент принимает приглашение
        receive_resp = requests.post(
            f"{self.patient_admin}/connections/receive-invitation",
            headers=self.headers["patient"],
            json={"invitation": invitation}
        )
        
        connection_id = receive_resp.json()['connection_id']
        print(f"   ✅ Соединение установлено: {connection_id}")
        
        await asyncio.sleep(2)
        
        # ЭТАП 2: Выпуск VC с blockchain-ссылками в атрибутах
        print("\n2. 🏥 Выпуск медицинской справки со встроенными ссылками...")
        
        issue_data = {
            "patient_id": "patient_123",
            "connection_id": connection_id
        }
        
        issue_response = requests.post(
            f"{self.hospital_controller}/issue-credential",
            json=issue_data
        )
        
        if issue_response.status_code == 200:
            issue_result = issue_response.json()
            print(f"   ✅ VC выпущен успешно!")
            print(f"   📊 Exchange ID: {issue_result.get('credential_exchange_id')}")
            print(f"   💡 Примечание: Все ссылки сохранены в атрибутах VC")
        else:
            print(f"   ❌ Ошибка: {issue_response.text}")
            return
        
        await asyncio.sleep(3)
        
        # ЭТАП 3: Проверка, что VC сохранен у пациента
        print("\n3. 👤 Проверка VC в кошельке пациента...")
        
        credentials_resp = requests.get(
            f"{self.patient_controller}/credentials",
            headers=self.headers["patient"]
        )
        
        if credentials_resp.status_code == 200:
            credentials = credentials_resp.json()
            if credentials:
                print(f"   ✅ Найдено VC в кошельке: {len(credentials)}")
                
                # Показываем атрибуты первого VC
                if credentials:
                    cred = credentials[0]
                    attrs = cred.get('attrs', {})
                    
                    print(f"   📋 Основные данные:")
                    print(f"      • ФИО: {attrs.get('full_name')}")
                    print(f"      • Группа крови: {attrs.get('blood_group_rh')}")
                    
                    print(f"   🔗 Blockchain-ссылки в атрибутах:")
                    if attrs.get('_hospital_endpoint'):
                        print(f"      • Эндпоинт больницы: {attrs.get('_hospital_endpoint')}")
                    if attrs.get('_blockchain_ref'):
                        print(f"      • Blockchain ссылка: присутствует")
                    if attrs.get('_hospital_did'):
                        print(f"      • DID больницы: {attrs.get('_hospital_did')}")
            else:
                print(f"   ⚠️  VC не найден в кошельке")
        else:
            print(f"   ❌ Ошибка получения VC: {credentials_resp.status_code}")
        
        await asyncio.sleep(2)
        
        # ЭТАП 4: Верификация VC через ссылку в атрибутах
        print("\n4. 🔍 Верификация VC через ссылку из атрибутов...")
        
        if credentials:
            credential_id = credentials[0].get('credential_id')
            
            verify_data = {
                "credential_id": credential_id,
                "verifier_did": "did:sov:verifier_123"
            }
            
            verify_response = requests.post(
                f"{self.patient_controller}/credential/{credential_id}/verify",
                json=verify_data
            )
            
            if verify_response.status_code == 200:
                verify_result = verify_response.json()
                print(f"   ✅ Запрос на верификацию отправлен")
                print(f"   📤 Эндпоинт: {verify_result.get('hospital_endpoint')}")
            else:
                print(f"   ❌ Ошибка верификации: {verify_response.text}")
        
        await asyncio.sleep(2)
        
        # ЭТАП 5: Экстренный доступ
        print("\n5. 🚨 Тест экстренного доступа...")
        
        # Пациент активирует экстренный режим
        emergency_resp = requests.post(
            f"{self.patient_controller}/emergency/enable",
            headers=self.headers["patient"]
        )
        
        if emergency_resp.status_code == 200:
            emergency_result = emergency_resp.json()
            print(f"   ✅ Экстренный режим активирован")
            print(f"   ⏰ Действует до: {time.ctime(emergency_result.get('expires_at'))}")
            print(f"   📋 Разрешенные данные: {emergency_result.get('scope')}")
        
        # Симулируем запрос от врача скорой помощи
        print("\n6. 🩺 Врач скорой помощи запрашивает экстренные данные...")
        
        emergency_verify_data = {
            "patient_name": "Иванов Иван Иванович",
            "date_of_birth": "1985-05-15",
            "emergency_code": "EMERGENCY-ACCESS-2024"
        }
        
        doctor_response = requests.post(
            f"{self.hospital_controller}/emergency-verify",
            json=emergency_verify_data
        )
        
        if doctor_response.status_code == 200:
            doctor_result = doctor_response.json()
            if doctor_result.get('emergency'):
                print(f"   ✅ Экстренные данные предоставлены врачу!")
                patients = doctor_result.get('patients', [])
                if patients:
                    print(f"   🩸 Группа крови: {patients[0].get('blood_group_rh')}")
                    print(f"   ⚠️  Аллергии: {patients[0].get('severe_allergies')}")
        else:
            print(f"   ❌ Ошибка экстренного доступа: {doctor_response.text}")
        
        await asyncio.sleep(2)
        
        # ЭТАП 6: Отключение экстренного режима
        print("\n7. 🔒 Отключение экстренного режима...")
        
        disable_resp = requests.post(
            f"{self.patient_controller}/emergency/disable",
            headers=self.headers["patient"]
        )
        
        if disable_resp.status_code == 200:
            print(f"   ✅ Экстренный режим отключен")
        
        print("\n" + "="*60)
        print("🎯 СЦЕНАРИЙ ЗАВЕРШЕН!")
        print("="*60)
        
        print("\n📋 ИТОГИ РЕАЛИЗАЦИИ:")
        print("   ✅ Blockchain-ссылки хранятся в атрибутах VC")
        print("   ✅ Пациент имеет полный контроль через свой кошелек")
        print("   ✅ Эндпоинты для верификации встроены в VC")
        print("   ✅ Реализован экстренный доступ с контролем пациента")
        print("   ✅ Нет отдельной базы данных для хранения ссылок")

# Запуск сценария
if __name__ == "__main__":
    scenario = VCStorageScenario()
    asyncio.run(scenario.run_scenario())
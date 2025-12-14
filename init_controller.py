"""
Скрипт первоначальной настройки агента регулятора.
Запускать один раз перед первым использованием.
"""
import requests
import json
import time

def initialize_regulator():
    """Инициализация публичного DID регулятора в сети"""
    
    print("⚙️  Инициализация государственного регулятора...")
    
    # Конфигурация
    admin_url = "http://localhost:8041"
    api_key = "regulator-admin-key-789"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # 1. Проверка доступности агента
    print("1. Проверка доступности агента...")
    try:
        response = requests.get(f"{admin_url}/status/ready", headers=headers, timeout=10)
        if response.status_code == 200:
            print("   ✅ Агент доступен")
        else:
            print(f"   ❌ Агент не отвечает: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False
    
    # 2. Проверка публичного DID
    print("2. Проверка публичного DID регулятора...")
    try:
        response = requests.get(f"{admin_url}/wallet/did/public", headers=headers)
        if response.status_code == 200:
            public_did = response.json().get("result", {}).get("did")
            if public_did:
                print(f"   ✅ Публичный DID найден: {public_did}")
                return True
            else:
                print("   ℹ️  Публичный DID не найден, создаем...")
        else:
            print(f"   ℹ️  Ответ сервера: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # 3. Создание публичного DID
    print("3. Создание публичного DID для регулятора...")
    try:
        did_body = {
            "method": "sov",
            "options": {
                "key_type": "ed25519"
            }
        }
        
        response = requests.post(
            f"{admin_url}/wallet/did/create",
            headers=headers,
            json=did_body
        )
        
        if response.status_code == 200:
            result = response.json()
            new_did = result.get("result", {}).get("did")
            print(f"   ✅ Создан новый DID: {new_did}")
            
            # 4. Публикация DID в реестре
            print("4. Публикация DID в сети Indy...")
            time.sleep(2)  # Ждем инициализации кошелька
            
            publish_body = {
                "did": new_did
            }
            
            publish_response = requests.post(
                f"{admin_url}/ledger/register-nym",
                headers=headers,
                json=publish_body
            )
            
            if publish_response.status_code == 200:
                print("   ✅ DID опубликован в реестре")
                print("\n🎉 Инициализация регулятора завершена успешно!")
                print(f"   📋 Публичный DID: {new_did}")
                print(f"   🔗 Роль: ENDORSER (может подписывать транзакции)")
                return True
            else:
                print(f"   ❌ Ошибка публикации: {publish_response.text}")
                return False
        else:
            print(f"   ❌ Ошибка создания DID: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return False

if __name__ == "__main__":
    success = initialize_regulator()
    if not success:
        print("\n⚠️  Инициализация не удалась. Проверьте:")
        print("   1. Запущен ли агент регулятора?")
        print("   2. Доступна ли сеть Indy (von-network)?")
        print("   3. Правильны ли параметры подключения?")
        exit(1)
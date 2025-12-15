import requests
import json
import logging
import time
from flask import Flask, request, jsonify
from typing import Dict, List, Optional, Union

app = Flask(__name__)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8021"
AGENT_API_KEY = "super-secret-admin-api-key-123"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}
REGULATOR_URL = "http://localhost:8070"

# Упрощенное "хранилище" данных пациента
MEDICAL_RECORDS = {
    "patient_123": {
        "full_name": "Иванов Иван Иванович",
        "date_of_birth": "1985-05-15",
        "blood_group_rh": "A+",
        "severe_allergies": ["Пенициллин"],
        "chronic_diagnoses": ["Артериальная гипертензия, контролируемая"]
    }
}

# Хранилище разрешенных схем
APPROVED_SCHEMAS = []
PENDING_SCHEMA_REQUESTS = []
HOSPITAL_DID = None
HOSPITAL_ENDPOINT = "http://localhost:8050"  # Контроллер больницы

def get_hospital_did() -> Optional[str]:
    """Получаем публичный DID больницы"""
    try:
        resp = requests.get(f"{AGENT_ADMIN_URL}/wallet/did/public", headers=HEADERS)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("did")
    except Exception as e:
        logging.error(f"Ошибка получения DID больницы: {e}")
    return None

def create_blockchain_reference(schema_data: Dict, cred_def_id: str) -> Dict:
    """Создание blockchain-ссылки для хранения в атрибутах VC"""
    return {
        "schema_id": f"{HOSPITAL_DID}:2:{schema_data['schema_name']}:{schema_data['schema_version']}",
        "cred_def_id": cred_def_id,
        "hospital_did": HOSPITAL_DID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verification_method": f"{HOSPITAL_DID}#key-1",
        "blockchain_network": "indy:sovrin:staging"
    }

def issue_credential_with_references(
    connection_id: str,
    patient_data: Dict,
    schema_data: Dict,
    cred_def_id: str
) -> Union[Dict,None]:
    """Выпуск VC с blockchain-ссылками в атрибутах"""
    
    # Создаем blockchain-ссылку
    blockchain_ref = create_blockchain_reference(schema_data, cred_def_id)
    
    # Формируем атрибуты VC
    attributes = [
        {"name": "full_name", "value": patient_data["full_name"]},
        {"name": "date_of_birth", "value": patient_data["date_of_birth"]},
        {"name": "blood_group_rh", "value": patient_data["blood_group_rh"]},
        {"name": "severe_allergies", "value": json.dumps(patient_data["severe_allergies"], ensure_ascii=False)},
        {"name": "chronic_diagnoses", "value": json.dumps(patient_data["chronic_diagnoses"], ensure_ascii=False)},
        
        # Метаданные и ссылки храним в атрибутах с префиксом _
        {"name": "_hospital_did", "value": HOSPITAL_DID},
        {"name": "_hospital_name", "value": "Городская Больница №1"},
        {"name": "_hospital_endpoint", "value": f"{HOSPITAL_ENDPOINT}/verify-credential"},
        {"name": "_document_type", "value": "Медицинская справка"},
        {"name": "_document_id", "value": f"MED-{int(time.time())}"},
        {"name": "_issuer_name", "value": "Городская Больница №1"},
        {"name": "_issued_date", "value": time.strftime("%Y-%m-%d")},
        {"name": "_expires_date", "value": "2025-12-31"},  # Срок действия
        {"name": "_blockchain_ref", "value": json.dumps(blockchain_ref, ensure_ascii=False)},
        {"name": "_verification_url", "value": f"{HOSPITAL_ENDPOINT}/verify/{{credential_id}}"},
        {"name": "_emergency_access", "value": "true"}  # Разрешение на экстренный доступ
    ]
    
    # Формируем предложение credential
    credential_offer = {
        "connection_id": connection_id,
        "credential_preview": {
            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview",
            "attributes": attributes
        },
        "cred_def_id": cred_def_id,
        "auto_issue": True,
        "trace": False
    }
    
    # Отправляем предложение
    response = requests.post(
        f"{AGENT_ADMIN_URL}/issue-credential/send-offer",
        headers=HEADERS,
        json=credential_offer
    )
    
    return response.json() if response.status_code == 200 else None


def request_schema_approval(schema_data: Dict) -> bool:
    """
    Отправляем запрос регулятору на проверку возможности выпускать credential
    Требование 3: Перед регистрацией VC больница отправляет запрос регулятору
    """
    try:
        payload = {
            "hospital_did": HOSPITAL_DID,
            "schema_name": schema_data["schema_name"],
            "schema_version": schema_data["schema_version"],
            "attributes": schema_data["attributes"],
            "purpose": "Новая медицинская справка"
        }
        
        response = requests.post(
            f"{REGULATOR_URL}/approve-schema",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("approved"):
                logging.info(f"Схема {schema_data['schema_name']} одобрена регулятором")
                return True
            else:
                logging.warning(f"Схема отклонена: {result.get('reason')}")
                PENDING_SCHEMA_REQUESTS.append({
                    "schema": schema_data,
                    "status": "rejected",
                    "reason": result.get("reason")
                })
        return False
        
    except Exception as e:
        logging.error(f"Ошибка запроса к регулятору: {e}")
        return False

def request_schema_modification(new_schemas: List[Dict]) -> bool:
    """
    Требование 4: Запрос регулятору на изменение списка выпускаемых VC
    """
    try:
        payload = {
            "hospital_did": HOSPITAL_DID,
            "current_schemas": APPROVED_SCHEMAS,
            "requested_changes": new_schemas,
            "justification": "Расширение медицинских услуг"
        }
        
        response = requests.post(
            f"{REGULATOR_URL}/modify-schemas",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("approved"):
                APPROVED_SCHEMAS.extend(new_schemas)
                logging.info(f"Изменения схем одобрены: {new_schemas}")
                return True
        return False
        
    except Exception as e:
        logging.error(f"Ошибка запроса модификации схем: {e}")
        return False
@app.route('/issue-credential', methods=['POST'])
def issue_medical_credential():
    """Выпуск медицинского документа с blockchain-ссылками в атрибутах"""
    global HOSPITAL_DID
    
    # Получаем DID больницы если еще не получен
    if not HOSPITAL_DID:
        HOSPITAL_DID = get_hospital_did()
    
    patient_id = request.json.get("patient_id")
    connection_id = request.json.get("connection_id")
    
    if patient_id not in MEDICAL_RECORDS:
        return jsonify({"error": "Пациент не найден"}), 404
    
    # Проверяем наличие одобренных схем
    if not APPROVED_SCHEMAS:
        return jsonify({"error": "Нет одобренных схем. Запросите одобрение у регулятора."}), 400
    
    patient_data = MEDICAL_RECORDS[patient_id]
    schema_data = APPROVED_SCHEMAS[0]  # Используем первую одобренную схему
    
    # Создаем credential definition (в реальности это было бы заранее создано)
    cred_def_id = create_credential_definition(schema_data)
    if not cred_def_id:
        return jsonify({"error": "Не удалось создать credential definition"}), 500
    
    # Выпускаем VC с blockchain-ссылками
    result = issue_credential_with_references(
        connection_id, 
        patient_data, 
        schema_data, 
        cred_def_id
    )
    
    if not result:
        return jsonify({"error": "Не удалось выпустить медицинскую справку"}), 500
    
    return jsonify({
        "status": "success",
        "message": "Медицинская справка выпущена. Blockchain-ссылки сохранены в атрибутах VC.",
        "credential_exchange_id": result.get("credential_exchange_id"),
        "patient_id": patient_id,
        "hospital_did": HOSPITAL_DID,
        "note": "Все ссылки и метаданные хранятся в атрибутах VC в кошельке пациента"
    }), 200

def create_credential_definition(schema_data: Dict) -> Optional[str]:
    """Создание credential definition для схемы"""
    try:
        # Сначала создаем схему
        schema_body = {
            "schema_name": schema_data["schema_name"],
            "schema_version": schema_data["schema_version"],
            "attributes": schema_data["attributes"]
        }
        
        schema_resp = requests.post(
            f"{AGENT_ADMIN_URL}/schemas",
            headers=HEADERS,
            json=schema_body
        )
        
        if schema_resp.status_code != 200:
            logging.error(f"Ошибка создания схемы: {schema_resp.text}")
            return None
        
        schema_id = schema_resp.json()["schema_id"]
        
        # Создаем credential definition
        cred_def_body = {
            "schema_id": schema_id,
            "support_revocation": False,
            "tag": "hospital_default"
        }
        
        cred_def_resp = requests.post(
            f"{AGENT_ADMIN_URL}/credential-definitions",
            headers=HEADERS,
            json=cred_def_body
        )
        
        if cred_def_resp.status_code == 200:
            return cred_def_resp.json()["credential_definition_id"]
        
    except Exception as e:
        logging.error(f"Ошибка создания cred def: {e}")
    
    return None

@app.route('/verify-credential', methods=['POST'])
def verify_patient_credential():
    """Верификация credential пациента по запросу"""
    data = request.json
    credential_id = data.get("credential_id")
    verifier_did = data.get("verifier_did")
    
    # В реальной системе здесь была бы проверка credential
    # через blockchain или внутреннюю базу данных
    
    return jsonify({
        "verified": True,
        "credential_id": credential_id,
        "hospital_did": HOSPITAL_DID,
        "verification_date": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "VALID",
        "message": "Credential верифицирован больницей"
    }), 200

@app.route('/emergency-verify', methods=['POST'])
def emergency_verify():
    """Экстренная верификация для врачей скорой помощи"""
    data = request.json
    patient_name = data.get("patient_name")
    date_of_birth = data.get("date_of_birth")
    emergency_code = data.get("emergency_code")
    
    # Проверяем emergency code (в реальности это был бы токен или подпись)
    if emergency_code != "EMERGENCY-ACCESS-2024":
        return jsonify({"error": "Неверный код экстренного доступа"}), 403
    
    # Ищем пациента
    found_patients = []
    for pid, pdata in MEDICAL_RECORDS.items():
        if (pdata["full_name"] == patient_name and 
            pdata["date_of_birth"] == date_of_birth):
            found_patients.append({
                "patient_id": pid,
                **pdata
            })
    
    if not found_patients:
        return jsonify({"error": "Пациент не найден"}), 404
    
    # Возвращаем только критические данные для экстренного случая
    return jsonify({
        "emergency": True,
        "patients": [{
            "full_name": p["full_name"],
            "date_of_birth": p["date_of_birth"],
            "blood_group_rh": p["blood_group_rh"],
            "severe_allergies": p["severe_allergies"],
            "verification_source": HOSPITAL_DID,
            "verified_at": time.time()
        } for p in found_patients]
    }), 200

@app.route('/webhooks/topic/<topic>', methods=['POST'])
def handle_hospital_webhooks(topic: str):
    """Обработка вебхуков больницы"""
    message = request.json
    logging.info(f"[Hospital Webhook] Topic: {topic}")
    
    if topic == 'endorsements':
        # Обработка транзакций от регулятора
        handle_endorsement_webhook(message)
    
    return jsonify({"status": "processed"}), 200

def handle_endorsement_webhook(message: Dict):
    """Обработка вебхуков о подписи транзакций"""
    state = message.get('state')
    
    if state == 'request-received':
        transaction_id = message.get('transaction_id')
        # Здесь можно добавить логику проверки транзакции
        # перед тем как подписать
        
        # Автоматически подписываем транзакцию
        if transaction_id:
            requests.post(
                f"{AGENT_ADMIN_URL}/endorse-transaction/{transaction_id}",
                headers=HEADERS,
                json={}
            )

# Существующие эндпоинты для работы с регулятором остаются
@app.route('/init-schema', methods=['POST'])
def initialize_schema():
    """
    Инициализация новой схемы с запросом одобрения у регулятора
    """
    global HOSPITAL_DID
    HOSPITAL_DID = get_hospital_did()
    
    if not HOSPITAL_DID:
        return jsonify({"error": "Не удалось получить DID больницы"}), 500
    
    schema_data = request.json
    
    # Проверяем на одобрение у регулятора
    if request_schema_approval(schema_data):
        APPROVED_SCHEMAS.append(schema_data)
        return jsonify({
            "status": "approved",
            "message": "Схема одобрена регулятором",
            "schema": schema_data
        }), 200
    else:
        return jsonify({
            "status": "pending",
            "message": "Схема ожидает одобрения регулятора"
        }), 202

@app.route('/request-schema-change', methods=['POST'])
def request_schema_change():
    """
    Запрос на изменение списка схем
    """
    new_schemas = request.json.get("schemas", [])
    
    if request_schema_modification(new_schemas):
        return jsonify({
            "status": "approved",
            "message": "Изменения схем одобрены",
            "approved_schemas": APPROVED_SCHEMAS
        }), 200
    else:
        return jsonify({
            "status": "rejected",
            "message": "Изменения не одобрены"
        }), 403


if __name__ == '__main__':
    # Получаем DID больницы при старте
    HOSPITAL_DID = get_hospital_did()
    if HOSPITAL_DID:
        print(f"[INFO] DID больницы: {HOSPITAL_DID}")
        print(f"[INFO] Эндпоинт для верификации: {HOSPITAL_ENDPOINT}/verify-credential")
    else:
        print("[WARN] Не удалось получить DID больницы")
    
    print("[INFO] Blockchain-ссылки теперь хранятся в атрибутах VC у пациента")
    app.run(port=8050, debug=True)
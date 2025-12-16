import requests
import json
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8021"
AGENT_API_KEY = "super-secret-admin-api-key-123"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# Упрощенное "хранилище" данных пациента (в реальности - подключение к БД ЛПУ)
MEDICAL_RECORDS = {
    "patient_123": {
        "full_name": "Иванов Иван Иванович",
        "date_of_birth": "1985-05-15",
        "blood_group_rh": "A+",
        "severe_allergies": ["Пенициллин"],
        "chronic_diagnoses": ["Артериальная гипертензия, контролируемая"]
    }
}

def create_schema_and_cred_def():
    """
    Шаг 1: Регистрация схемы и определения учетных данных в блокчейне.
    Выполняется один раз при инициализации системы.
    """
    
    schema_body = {
        "schema_name": "HospitalMedicalRecord",
        "schema_version": "1.0.0",
        "attributes": [
            "full_name",
            "date_of_birth",
            "blood_group_rh",
            "severe_allergies",
            "chronic_diagnoses"
        ]
    }
    # 1. Проверка существования схемы
    schema_find = requests.get(f"{AGENT_ADMIN_URL}/schemas/created?schema_name=HospitalMedicalRecord",headers=HEADERS)
    if schema_find:
        print("Схема уже существует")
        schema_result = schema_find.json()
        schema_id = schema_result["schema_ids"][0]
    else:
        # 1. Создание схемы
        schema_resp = requests.post(f"{AGENT_ADMIN_URL}/schemas", headers=HEADERS, json=schema_body)
        if schema_resp.status_code != 200:
            logging.error(f"Ошибка создания схемы: {schema_resp.text}")
            return None

        schema_result = schema_resp.json()
        schema_id = schema_result["schema_id"]
    # 1. Проверка существования схемы кредов
    cred_def_find = requests.get(f"{AGENT_ADMIN_URL}/credential-definitions/created?=schema_name=HospitalMedicalRecord", headers=HEADERS)
    if cred_def_find:
        print("Определение VC уже существует")
        cred_result = cred_def_find.json()
        return cred_result["credential_definition_ids"][0]

    # 2. Создание определения учетных данных на основе схемы
    cred_def_body = {
        "schema_id": schema_id,
        "support_revocation": False,
        "tag": "default"
    }
    cred_def_resp = requests.post(f"{AGENT_ADMIN_URL}/credential-definitions", headers=HEADERS, json=cred_def_body)
    if cred_def_resp.status_code != 200:
        logging.error(f"Ошибка создания cred def: {cred_def_resp.text}")
        return None

    return cred_def_resp.json()["credential_definition_id"]

@app.route('/issue-credential', methods=['POST'])
def issue_medical_credential():
    """
    Шаг 2: Выпуск верифицируемой медицинской справки для пациента.
    Эндпоинт, который может вызываться из внутренней системы больницы.
    """
    # 1. Получаем данные пациента из запроса (например, из EHR системы)
    patient_id = request.json.get("patient_id")
    connection_id = request.json.get("connection_id") # ID установленного соединения с агентом пациента

    if patient_id not in MEDICAL_RECORDS:
        return jsonify({"error": "Пациент не найден"}), 404

    patient_data = MEDICAL_RECORDS[patient_id]

    # 2. Формируем предложение учетных данных для агента пациента
    credential_offer = {
        "connection_id": connection_id,
        "credential_preview": {
            "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview",
            "attributes": [
                {"name": "full_name", "value": patient_data["full_name"]},
                {"name": "date_of_birth", "value": patient_data["date_of_birth"]},
                {"name": "blood_group_rh", "value": patient_data["blood_group_rh"]},
                {"name": "severe_allergies", "value": json.dumps(patient_data["severe_allergies"], ensure_ascii=False)},
                {"name": "chronic_diagnoses", "value": json.dumps(patient_data["chronic_diagnoses"], ensure_ascii=False)}
            ]
        },
        "cred_def_id": CRED_DEF_ID # ID, полученный при создании cred def
    }

    # 3. Отправляем предложение агенту через административный API
    issue_resp = requests.post(f"{AGENT_ADMIN_URL}/issue-credential/send-offer", headers=HEADERS, json=credential_offer)

    if issue_resp.status_code != 200:
        logging.error(f"Ошибка отправки оффера: {issue_resp.text}")
        return jsonify({"error": "Не удалось выпустить справку"}), 500

    return jsonify(issue_resp.json()), 200

@app.route('/verify-proof', methods=['POST'])
def verify_emergency_proof():
    """
    Шаг 3: Верификация доказательства от пациента (например, для экстренного доступа).
    Поликлиника или приемный покой запрашивает конкретные данные.
    """
    # 1. Получаем ID соединения с агентом, который представляет доказательство (например, родственника или врача скорой)
    verifier_connection_id = request.json.get("verifier_connection_id")

    # 2. Формируем запрос на доказательство (Proof Request)
    proof_request = {
        "connection_id": verifier_connection_id,
        "proof_request": {
            "name": "Emergency Medical Data Request",
            "version": "1.0",
            "requested_attributes": {
                "blood_group_attr": {
                    "name": "blood_group_rh",
                    "restrictions": [{"cred_def_id": CRED_DEF_ID}] # Требуем данные, выпущенные НАШЕЙ больницей
                }
            },
            # Можем добавить запрос предикатов (например, age > 18)
            "requested_predicates": {}
        }
    }

    # 3. Отправляем запрос на доказательство
    proof_resp = requests.post(f"{AGENT_ADMIN_URL}/present-proof/send-request", headers=HEADERS, json=proof_request)

    if proof_resp.status_code != 200:
        return jsonify({"error": "Не удалось отправить запрос на верификацию"}), 500

    # 4. Ответ содержит идентификатор презентации, статус которой нужно проверять асинхронно
    presentation_exchange_id = proof_resp.json()["presentation_exchange_id"]
    return jsonify({"presentation_exchange_id": presentation_exchange_id}), 200

# Глобальная переменная для ID определения учетных данных
CRED_DEF_ID = None

if __name__ == '__main__':
    # При старте регистрируем схему в блокчейне (в продакшене это делается отдельно)
    CRED_DEF_ID = create_schema_and_cred_def()
    if CRED_DEF_ID:
        print(f"[INFO] Cred Def ID зарегистрирован: {CRED_DEF_ID}")
        app.run(port=8050, debug=True)
    else:
        print("[ERROR] Не удалось инициализировать агента. Проверьте сеть Indy.")
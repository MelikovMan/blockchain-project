import requests
import json
import logging
from flask import Flask, request, jsonify
import os

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8021"
AGENT_API_KEY = "super-secret-admin-api-key-123"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}
DID_SEED = "very_strong_hospital_seed0000000"

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

CREDENTIAL_EXCHANGES = {}
def generate_and_publish_did():
    local_did = requests.post(f"{AGENT_ADMIN_URL}/wallet/did/create",headers=HEADERS,json={
  "method": "sov",
  "options": {
    "key_type": "ed25519"
  },
  "seed": DID_SEED
    })
    if local_did.status_code != 200:
        print(f"Ошибка создания did: {local_did.text}")
        return False
    got_did=local_did.json()["result"]["did"]
    publish_did=requests.post(f"{AGENT_ADMIN_URL}/wallet/did/public?did={got_did}",headers=HEADERS)
    if publish_did.status_code != 200:
        print(f"Ошибка связывания с публичным DiD")
        return False
    return True
def create_schema_and_cred_def():
    """
    Шаг 1: Регистрация схемы и определения учетных данных в блокчейне.
    Выполняется один раз при инициализации системы.
    """
    
    schema_body = {
        "schema_name": "HospitalMedicalRecord66",
        "schema_version": "1.0.5",
        "attributes": [
            "full_name",
            "date_of_birth",
            "blood_group_rh",
            "severe_allergies",
            "chronic_diagnoses"
        ]
    }
    # 1. Проверка существования схемы
    schema_find = requests.get(f"{AGENT_ADMIN_URL}/schemas/created?schema_name=HospitalMedicalRecord66",headers=HEADERS)
    if schema_find.json()["schema_ids"]:
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
    cred_def_find = requests.get(f"{AGENT_ADMIN_URL}/credential-definitions/created?=schema_name=HospitalMedicalRecord66", headers=HEADERS)
    if cred_def_find.json()["credential_definition_ids"]:
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
def handle_connection_webhook(message):
    """Обработка вебхуков соединений"""
    state = message.get('state')
    connection_id = message.get('connection_id')
    their_label = message.get('their_label', 'Неизвестный')
    
    if state == 'invitation':
        logging.info(f"📨 Создано приглашение для соединения: {connection_id}")
    
    elif state == 'request':
        logging.info(f"📥 Получен запрос на соединение от: {their_label}, ID: {connection_id}")
        # Автоматически принимаем запрос на соединение с использованием DID Exchange
        try:
            accept_response = requests.post(
                f"{AGENT_ADMIN_URL}/didexchange/{connection_id}/accept-request",
                headers=HEADERS,
                json={}
            )
            if accept_response.status_code == 200:
                logging.info(f"✅ Запрос на соединение принят: {connection_id}")
            else:
                logging.error(f"❌ Ошибка принятия запроса: {accept_response.text}")
        except Exception as e:
            logging.error(f"❌ Ошибка при принятии запроса: {e}")
    
    elif state == 'response':
        logging.info(f"✅ Соединение установлено с: {their_label}, ID: {connection_id}")
        # Можно добавить логику для автоматического выпуска справки после установления соединения
    
    elif state == 'completed':
        logging.info(f"🏁 Соединение завершено: {connection_id}")
    
    elif state == 'active':
        logging.info(f"🟢 Соединение активно: {connection_id}")
        # Когда соединение становится активным, можно автоматически выпускать справку
        #if their_label and "Patient" in their_label:
            # Это пример - в реальности нужно получить patient_id из метаданных
            #auto_issue_credential(connection_id, "patient_123")
    
    elif state == 'abandoned' or state == 'error':
        logging.error(f"❌ Проблема с соединением {connection_id}: {state}, {message.get('error_msg', '')}")

def handle_issue_credential_webhook(message):
    """Обработка вебхуков выпуска учетных данных"""
    state = message.get('state')
    cred_ex_id = message.get('credential_exchange_id')
    connection_id = message.get('connection_id')
    
    # Сохраняем информацию об обмене
    if cred_ex_id not in CREDENTIAL_EXCHANGES:
        CREDENTIAL_EXCHANGES[cred_ex_id] = {}
    
    CREDENTIAL_EXCHANGES[cred_ex_id]['state'] = state
    CREDENTIAL_EXCHANGES[cred_ex_id]['connection_id'] = connection_id
    
    if state == 'proposal-received':
        logging.info(f"📋 Получено предложение учетных данных: {cred_ex_id}")
        # Можно автоматически отправить оффер в ответ
        send_credential_offer(cred_ex_id)
    
    elif state == 'offer-sent':
        logging.info(f"📤 Предложение учетных данных отправлено: {cred_ex_id}")
    
    elif state == 'request-received':
        logging.info(f"📥 Получен запрос на учетные данные: {cred_ex_id}")
        # Автоматически выпускаем учетные данные
        issue_credential(cred_ex_id)
    
    elif state == 'credential-issued':
        logging.info(f"✅ Учетные данные выпущены: {cred_ex_id}")
        # Обновляем статус в нашей системе
        update_credential_status(cred_ex_id, 'issued')
    
    elif state == 'credential-acked':
        logging.info(f"🎉 Учетные данные подтверждены пациентом: {cred_ex_id}")
        # Справка успешно доставлена и сохранена
        update_credential_status(cred_ex_id, 'delivered')
    
    elif state == 'done':
        logging.info(f"🏁 Процесс выпуска завершен: {cred_ex_id}")
        # Очищаем запись после завершения
        if cred_ex_id in CREDENTIAL_EXCHANGES:
            del CREDENTIAL_EXCHANGES[cred_ex_id]
    
    elif state == 'abandoned' or state == 'error':
        error_msg = message.get('error_msg', '')
        logging.error(f"❌ Ошибка в процессе выпуска {cred_ex_id}: {state}, {error_msg}")
        update_credential_status(cred_ex_id, 'failed')

def handle_present_proof_webhook(message):
    """Обработка вебхуков верификации доказательств"""
    state = message.get('state')
    pres_ex_id = message.get('pres_ex_id')
    connection_id = message.get('connection_id', '')
    if state == 'request-sent':
        logging.info(f"📤 Запрос на доказательство отправлен: {pres_ex_id}")
    
    elif state == 'presentation-received':
        logging.info(f"📥 Получено доказательство: {pres_ex_id}")
        # Можно автоматически верифицировать
        verify_presentation(pres_ex_id)
    
    elif state == 'done':
        logging.info(f"✅ Доказательство верифицировано: {pres_ex_id}")
        # Извлекаем раскрытые атрибуты
        logging.info(message)
        try:
            detail_resp = requests.get(
                f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}",
                headers=HEADERS
            )
            
            if detail_resp.status_code == 200:
                presentation_details = detail_resp.json()["by_format"]["pres"]["indy"]
                
                # Теперь извлекаем revealed_attrs из деталей
                proof = presentation_details.get('requested_proof', {})
                revealed_attrs = proof.get("revealed_attrs")
                logging.info(presentation_details)
                if revealed_attrs:
                    logging.info(f"📊 Раскрытые данные: {json.dumps(revealed_attrs, indent=2)}")
                    # Сохраняем в журнал доступа
                    log_access_request(pres_ex_id, revealed_attrs)
                    
                    # Обрабатываем медицинские данные
                    #process_medical_data_from_presentation(pres_ex_id, revealed_attrs, connection_id)
                else:
                    logging.warning(f"⚠️ Нет раскрытых атрибутов в верифицированной презентации {pres_ex_id}")
                    
                    # Попробуем получить данные через API credentials
                    get_presentation_credentials_data(pres_ex_id, connection_id)
            else:
                logging.error(f"❌ Ошибка получения деталей презентации: {detail_resp.text}")
        except Exception as e:
            logging.error(f"❌ Исключение при обработке верифицированной презентации: {e}")
    
    elif state == 'abandoned' or state == 'error':
        logging.error(f"❌ Ошибка в процессе верификации {pres_ex_id}: {state}")

def handle_endorsement_webhook(message):
    """Обработка вебхуков одобрения транзакций регулятором"""
    logging.info(f"🏛️  Получен вебхук одобрения: {message.get('state')}")
    # В реальной системе здесь была бы логика взаимодействия с регулятором

def handle_revocation_webhook(message):
    """Обработка вебхуков отзыва учетных данных"""
    logging.info(f"🔄 Получен вебхук отзыва: {message}")
    # Логика отзыва учетных данных

def handle_basic_message_webhook(message):
    """Обработка базовых сообщений"""
    content = message.get('content', '')
    sent_time = message.get('sent_time', '')
    connection_id = message.get('connection_id', '')
    logging.info(f"💬 Базовое сообщение от {connection_id}: {content}")

def handle_problem_report_webhook(message):
    """Обработка отчетов об ошибках"""
    problem_code = message.get('problem_code', '')
    explain = message.get('explain', '')
    connection_id = message.get('connection_id', '')
    logging.error(f"🚨 Отчет об ошибке от {connection_id}: {problem_code} - {explain}")

# Вспомогательные функции
def get_presentation_credentials_data(pres_ex_id, connection_id):
    """Получает данные credentials через API для конкретной презентации"""
    try:
        # Получаем список credentials для этой презентации
        creds_resp = requests.get(
            f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/credentials",
            headers=HEADERS
        )
        
        if creds_resp.status_code == 200:
            credentials_list = creds_resp.json()
            logging.info(f"Найдено credentials для презентации {pres_ex_id}: {len(credentials_list)}")
            
            # Если есть credentials, можем получить их детали
            if credentials_list:
                for cred_data in credentials_list:
                    cred_info = cred_data.get('cred_info', {})
                    cred_attrs = cred_info.get('attrs', {})
                    
                    if cred_attrs:
                        logging.info(f"Атрибуты из credential: {json.dumps(cred_attrs, indent=2)}")
                        
                        # Извлекаем медицинские данные
                        #medical_data = extract_medical_data_from_attrs(cred_attrs)
                        
                        #if medical_data:
                            # Сохраняем данные
                            #save_medical_data_access(pres_ex_id, connection_id, medical_data)
                            #return medical_data
            
            # Если не нашли через credentials API, пробуем получить через presentation exchange
            #eturn get_presentation_exchange_data(pres_ex_id, connection_id)
        else:
            logging.error(f"Ошибка получения credentials: {creds_resp.text}")
            return None
            
    except Exception as e:
        logging.error(f"Исключение при получении данных credentials: {e}")
        return None
def send_credential_offer(cred_ex_id):
    """Отправляет оффер учетных данных в ответ на предложение"""
    try:
        response = requests.post(
            f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}/send-offer",
            headers=HEADERS,
            json={}
        )
        if response.status_code == 200:
            logging.info(f"✅ Оффер отправлен для {cred_ex_id}")
        else:
            logging.error(f"❌ Ошибка отправки оффера: {response.text}")
    except Exception as e:
        logging.error(f"❌ Исключение при отправке оффера: {e}")

def issue_credential(cred_ex_id):
    """Выпускает учетные данные"""
    try:
        response = requests.post(
            f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}/issue",
            headers=HEADERS,
            json={"comment": "Медицинская справка выпущена"}
        )
        if response.status_code == 200:
            logging.info(f"✅ Учетные данные выпущены для {cred_ex_id}")
        else:
            logging.error(f"❌ Ошибка выпуска учетных данных: {response.text}")
    except Exception as e:
        logging.error(f"❌ Исключение при выпуске учетных данных: {e}")

def verify_presentation(pres_ex_id):
    """Верифицирует полученное доказательство"""
    try:
        response = requests.post(
            f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/verify-presentation",
            headers=HEADERS,
            json={}
        )
        if response.status_code == 200:
            logging.info(f"✅ Доказательство отправлено на верификацию: {pres_ex_id}")
        else:
            logging.error(f"❌ Ошибка верификации: {response.text}")
    except Exception as e:
        logging.error(f"❌ Исключение при верификации: {e}")

def auto_issue_credential(connection_id, patient_id):
    """Автоматически выпускает справку при установлении соединения"""
    if patient_id not in MEDICAL_RECORDS:
        logging.error(f"Пациент {patient_id} не найден")
        return
    
    patient_data = MEDICAL_RECORDS[patient_id]
    
    credential_offer = {
        "connection_id": connection_id,
        "credential_preview": {
            "@type": "issue-credential/2.0/credential-preview",
            "attributes": [
                {"name": "full_name", "value": patient_data["full_name"]},
                {"name": "date_of_birth", "value": patient_data["date_of_birth"]},
                {"name": "blood_group_rh", "value": patient_data["blood_group_rh"]},
                {"name": "severe_allergies", "value": json.dumps(patient_data["severe_allergies"], ensure_ascii=False)},
                {"name": "chronic_diagnoses", "value": json.dumps(patient_data["chronic_diagnoses"], ensure_ascii=False)}
            ]
        },
        "filter": {
            "indy": {
                "cred_def_id": CRED_DEF_ID 
            }
    },
    }
    
    try:
        response = requests.post(
            f"{AGENT_ADMIN_URL}/issue-credential-2.0/send-offer",
            headers=HEADERS,
            json=credential_offer
        )
        if response.status_code == 200:
            logging.info(f"✅ Автоматически отправлен оффер справки для {patient_id}")
        else:
            logging.error(f"❌ Ошибка автоматической отправки оффера: {response.text}")
    except Exception as e:
        logging.error(f"❌ Исключение при автоматической отправке оффера: {e}")

def update_credential_status(cred_ex_id, status):
    """Обновляет статус учетных данных в системе больницы"""
    # В реальной системе здесь была бы запись в БД
    logging.info(f"📝 Обновлен статус учетных данных {cred_ex_id}: {status}")

def log_access_request(pres_ex_id, revealed_attrs):
    """Логирует запрос доступа к данным"""
    # В реальной системе здесь была бы запись в журнал аудита
    logging.info(f"🔐 Запись в журнал доступа: {pres_ex_id}, данные: {revealed_attrs}")
@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def handle_hospital_webhooks(topic):
    """
    Обработчик вебхуков для больничного агента
    """
    message = request.json
    logging.info(f"[Hospital Webhook] Топик: {topic}, Сообщение: {json.dumps(message, indent=2)}")
    
    if topic == 'connections':
        handle_connection_webhook(message)
    
    elif topic == 'issue_credential_v2_0':
        handle_issue_credential_webhook(message)
    
    elif topic == 'present_proof_v2_0':
        handle_present_proof_webhook(message)
    
    elif topic == 'endorsements':
        handle_endorsement_webhook(message)
    
    elif topic == 'revocation':
        handle_revocation_webhook(message)
    
    elif topic == 'basicmessages':
        handle_basic_message_webhook(message)
    
    elif topic == 'problem_report':
        handle_problem_report_webhook(message)
    
    return jsonify({"status": "ok"}), 200
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
            "@type": "issue-credential/2.0/credential-preview",
            "attributes": [
                {"name": "full_name", "value": patient_data["full_name"]},
                {"name": "date_of_birth", "value": patient_data["date_of_birth"]},
                {"name": "blood_group_rh", "value": patient_data["blood_group_rh"]},
                {"name": "severe_allergies", "value": json.dumps(patient_data["severe_allergies"], ensure_ascii=False)},
                {"name": "chronic_diagnoses", "value": json.dumps(patient_data["chronic_diagnoses"], ensure_ascii=False)}
            ]
        },
        "filter": {
            "indy": {
                "cred_def_id": CRED_DEF_ID 
            }
    },
    }

    # 3. Отправляем предложение агенту через административный API
    issue_resp = requests.post(f"{AGENT_ADMIN_URL}/issue-credential-2.0/send-offer", headers=HEADERS, json=credential_offer)

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
    proof_resp = requests.post(f"{AGENT_ADMIN_URL}/present-proof-2.0/send-request", headers=HEADERS, json=proof_request)

    if proof_resp.status_code != 200:
        return jsonify({"error": "Не удалось отправить запрос на верификацию"}), 500

    # 4. Ответ содержит идентификатор презентации, статус которой нужно проверять асинхронно
    presentation_exchange_id = proof_resp.json()["pres_ex_id"]
    return jsonify({"presentation_exchange_id": presentation_exchange_id}), 200
@app.route('/create-invitation', methods=['POST'])
def create_invitation():
    """
    Создание приглашения с использованием Qualified DID (did:peer:4)
    """
    # Параметры запроса
    use_did_method = request.json.get('use_did_method', 'did:peer:4')
    handshake_protocols = request.json.get('handshake_protocols', 
                                          ['"https://didcomm.org/didexchange/1.1"'])
    
    invitation_body = {
        "use_did_method": use_did_method,
        "handshake_protocols": handshake_protocols,
        "alias": "City Hospital",
        "auto_accept": True
    }
    
    # Создание OOB приглашения
    invitation_resp = requests.post(
        f"{AGENT_ADMIN_URL}/out-of-band/create-invitation",
        headers=HEADERS,
        json=invitation_body
    )
    
    if invitation_resp.status_code != 200:
        logging.error(f"Ошибка создания приглашения: {invitation_resp.text}")
        return jsonify({"error": "Не удалось создать приглашение"}), 500
    
    invitation_data = invitation_resp.json()
    return jsonify({
        "invitation": invitation_data.get("invitation"),
        "invitation_url": invitation_data.get("invitation_url"),
        "connection_id": invitation_data.get("connection_id")
    }), 200
# Глобальная переменная для ID определения учетных данных
CRED_DEF_ID = None

if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(filename='logs/hospital.log', level=logging.INFO,encoding='utf-8')
    # При старте регистрируем схему в блокчейне (в продакшене это делается отдельно)
    if (requests.get(f"{AGENT_ADMIN_URL}/wallet/did",headers=HEADERS).json()["results"] and requests.get(f"{AGENT_ADMIN_URL}/wallet/did/public",headers=HEADERS).json()["result"]):
        print("DiD найдены в кошельке")
    else:
        print("DiD не найдены в кошельке, создаем...")
        if (not generate_and_publish_did()):
            print("Ошибка создания DiD. Не удалось инициализировать агента")

    
    CRED_DEF_ID = create_schema_and_cred_def()
    if CRED_DEF_ID:
        print(f"[INFO] Cred Def ID зарегистрирован: {CRED_DEF_ID}")
        app.run(port=8050, debug=True)
    else:
        print("[ERROR] Не удалось инициализировать агента. Проверьте сеть Indy.")
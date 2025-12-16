# Обновленный импорт в regulator_controller.py
import requests
import json
import logging
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# Импорт модуля работы с БД
from db_regulator import RegulatorDatabase as db

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8041"
AGENT_API_KEY = "regulator-admin-key-789"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# Тестирование соединения с БД при старте
if not db.test_db_connection():
    logger.error("Не удалось подключиться к базе данных")
    exit(1)

# Пример обновленного эндпоинта с использованием БД
@app.route('/institutions', methods=['GET'])
def get_registered_institutions():
    """Получение списка всех зарегистрированных учреждений из БД"""
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        institutions = db.get_all_institutions(active_only=active_only)
        return jsonify(institutions), 200
    except Exception as e:
        logging.error(f"Ошибка при получении списка учреждений: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

@app.route('/register-institution', methods=['POST'])
def register_institution():
    """Регистрация медицинского учреждения с сохранением в БД"""
    try:
        data = request.json
        
        # Валидация
        required_fields = ['institution_name', 'license_number', 'institution_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
        
        # Проверка уникальности лицензии через БД
        existing_institution = db.get_institution_by_license(data['license_number'])
        if existing_institution:
            return jsonify({"error": "Учреждение с таким номером лицензии уже зарегистрировано"}), 400
        
        # Генерация уникального DID для учреждения
        institution_id = str(uuid.uuid4())
        did_seed = f"institution_{data['license_number']}_{int(time.time())}"
        
        # Регистрация DID в блокчейне (упрощенный пример)
        did_result = register_institution_did(
            seed=did_seed,
            alias=data['institution_name'],
            role="ENDORSER"
        )
        
        if not did_result:
            return jsonify({"error": "Не удалось зарегистрировать DID в блокчейне"}), 500
        
        institution_did = did_result['did']
        
        # Сохранение в БД
        institution_data = {
            'institution_id': institution_id,
            'name': data['institution_name'],
            'license_number': data['license_number'],
            'type_id': data['institution_type'],
            'did': institution_did,
            'verkey': did_result.get('verkey'),
            'address': data.get('address', ''),
            'contact_email': data.get('contact_email'),
            'metadata': {
                'registered_by': 'REGULATOR_API',
                'registration_timestamp': datetime.now().isoformat()
            }
        }
        
        institution = db.create_institution(institution_data)
        
        if not institution:
            return jsonify({"error": "Не удалось сохранить учреждение в БД"}), 500
        
        logging.info(f"Зарегистрировано новое учреждение: {data['institution_name']}, DID: {institution_did}")
        
        # Запись в аудит-лог
        db.log_action({
            'action_type': 'INSTITUTION_REGISTERED',
            'performed_by': 'REGULATOR_API',
            'target_institution_id': institution_id,
            'description': f'Зарегистрировано новое учреждение: {data["institution_name"]}'
        })
        
        return jsonify({
            'success': True,
            'message': 'Медицинское учреждение успешно зарегистрировано',
            'institution_id': institution_id,
            'did': institution_did,
            'seed': did_seed,
            'instructions': 'Используйте этот DID для настройки вашего агента'
        }), 200
        
    except Exception as e:
        logging.error(f"Ошибка при регистрации учреждения: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

@app.route('/credential-issuance-requests/<request_id>/approve', methods=['POST'])
def approve_credential_request(request_id):
    """Одобрение заявки на выпуск VC с сохранением в БД"""
    try:
        # Получение заявки из БД
        request_data = db.get_credential_issuance_request(request_id)
        if not request_data:
            return jsonify({"error": "Заявка не найдена"}), 404
        
        # Проверка статуса
        if request_data['status_id'] != 'pending':
            return jsonify({"error": "Заявка уже обработана"}), 400
        
        # Получение причины одобрения
        decision_reason = request.json.get('reason', 'Одобрено регулятором')
        decision_by = request.json.get('decision_by', 'REGULATOR')
        
        # Обновление статуса заявки в БД
        approved = db.update_credential_issuance_request_status(
            request_id=request_id,
            status_id='approved',
            decision_reason=decision_reason,
            decision_by=decision_by
        )
        
        if not approved:
            return jsonify({"error": "Не удалось обновить статус заявки"}), 500
        
        # Добавление типа VC в разрешенные для учреждения
        credential_added = db.add_allowed_credential(
            institution_id=request_data['institution_id'],
            credential_type_id=request_data['credential_type_id'],
            granted_by=decision_by
        )
        
        if not credential_added:
            logging.warning(f"Не удалось добавить разрешение на VC для учреждения {request_data['institution_id']}")
        
        logging.info(f"Заявка {request_id} одобрена. Учреждение теперь может выпускать {request_data['credential_type_id']}")
        
        # Отправка уведомления через агента
        hospital_did = request_data['institution_did']
        notification_sent = send_notification_to_hospital(
            hospital_did=hospital_did,
            notification_type='CREDENTIAL_ISSUANCE_APPROVED',
            data={
                'request_id': request_id,
                'credential_type': request_data['credential_type_id'],
                'decision_reason': decision_reason,
                'decision_by': decision_by
            }
        )
        
        # Сохранение уведомления в БД
        if notification_sent:
            db.save_notification({
                'institution_id': request_data['institution_id'],
                'notification_type': 'CREDENTIAL_ISSUANCE_APPROVED',
                'message_data': {
                    'request_id': request_id,
                    'credential_type': request_data['credential_type_id']
                }
            })
        
        # Запись в аудит-лог
        db.log_action({
            'action_type': 'CREDENTIAL_ISSUANCE_APPROVED',
            'performed_by': decision_by,
            'target_institution_id': request_data['institution_id'],
            'target_request_id': request_id,
            'description': f'Одобрена заявка на выпуск VC типа {request_data["credential_type_id"]}'
        })
        
        return jsonify({
            'success': True,
            'message': 'Заявка одобрена',
            'request_id': request_id,
            'credential_type': request_data['credential_type_id'],
            'notification_sent': notification_sent
        }), 200
        
    except Exception as e:
        logging.error(f"Ошибка при одобрении заявки: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

# Обновленная функция отправки уведомлений
def send_notification_to_hospital(hospital_did, notification_type, data):
    """Отправка уведомления больнице через агента с сохранением в БД"""
    try:
        # Получение соединения из БД
        connection = db.get_connection_by_did(hospital_did)
        
        if not connection:
            logging.warning(f"Нет активного соединения с больницей DID: {hospital_did}")
            return False
        
        # Формирование сообщения
        notification_message = {
            'type': notification_type,
            'from': 'REGULATOR',
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        # Отправка через агента
        response = requests.post(
            f"{AGENT_ADMIN_URL}/connections/{connection['connection_id']}/send-message",
            headers=HEADERS,
            json={
                "content": json.dumps(notification_message, ensure_ascii=False)
            }
        )
        
        if response.status_code == 200:
            logging.info(f"✅ Уведомление отправлено больнице {hospital_did}: {notification_type}")
            
            # Обновление статуса уведомления в БД
            # (если сохранили уведомление перед отправкой)
            
            return True
        else:
            logging.error(f"❌ Ошибка отправки уведомления: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Исключение при отправке уведомления: {e}")
        return False

@app.route('/statistics', methods=['GET'])
def get_statistics():
    """Получение статистики регулятора из БД"""
    try:
        stats = db.get_statistics()
        return jsonify(stats), 200
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/recent-activity', methods=['GET'])
def get_recent_activity():
    """Получение последних действий из аудит-лога"""
    try:
        limit = request.args.get('limit', 50, type=int)
        activities = db.get_recent_activity(limit=limit)
        return jsonify(activities), 200
    except Exception as e:
        logging.error(f"Ошибка при получении истории действий: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Остальной код контроллера остается аналогичным, но с заменой 
# операций со словарями на вызовы методов db.*

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/regulator.log'),
            logging.StreamHandler()
        ]
    )
    
    print("🏛️  Запуск контроллера государственного регулятора с PostgreSQL...")
    print(f"📊 Панель управления: http://localhost:8070")
    print(f"🗄️  База данных: PostgreSQL на порту 5433")
    print(f"📈 Статистика доступна по: http://localhost:8070/statistics")
    
    app.run(host='0.0.0.0', port=8070, debug=True)
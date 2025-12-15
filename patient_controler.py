import requests
import json
import logging
import time
from flask import Flask, request, jsonify, render_template_string
from typing import Dict, List, Optional

app = Flask(__name__)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8031"
AGENT_API_KEY = "patient-admin-key-456"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

HTML_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>Мой Медицинский Кошелек</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .credential { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .hidden { display: none; }
        .cred-id { font-family: monospace; font-size: 0.9em; color: #666; }
        .attr-name { font-weight: bold; }
        .attr-value { margin-left: 10px; }
        .blockchain-ref { background: #f0f0f0; padding: 10px; border-radius: 3px; font-family: monospace; }
    </style>
</head>
<body>
    <h1>👤 Мой Медицинский Кошелек</h1>
    
    <div>
        <h2>Мои медицинские справки</h2>
        <button onclick="loadCredentials()">Обновить список справок</button>
        <div id="credentialsList"></div>
    </div>
    
    <div>
        <h2>Экстренный доступ</h2>
        <div style="background: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeaa7;">
            <p>В экстренной ситуации (скорая помощь, приемный покой):</p>
            <button onclick="enableEmergencyMode()" style="background: #dc3545; color: white; padding: 10px 20px; border: none; border-radius: 4px;">
                🔴 Активировать экстренный режим
            </button>
            <p id="emergencyStatus"></p>
        </div>
    </div>
    
    <script>
        async function loadCredentials() {
            const response = await fetch('/credentials');
            const credentials = await response.json();
            
            let html = '';
            credentials.forEach(cred => {
                const attrs = cred.attrs || {};
                const meta = cred.metadata || {};
                
                html += `<div class="credential">
                    <h3>🏥 ${attrs.issuer_name || 'Неизвестный эмитент'}</h3>
                    <div class="cred-id">ID: ${cred.credential_id}</div>
                    <div>Дата выдачи: ${new Date(cred.created_at).toLocaleString()}</div>
                    <div><strong>Тип документа:</strong> ${meta.document_type || 'Медицинская справка'}</div>
                    
                    <h4>Данные:</h4>
                    ${Object.entries(attrs)
                        .filter(([key]) => !key.startsWith('_'))
                        .map(([key, value]) => `
                            <div>
                                <span class="attr-name">${key}:</span>
                                <span class="attr-value">${typeof value === 'string' ? value : JSON.stringify(value)}</span>
                            </div>
                        `).join('')}
                    
                    ${attrs._hospital_endpoint ? `
                        <h4>🔗 Ссылка для запроса документа:</h4>
                        <div class="blockchain-ref">${attrs._hospital_endpoint}</div>
                        <small>Используется для повторного запроса справки у больницы</small>
                    ` : ''}
                    
                    ${attrs._blockchain_ref ? `
                        <h4>⛓️ Ссылка на блокчейн:</h4>
                        <div class="blockchain-ref">${JSON.stringify(attrs._blockchain_ref)}</div>
                    ` : ''}
                    
                    <button onclick="showConsentDialog('${cred.credential_id}')">Настроить доступ</button>
                </div>`;
            });
            
            document.getElementById('credentialsList').innerHTML = html || '<p>Нет медицинских справок</p>';
        }
        
        async function enableEmergencyMode() {
            const response = await fetch('/emergency/enable', { method: 'POST' });
            const result = await response.json();
            document.getElementById('emergencyStatus').innerHTML = 
                `<strong>${result.enabled ? '✅ ЭКСТРЕННЫЙ РЕЖИМ АКТИВЕН' : '❌ Ошибка активации'}</strong><br>
                 ${result.message || ''}`;
        }
        
        function showConsentDialog(credentialId) {
            alert(`Настройка доступа для справки ${credentialId}\n\nВ реальном приложении здесь был бы интерфейс управления согласием.`);
        }
        
        // Загружаем справки при загрузке страницы
        window.onload = loadCredentials;
    </script>
</body>
</html>
"""

def get_wallet_credentials() -> List[Dict]:
    """Получить все верифицируемые учетные данные из кошелька пациента"""
    try:
        response = requests.get(f"{AGENT_ADMIN_URL}/credentials", headers=HEADERS)
        if response.status_code == 200:
            return response.json().get('results', [])
    except Exception as e:
        logging.error(f"Ошибка получения credentials из кошелька: {e}")
    return []

def get_credential_by_id(credential_id: str) -> Optional[Dict]:
    """Получить конкретный credential по ID"""
    try:
        response = requests.get(f"{AGENT_ADMIN_URL}/credentials/{credential_id}", headers=HEADERS)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logging.error(f"Ошибка получения credential {credential_id}: {e}")
    return None

def extract_blockchain_references(credential: Dict) -> Dict:
    """Извлечь blockchain-ссылки и метаданные из атрибутов credential"""
    attrs = credential.get('attrs', {})
    references = {}
    
    # Извлекаем метаданные из специальных атрибутов (начинающихся с _)
    for key, value in attrs.items():
        if key.startswith('_'):
            references[key] = value
    
    return references

@app.route('/')
def patient_dashboard():
    """Панель управления пациента"""
    return render_template_string(HTML_INTERFACE)

@app.route('/webhooks/topic/<topic>', methods=['POST'])
def handle_webhooks(topic: str):
    """
    Обработка вебхуков от агента
    """
    message = request.json
    logging.info(f"[Webhook] Топик: {topic}")
    
    if topic == 'connections':
        if message['state'] == 'response':
            logging.info(f"✅ Соединение установлено: {message['connection_id']}")
    
    elif topic == 'issue_credential':
        handle_credential_webhook(message)
    
    elif topic == 'present_proof':
        handle_proof_webhook(message)
    
    return jsonify({"status": "processed"}), 200

def handle_credential_webhook(message: Dict):
    """Обработка вебхуков о выпуске credentials"""
    state = message.get('state')
    cred_ex_id = message.get('credential_exchange_id')
    
    if state == 'offer_received':
        logging.info(f"📄 Получено предложение справки: {cred_ex_id}")
        # Автоматически запрашиваем credential
        requests.post(
            f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}/send-request",
            headers=HEADERS, 
            json={}
        )
    
    elif state == 'credential_received':
        logging.info("🎉 Новая медицинская справка сохранена в кошельке!")
        
        # Получаем детали credential
        record_resp = requests.get(
            f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}",
            headers=HEADERS
        )
        
        if record_resp.status_code == 200:
            record = record_resp.json()
            cred_id = record.get('credential_id')
            
            # Проверяем наличие blockchain-ссылок в атрибутах
            if cred_id:
                credential = get_credential_by_id(cred_id)
                if credential:
                    references = extract_blockchain_references(credential)
                    if references:
                        logging.info(f"📎 Извлечены blockchain-ссылки: {list(references.keys())}")

def handle_proof_webhook(message: Dict):
    """Обработка вебхуков о запросах доказательств"""
    state = message.get('state')
    pres_ex_id = message.get('presentation_exchange_id')
    
    if state == 'request_received':
        logging.info(f"🔍 Получен запрос на предоставление данных: {pres_ex_id}")
        
        # Получаем детали запроса
        record_resp = requests.get(
            f"{AGENT_ADMIN_URL}/present-proof/records/{pres_ex_id}",
            headers=HEADERS
        )
        
        if record_resp.status_code == 200:
            record = record_resp.json()
            proof_request = record.get('presentation_request', {})
            
            # Определяем, является ли запрос экстренным
            is_emergency = "emergency" in proof_request.get('name', '').lower()
            
            if is_emergency and check_emergency_consent():
                # Автоматически предоставляем только критические данные в экстренном случае
                provide_emergency_data(pres_ex_id)
            else:
                # В нормальном режиме - ждем согласия пользователя
                logging.info("⏳ Запрос ожидает согласия пользователя")

def check_emergency_consent() -> bool:
    """Проверяем, давал ли пациент согласие на экстренный доступ"""
    # В реальной системе здесь была бы проверка настроек пациента
    # По умолчанию разрешаем экстренный доступ (можно отключить в настройках)
    return True

def provide_emergency_data(presentation_exchange_id: str):
    """Предоставить экстренные данные по запросу"""
    try:
        # Получаем все credentials пациента
        credentials = get_wallet_credentials()
        
        # Собираем только критические данные из всех credentials
        critical_data = {}
        for cred in credentials:
            attrs = cred.get('attrs', {})
            
            # Извлекаем критические атрибуты (группа крови, аллергии)
            if 'blood_group_rh' in attrs:
                critical_data['blood_group'] = attrs['blood_group_rh']
            if 'severe_allergies' in attrs:
                critical_data['allergies'] = attrs['severe_allergies']
            if 'chronic_diagnoses' in attrs:
                critical_data['diagnoses'] = attrs['chronic_diagnoses']
        
        # Формируем ответ с критическими данными
        # В реальной системе здесь был бы формат, соответствующий proof request
        presentation = {
            "requested_attributes": {
                "blood_attr": {
                    "cred_id": credentials[0]['credential_id'] if credentials else None,
                    "revealed": True,
                    "value": critical_data.get('blood_group', 'Не указано')
                }
            },
            "comment": "Экстренный доступ к медицинским данным"
        }
        
        response = requests.post(
            f"{AGENT_ADMIN_URL}/present-proof/records/{presentation_exchange_id}/send-presentation",
            headers=HEADERS,
            json=presentation
        )
        
        if response.status_code == 200:
            logging.warning(f"⚠️ Предоставлены экстренные данные по запросу {presentation_exchange_id}")
            return True
        
    except Exception as e:
        logging.error(f"Ошибка предоставления экстренных данных: {e}")
    
    return False

@app.route('/credentials', methods=['GET'])
def get_credentials():
    """Получить все медицинские справки из кошелька с blockchain-ссылками"""
    credentials = get_wallet_credentials()
    
    enhanced_credentials = []
    for cred in credentials:
        # Извлекаем blockchain-ссылки из атрибутов
        references = extract_blockchain_references(cred)
        
        enhanced_cred = {
            "credential_id": cred.get("credential_id"),
            "schema_id": cred.get("schema_id"),
            "cred_def_id": cred.get("cred_def_id"),
            "attrs": cred.get("attrs", {}),
            "created_at": cred.get("created_at"),
            "updated_at": cred.get("updated_at"),
            "metadata": {
                "has_blockchain_ref": '_blockchain_ref' in references,
                "has_hospital_endpoint": '_hospital_endpoint' in references,
                "references_count": len(references)
            }
        }
        enhanced_credentials.append(enhanced_cred)
    
    return jsonify(enhanced_credentials), 200

@app.route('/credential/<credential_id>/consent', methods=['POST'])
def manage_credential_consent(credential_id: str):
    """Управление согласием для конкретного credential"""
    data = request.json
    action = data.get('action')  # 'grant', 'revoke', 'limit'
    verifier_did = data.get('verifier_did')
    
    # Получаем credential для проверки
    credential = get_credential_by_id(credential_id)
    if not credential:
        return jsonify({"error": "Credential не найден"}), 404
    
    # В реальной системе здесь была бы логика управления согласием
    # с сохранением в атрибуты credential или в отдельные consent credentials
    
    return jsonify({
        "status": "success",
        "credential_id": credential_id,
        "action": action,
        "verifier_did": verifier_did,
        "message": "Настройки согласия обновлены"
    }), 200

@app.route('/credential/<credential_id>/verify', methods=['POST'])
def verify_credential_with_hospital(credential_id: str):
    """Запросить верификацию credential у больницы через blockchain-ссылку"""
    credential = get_credential_by_id(credential_id)
    if not credential:
        return jsonify({"error": "Credential не найден"}), 404
    
    attrs = credential.get('attrs', {})
    hospital_endpoint = attrs.get('_hospital_endpoint')
    blockchain_ref = attrs.get('_blockchain_ref')
    
    if not hospital_endpoint:
        return jsonify({"error": "Credential не содержит ссылки на больницу"}), 400
    
    # В реальной системе здесь был бы запрос к больнице
    # по endpoint с предоставлением credential_id и blockchain_ref
    
    return jsonify({
        "status": "verification_requested",
        "credential_id": credential_id,
        "hospital_endpoint": hospital_endpoint,
        "blockchain_ref": blockchain_ref,
        "message": "Запрос на верификацию отправлен больнице"
    }), 200

@app.route('/emergency/enable', methods=['POST'])
def enable_emergency_mode():
    """Активация экстренного режима"""
    # В реальной системе здесь была бы настройка временного согласия
    return jsonify({
        "enabled": True,
        "message": "Экстренный режим активирован на 24 часа. Врачи скорой помощи могут получить доступ к критическим данным.",
        "expires_at": time.time() + 86400,  # 24 часа
        "scope": ["blood_group_rh", "severe_allergies", "chronic_diagnoses"]
    }), 200

@app.route('/emergency/disable', methods=['POST'])
def disable_emergency_mode():
    """Отключение экстренного режима"""
    return jsonify({
        "enabled": False,
        "message": "Экстренный режим отключен"
    }), 200

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("👤 Запуск контроллера пациента...")
    print(f"📱 Интерфейс доступен по адресу: http://localhost:8060")
    print(f"🔗 Административный API агента: {AGENT_ADMIN_URL}")
    
    app.run(host='0.0.0.0', port=8060, debug=True)
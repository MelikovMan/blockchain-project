import requests
import json
import logging
import time
from flask import Flask, request, jsonify, render_template_string
import os

app = Flask(__name__)
app.logger.setLevel(logging.INFO)
# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8031"
AGENT_API_KEY = "patient-admin-key-456"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# Шаблон простого UI для пациента (в реальности это мобильное приложение)
PATIENT_UI_HTML = """
<!DOCTYPE html>
<html>
<head><title>Мой Медицинский Кошелек</title></head>
<body>
    <h2>Привет, {{ patient_name }}!</h2>
    
    <h3>1. Получить приглашение от больницы</h3>
    <form action="/receive-invitation" method="post">
        <textarea name="invitation" placeholder="Вставьте приглашение (JSON)..." rows="6" cols="50"></textarea><br>
        <button type="submit">Принять приглашение</button>
    </form>
    
    <h3>2. Мои текущие соединения</h3>
    <button onclick="fetchConnections()">Обновить список</button>
    <div id="connections"></div>
    
    <h3>3. Мои медицинские справки</h3>
    <button onclick="fetchCredentials()">Показать справки</button>
    <div id="credentials"></div>
    
    <h3>4. Экстренный доступ</h3>
    <p>При запросе данных от врача:</p>
    <button onclick="checkProofRequests()">Проверить запросы на данные</button>
    <div id="proofs"></div>
</body>
</html>
"""

@app.route('/')
def patient_dashboard():
    """Простой интерфейс пациента"""
    return render_template_string(PATIENT_UI_HTML, patient_name="Иван")

@app.route('/webhooks/topic/<topic>/', methods=['POST'])
def handle_webhooks(topic):
    """
    КРИТИЧЕСКИ ВАЖНЫЙ ЭНДПОИНТ: ACA-Py отправляет сюда все события.
    Это асинхронный способ получения уведомлений от агента.
    """
    message = request.json
    logging.info(f"[Webhook] Топик: {topic}, Сообщение: {message}")
    
    if topic == 'connections':
        # Уведомление об изменении статуса соединения
        if message['state'] == 'response':
            logging.info(f"✅ Соединение установлено! ID: {message['connection_id']}")
    
    elif topic == 'issue_credential':
        # Уведомление о поступлении новой медицинской справки
        if message['state'] == 'offer_received':
            cred_ex_id = message['credential_exchange_id']
            logging.info(f"📄 Получено предложение справки. ID: {cred_ex_id}")
            # Автоматически принимаем оффер
            resp = requests.post(f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}/send-request", 
                         headers=HEADERS, json={})
            if resp.status_code == 200:
                presentation_request = resp.json().get('presentation_request')
            else:
                logging.error(f"Не удалось получить запрос на презентацию {cred_ex_id}: {resp.text}")
                return 400
        elif message['state'] == 'credential_received':
            logging.info("🎉 Медицинская справка успешно сохранена в кошельке!")
    
    elif topic == 'present_proof':
        # Уведомление о запросе доказательства (например, от врача скорой)
        if message['state'] == 'request_received':
            pres_ex_id = message['presentation_exchange_id']
            logging.info(f"🔍 Получен запрос на предоставление данных. ID: {pres_ex_id}")
            
            # В ЭКСТРЕННОМ СЛУЧАЕ: Автоматически предоставить только критичные данные
            presentation_request = message.get('presentation_request')
            if presentation_request is None:
                # Запрашиваем у агента
                resp = requests.get(f"{AGENT_ADMIN_URL}/present-proof/records/{pres_ex_id}", headers=HEADERS)
                if resp.status_code == 200:
                    presentation_request = resp.json().get('presentation_request')
                else:
                    logging.error(f"Не удалось получить запрос на презентацию {pres_ex_id}: {resp.text}")
                    return 400
            if is_emergency_request(presentation_request):
                emergency_response = {
                    "requested_attributes": {
                        "blood_attr": {"cred_id": get_credential_id(pres_ex_id), "revealed": True}
                    },
                    "requested_predicates":{},
                    "self_attested_attributes":{},
                }
                print(f"Тело ответа: {emergency_response}")
                requesting = requests.post(f"{AGENT_ADMIN_URL}/present-proof/records/{pres_ex_id}/send-presentation",
                             headers=HEADERS, json=emergency_response)
                if requesting.status_code != 200:
                    print(f"Ошибка отправки репрезентации: {requesting.text}")
                logging.warning("⚠️ Автоматически предоставлены экстренные данные!")
    
    return jsonify({"status": "ok"}), 200

def is_emergency_request(presentation_request):
    """Определяет, является ли запрос экстренным (по метаданным или политике)"""
    return "emergency" in presentation_request.get('name', '').lower()

def get_credential_id(pres_ex_id):
    """Находит ID credential, содержащего нужный атрибут"""
    # Упрощенная логика. В реальности нужно искать в wallet
    creds_resp = requests.get(f"{AGENT_ADMIN_URL}/present-proof/records/{pres_ex_id}/credentials", headers=HEADERS)
    if creds_resp.status_code != 200:
        print(f"Ошибка запроса получения credentials по предложению {creds_resp.text}")
        return None
    if not creds_resp.json():
        print(f"Не найдены credentials по запросу")
        return None
    return creds_resp.json()[0]['cred_info']["referent"]

@app.route('/receive-invitation', methods=['POST'])
def receive_invitation():
    """Принять приглашение от больницы для установления соединения"""
    invitation_json = request.form.get('invitation')
    if not invitation_json:
        return "❌ Неверный формат приглашения", 400
    try:
        invitation = json.loads(invitation_json)
    except:
        return "❌ Неверный формат приглашения", 400
    
    resp = requests.post(f"{AGENT_ADMIN_URL}/connections/receive-invitation", 
                        headers=HEADERS, json={"invitation": invitation})
    
    if resp.status_code == 200:
        return "✅ Приглашение принято! Соединение устанавливается..."
    return "❌ Ошибка при принятии приглашения", 500

@app.route('/connections', methods=['GET'])
def get_connections():
    """Получить список всех активных соединений"""
    resp = requests.get(f"{AGENT_ADMIN_URL}/connections", headers=HEADERS)
    if resp.status_code == 200:
        connections = resp.json()['results']
        return jsonify([{
            "id": c["connection_id"],
            "label": c.get("their_label", "Неизвестный"),
            "state": c["state"]
        } for c in connections])
    return jsonify([])

@app.route('/credentials', methods=['GET'])
def get_credentials():
    """Получить список всех медицинских справок в кошельке"""
    resp = requests.get(f"{AGENT_ADMIN_URL}/credentials", headers=HEADERS)
    if resp.status_code == 200:
        credentials = []
        for cred in resp.json()['results']:
            attrs = cred.get('attrs', {})
            credentials.append({
                "issuer": attrs.get('issuer', 'Неизвестно'),
                "type": cred.get('schema_id', '').split(':')[-2] if ':' in cred.get('schema_id', '') else 'Unknown',
                "issued": cred.get('created_at', ''),
                "attrs": {k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in attrs.items()}
            })
        return jsonify(credentials)
    return jsonify([])

if __name__ == '__main__':
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(filename='logs/patient.log',level=logging.INFO,encoding='utf-8')
    app.run(port=8060, debug=True)
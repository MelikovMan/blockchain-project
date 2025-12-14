import requests
import json
import logging
from flask import Flask, request, jsonify, render_template_string
import hashlib
import time

app = Flask(__name__)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8041"
AGENT_API_KEY = "regulator-admin-key-789"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# База данных зарегистрированных учреждений (в реальности - БД)
REGISTERED_ENTITIES = {
    # Формат: entity_id -> {name, did, role, status, timestamp}
}

# Уровни доступа для медицинских учреждений
MEDICAL_ROLES = {
    "HOSPITAL": "ENDORSER",        # Крупные больницы могут выпускать схемы
    "CLINIC": "TRUST_ANCHOR",      # Клиники могут писать в реестр
    "LAB": "NETWORK_MONITOR",      # Лаборатории только читают
    "PHARMACY": "USER"             # Аптеки - базовый доступ
}

HTML_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>Государственный медицинский регулятор</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .section { margin: 20px 0; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }
        input, select, textarea { width: 300px; margin: 5px 0; padding: 8px; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .success { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>🏛️ Государственный медицинский регулятор</h1>
    
    <div class="section">
        <h2>1. Регистрация нового медицинского учреждения</h2>
        <form id="registerForm">
            <input type="text" name="institution_name" placeholder="Название учреждения" required><br>
            <input type="text" name="license_number" placeholder="Лицензия №" required><br>
            <select name="institution_type" required>
                <option value="">Выберите тип учреждения</option>
                <option value="HOSPITAL">Больница</option>
                <option value="CLINIC">Поликлиника</option>
                <option value="LAB">Лаборатория</option>
                <option value="PHARMACY">Аптека</option>
            </select><br>
            <input type="email" name="contact_email" placeholder="Контактный email"><br>
            <button type="submit">Зарегистрировать DID</button>
        </form>
        <div id="registerResult"></div>
    </div>
    
    <div class="section">
        <h2>2. Просмотр зарегистрированных учреждений</h2>
        <button onclick="loadEntities()">Обновить список</button>
        <div id="entitiesList"></div>
    </div>
    
    <div class="section">
        <h2>3. Проверка статуса учреждения</h2>
        <input type="text" id="checkDid" placeholder="Введите DID для проверки">
        <button onclick="checkEntity()">Проверить</button>
        <div id="checkResult"></div>
    </div>
    
    <div class="section">
        <h2>4. Отзыв/приостановка регистрации</h2>
        <input type="text" id="revokeDid" placeholder="DID учреждения">
        <select id="revokeAction">
            <option value="SUSPEND">Приостановить</option>
            <option value="REVOKE">Отозвать</option>
            <option value="REINSTATE">Восстановить</option>
        </select>
        <input type="text" id="revokeReason" placeholder="Причина">
        <button onclick="updateStatus()">Изменить статус</button>
        <div id="revokeResult"></div>
    </div>
    
    <script>
        document.getElementById('registerForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            const response = await fetch('/register-entity', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            const resultDiv = document.getElementById('registerResult');
            
            if (response.ok) {
                resultDiv.innerHTML = `<div class="success">
                    <strong>✓ Учреждение зарегистрировано!</strong><br>
                    DID: ${result.did}<br>
                    Seed: ${result.seed}<br>
                    Роль: ${result.role}<br>
                    <small>Сохраните seed для настройки агента учреждения</small>
                </div>`;
            } else {
                resultDiv.innerHTML = `<div class="error">❌ Ошибка: ${result.error}</div>`;
            }
        };
        
        async function loadEntities() {
            const response = await fetch('/entities');
            const entities = await response.json();
            
            let html = '<table border="1" cellpadding="10"><tr><th>Название</th><th>DID</th><th>Роль</th><th>Статус</th><th>Дата</th></tr>';
            entities.forEach(e => {
                html += `<tr>
                    <td>${e.name}</td>
                    <td><code>${e.did}</code></td>
                    <td>${e.role}</td>
                    <td>${e.status}</td>
                    <td>${new Date(e.timestamp).toLocaleDateString()}</td>
                </tr>`;
            });
            html += '</table>';
            
            document.getElementById('entitiesList').innerHTML = html;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def regulator_dashboard():
    """Панель управления регулятора"""
    return render_template_string(HTML_INTERFACE)

@app.route('/webhooks/topic/<topic>', methods=['POST'])
def handle_regulator_webhooks(topic):
    """Обработка вебхуков от агента"""
    message = request.json
    logging.info(f"[Regulator Webhook] Topic: {topic}, Message: {message}")
    
    if topic == 'endorsements':
        # Обработка запросов на подпись транзакций от учреждений
        if message.get('state') == 'request-received':
            transaction_id = message.get('transaction_id')
            # Здесь можно добавить бизнес-логику проверки запроса
            
    return jsonify({"status": "processed"}), 200

@app.route('/register-entity', methods=['POST'])
def register_medical_entity():
    """Основной эндпоинт: регистрация нового медицинского учреждения"""
    try:
        data = request.json
        
        # Валидация входных данных
        required_fields = ['institution_name', 'license_number', 'institution_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
        
        institution_name = data['institution_name']
        license_number = data['license_number']
        institution_type = data['institution_type']
        contact_email = data.get('contact_email', '')
        
        # Проверка типа учреждения
        if institution_type not in MEDICAL_ROLES:
            return jsonify({"error": f"Неверный тип учреждения. Допустимые: {list(MEDICAL_ROLES.keys())}"}), 400
        
        # Генерация уникального DID seed на основе данных учреждения
        # В реальной системе здесь должна быть криптографически безопасная генерация
        seed_base = f"{license_number}_{institution_name}_{int(time.time())}"
        entity_seed = hashlib.sha256(seed_base.encode()).hexdigest()[:32]
        
        # DID формируется на основе сида
        entity_did = f"did:sov:{entity_seed[:16]}"
        entity_role = MEDICAL_ROLES[institution_type]
        
        # Регистрация DID в сети Indy через агента регулятора
        registration_result = register_did_on_ledger(
            did=entity_did,
            seed=entity_seed,
            role=entity_role,
            alias=institution_name
        )
        
        if not registration_result:
            return jsonify({"error": "Не удалось зарегистрировать DID в сети"}), 500
        
        # Сохранение в базу данных регулятора
        entity_id = hashlib.md5(license_number.encode()).hexdigest()
        REGISTERED_ENTITIES[entity_id] = {
            "id": entity_id,
            "name": institution_name,
            "did": entity_did,
            "seed": entity_seed,
            "role": entity_role,
            "type": institution_type,
            "license": license_number,
            "email": contact_email,
            "status": "ACTIVE",
            "registered_by": "State_Regulator",
            "timestamp": time.time()
        }
        
        # Логирование действия
        logging.info(f"Зарегистрировано новое учреждение: {institution_name}, DID: {entity_did}")
        
        return jsonify({
            "success": True,
            "message": "Медицинское учреждение успешно зарегистрировано",
            "institution_id": entity_id,
            "did": entity_did,
            "seed": entity_seed,
            "role": entity_role,
            "instructions": "Используйте этот seed в настройках вашего агента ACA-Py (ACAPY_WALLET_SEED)"
        }), 200
        
    except Exception as e:
        logging.error(f"Ошибка при регистрации учреждения: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500

def register_did_on_ledger(did: str, seed: str, role: str, alias: str):
    """
    Регистрация публичного DID в сети Indy через транзакцию NYM
    Использует административный API агента регулятора
    """
    try:
        # Формирование транзакции NYM для регистрации DID
        nym_transaction = {
            "did": did,
            "seed": seed,
            "role": role,
            "alias": alias
        }
        
        # Отправка запроса на регистрацию через агента
        # В реальности это делается через write_did или подобный эндпоинт
        # Здесь упрощенная версия для демонстрации
        response = requests.post(
            f"{AGENT_ADMIN_URL}/ledger/register-nym",
            headers=HEADERS,
            json=nym_transaction,
            timeout=30
        )
        
        if response.status_code == 200:
            logging.info(f"DID {did} успешно зарегистрирован с ролью {role}")
            return True
        else:
            logging.error(f"Ошибка регистрации DID: {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Исключение при регистрации DID: {str(e)}")
        return False

@app.route('/entities', methods=['GET'])
def get_registered_entities():
    """Получение списка всех зарегистрированных учреждений"""
    entities_list = []
    for entity_id, entity_data in REGISTERED_ENTITIES.items():
        entities_list.append({
            "id": entity_id,
            "name": entity_data["name"],
            "did": entity_data["did"],
            "role": entity_data["role"],
            "type": entity_data["type"],
            "license": entity_data["license"],
            "status": entity_data["status"],
            "timestamp": entity_data["timestamp"]
        })
    
    return jsonify(entities_list), 200

@app.route('/entity/<entity_id>', methods=['GET'])
def get_entity_details(entity_id):
    """Получение детальной информации об учреждении"""
    if entity_id not in REGISTERED_ENTITIES:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    return jsonify(REGISTERED_ENTITIES[entity_id]), 200

@app.route('/entity/<entity_id>/status', methods=['PUT'])
def update_entity_status(entity_id):
    """Изменение статуса учреждения (активно/приостановлено/отозвано)"""
    if entity_id not in REGISTERED_ENTITIES:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    data = request.json
    new_status = data.get("status")
    reason = data.get("reason", "")
    
    valid_statuses = ["ACTIVE", "SUSPENDED", "REVOKED"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Неверный статус. Допустимые: {valid_statuses}"}), 400
    
    # В реальной системе здесь должна быть дополнительная бизнес-логика
    # и возможно, отзыв DID из реестра
    
    REGISTERED_ENTITIES[entity_id]["status"] = new_status
    REGISTERED_ENTITIES[entity_id]["status_reason"] = reason
    REGISTERED_ENTITIES[entity_id]["status_updated"] = time.time()
    
    logging.warning(f"Изменен статус учреждения {entity_id}: {new_status}. Причина: {reason}")
    
    return jsonify({
        "success": True,
        "message": f"Статус учреждения изменен на {new_status}",
        "entity_id": entity_id,
        "new_status": new_status
    }), 200

@app.route('/verify-credential-def', methods=['POST'])
def verify_credential_definition():
    """
    Верификация схемы учетных данных, выпущенной медицинским учреждением.
    Регулятор проверяет, что схема соответствует государственным стандартам.
    """
    try:
        data = request.json
        cred_def_id = data.get("cred_def_id")
        issuer_did = data.get("issuer_did")
        
        # Проверка, что DID учреждения зарегистрирован
        issuer_found = False
        for entity in REGISTERED_ENTITIES.values():
            if entity["did"] == issuer_did and entity["status"] == "ACTIVE":
                issuer_found = True
                break
        
        if not issuer_found:
            return jsonify({
                "verified": False,
                "error": "DID учреждения не найден или не активен"
            }), 400
        
        # Здесь можно добавить дополнительную логику проверки схемы
        # Например, проверка соответствия стандартам HL7 FHIR
        
        # Для демонстрации просто возвращаем успех
        return jsonify({
            "verified": True,
            "cred_def_id": cred_def_id,
            "issuer_did": issuer_did,
            "issuer_status": "ACTIVE",
            "verification_date": time.time(),
            "regulator_stamp": "STATE_MEDICAL_REGULATOR_V1"
        }), 200
        
    except Exception as e:
        return jsonify({
            "verified": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🏛️  Запуск контроллера государственного регулятора...")
    print(f"📊 Панель управления доступна по адресу: http://localhost:8070")
    print(f"🔗 Административный API агента: {AGENT_ADMIN_URL}")
    
    app.run(host='0.0.0.0', port=8070, debug=True)
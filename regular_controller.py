import requests
import json
import logging
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# Конфигурация
AGENT_ADMIN_URL = "http://localhost:8041"
AGENT_API_KEY = "regulator-admin-key-789"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# База данных зарегистрированных учреждений
REGISTERED_INSTITUTIONS = {
    # Формат: institution_id -> {name, did, role, status, credential_types, registered_at}
}

# База данных заявок на выпуск VC
CREDENTIAL_ISSUANCE_REQUESTS = {
    # Формат: request_id -> {hospital_id, schema_data, status, decision_date, decision_reason}
}

# База данных изменений типов VC
CREDENTIAL_MODIFICATION_REQUESTS = {
    # Формат: modification_id -> {hospital_id, action, credential_types, status, decision}
}

# Справочник разрешенных типов медицинских документов
APPROVED_CREDENTIAL_TYPES = {
    "MEDICAL_RECORD": "Медицинская карта",
    "PRESCRIPTION": "Рецепт",
    "LAB_RESULT": "Результат анализа",
    "VACCINATION_CERTIFICATE": "Сертификат вакцинации",
    "DISCHARGE_SUMMARY": "Выписка из стационара",
    "REFERRAL": "Направление на консультацию",
    "SICK_LEAVE_CERTIFICATE": "Больничный лист"
}

HTML_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>Реестр медицинских учреждений</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }
        .section-title { color: #3498db; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 30px; }
        .btn { padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn-success { background: #27ae60; }
        .btn-warning { background: #f39c12; }
        .btn-danger { background: #e74c3c; }
        .btn-small { padding: 5px 10px; font-size: 12px; }
        .status-active { color: #27ae60; font-weight: bold; }
        .status-pending { color: #f39c12; font-weight: bold; }
        .status-rejected { color: #e74c3c; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #ecf0f1; }
        .badge { padding: 3px 8px; border-radius: 12px; font-size: 12px; }
        .badge-success { background: #d5f4e6; color: #27ae60; }
        .badge-warning { background: #fef5e7; color: #f39c12; }
        .badge-danger { background: #fadbd8; color: #e74c3c; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏛️ Государственный реестр медицинских учреждений</h1>
            <p>Управление регистрацией и разрешениями для выпуска верифицируемых медицинских документов</p>
        </div>
        
        <!-- Раздел 1: Регистрация учреждений -->
        <div class="card">
            <h2 class="section-title">1. Регистрация медицинских учреждений</h2>
            <form id="registerForm">
                <input type="text" name="institution_name" placeholder="Полное название учреждения" required style="width: 300px; padding: 8px; margin: 5px;">
                <input type="text" name="license_number" placeholder="Номер лицензии" required style="width: 200px; padding: 8px; margin: 5px;">
                <select name="institution_type" required style="padding: 8px; margin: 5px;">
                    <option value="">Тип учреждения</option>
                    <option value="HOSPITAL">Больница</option>
                    <option value="POLYCLINIC">Поликлиника</option>
                    <option value="DIAGNOSTIC_CENTER">Диагностический центр</option>
                    <option value="LABORATORY">Лаборатория</option>
                </select>
                <input type="text" name="address" placeholder="Юридический адрес" style="width: 300px; padding: 8px; margin: 5px;">
                <button type="submit" class="btn">Зарегистрировать</button>
            </form>
            <div id="registerResult"></div>
        </div>
        
        <!-- Раздел 2: Заявки на выпуск VC -->
        <div class="card">
            <h2 class="section-title">2. Заявки на выпуск верифицируемых документов</h2>
            <div id="credentialRequests"></div>
        </div>
        
        <!-- Раздел 3: Изменения типов VC -->
        <div class="card">
            <h2 class="section-title">3. Запросы на изменение типов документов</h2>
            <div id="modificationRequests"></div>
        </div>
        
        <!-- Раздел 4: Зарегистрированные учреждения -->
        <div class="card">
            <h2 class="section-title">4. Зарегистрированные медицинские учреждения</h2>
            <button onclick="loadInstitutions()" class="btn">Обновить список</button>
            <div id="institutionsList"></div>
        </div>
    </div>

    <script>
        // Регистрация учреждения
        document.getElementById('registerForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            const response = await fetch('/register-institution', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            const resultDiv = document.getElementById('registerResult');
            
            if (response.ok) {
                resultDiv.innerHTML = `
                    <div style="background: #d5f4e6; padding: 15px; border-radius: 4px; margin-top: 10px;">
                        <strong>✓ Учреждение зарегистрировано!</strong><br>
                        DID: <code>${result.did}</code><br>
                        ID учреждения: ${result.institution_id}<br>
                        <small>Сохраните эту информацию для настройки системы учреждения</small>
                    </div>`;
                loadCredentialRequests();
                loadModificationRequests();
                loadInstitutions();
            } else {
                resultDiv.innerHTML = `<div style="background: #fadbd8; padding: 15px; border-radius: 4px; margin-top: 10px;">❌ Ошибка: ${result.error}</div>`;
            }
        };
        
        // Загрузка заявок на выпуск VC
        async function loadCredentialRequests() {
            const response = await fetch('/credential-issuance-requests');
            const requests = await response.json();
            
            let html = '<table><tr><th>ID заявки</th><th>Учреждение</th><th>Тип документа</th><th>Статус</th><th>Дата</th><th>Действия</th></tr>';
            requests.forEach(req => {
                html += `<tr>
                    <td>${req.request_id}</td>
                    <td>${req.hospital_name}</td>
                    <td>${req.credential_type}</td>
                    <td class="status-${req.status}">${req.status === 'pending' ? 'На рассмотрении' : 
                                                     req.status === 'approved' ? 'Одобрено' : 'Отклонено'}</td>
                    <td>${new Date(req.submitted_at).toLocaleString()}</td>
                    <td>`;
                if (req.status === 'pending') {
                    html += `<button class="btn btn-small btn-success" onclick="approveCredentialRequest('${req.request_id}')">Одобрить</button>
                            <button class="btn btn-small btn-danger" onclick="rejectCredentialRequest('${req.request_id}')">Отклонить</button>`;
                }
                html += `</td></tr>`;
            });
            html += '</table>';
            
            document.getElementById('credentialRequests').innerHTML = html;
        }
        
        // Загрузка запросов на изменение
        async function loadModificationRequests() {
            const response = await fetch('/credential-modification-requests');
            const requests = await response.json();
            
            let html = '<table><tr><th>ID запроса</th><th>Учреждение</th><th>Действие</th><th>Типы документов</th><th>Статус</th><th>Действия</th></tr>';
            requests.forEach(req => {
                html += `<tr>
                    <td>${req.modification_id}</td>
                    <td>${req.hospital_name}</td>
                    <td>${req.action === 'ADD' ? 'Добавление' : 'Удаление'}</td>
                    <td>${req.credential_types.join(', ')}</td>
                    <td class="status-${req.status}">${req.status === 'pending' ? 'На рассмотрении' : 
                                                       req.status === 'approved' ? 'Одобрено' : 'Отклонено'}</td>
                    <td>`;
                if (req.status === 'pending') {
                    html += `<button class="btn btn-small btn-success" onclick="approveModificationRequest('${req.modification_id}')">Одобрить</button>
                            <button class="btn btn-small btn-danger" onclick="rejectModificationRequest('${req.modification_id}')">Отклонить</button>`;
                }
                html += `</td></tr>`;
            });
            html += '</table>';
            
            document.getElementById('modificationRequests').innerHTML = html;
        }
        
        // Загрузка учреждений
        async function loadInstitutions() {
            const response = await fetch('/institutions');
            const institutions = await response.json();
            
            let html = '<table><tr><th>Название</th><th>DID</th><th>Лицензия</th><th>Разрешенные VC</th><th>Статус</th><th>Действия</th></tr>';
            institutions.forEach(inst => {
                html += `<tr>
                    <td>${inst.name}</td>
                    <td><code>${inst.did}</code></td>
                    <td>${inst.license_number}</td>
                    <td>`;
                inst.allowed_credentials.forEach(type => {
                    html += `<span class="badge badge-success">${type}</span> `;
                });
                html += `</td>
                    <td class="status-${inst.status.toLowerCase()}">${inst.status === 'ACTIVE' ? 'Активно' : 'Приостановлено'}</td>
                    <td>
                        <button class="btn btn-small btn-warning" onclick="openModifyDialog('${inst.institution_id}')">Изменить VC</button>
                        ${inst.status === 'ACTIVE' ? 
                            `<button class="btn btn-small btn-danger" onclick="suspendInstitution('${inst.institution_id}')">Приостановить</button>` :
                            `<button class="btn btn-small btn-success" onclick="activateInstitution('${inst.institution_id}')">Активировать</button>`}
                    </td>
                </tr>`;
            });
            html += '</table>';
            
            document.getElementById('institutionsList').innerHTML = html;
        }
        
        // Функции для работы с заявками
        async function approveCredentialRequest(requestId) {
            const reason = prompt("Введите причину одобрения (опционально):");
            const response = await fetch(`/credential-issuance-requests/${requestId}/approve`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({reason: reason || ''})
            });
            if (response.ok) {
                loadCredentialRequests();
                loadInstitutions();
            }
        }
        
        async function rejectCredentialRequest(requestId) {
            const reason = prompt("Введите причину отклонения:");
            if (reason) {
                const response = await fetch(`/credential-issuance-requests/${requestId}/reject`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({reason: reason})
                });
                if (response.ok) {
                    loadCredentialRequests();
                }
            }
        }
        
        async function approveModificationRequest(modificationId) {
            const response = await fetch(`/credential-modification-requests/${modificationId}/approve`, {
                method: 'POST'
            });
            if (response.ok) {
                loadModificationRequests();
                loadInstitutions();
            }
        }
        
        async function rejectModificationRequest(modificationId) {
            const reason = prompt("Введите причину отклонения:");
            if (reason) {
                const response = await fetch(`/credential-modification-requests/${modificationId}/reject`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({reason: reason})
                });
                if (response.ok) {
                    loadModificationRequests();
                }
            }
        }
        
        // Диалог изменения разрешенных VC
        function openModifyDialog(institutionId) {
            const institution = REGISTERED_INSTITUTIONS[institutionId];
            if (!institution) return;
            
            let html = `<h3>Изменение разрешенных типов VC для ${institution.name}</h3>`;
            html += `<form id="modifyForm">
                <input type="hidden" name="institution_id" value="${institutionId}">
                <select name="action" style="padding: 8px; margin: 5px;">
                    <option value="ADD">Добавить типы</option>
                    <option value="REMOVE">Удалить типы</option>
                </select><br>`;
            
            Object.entries(APPROVED_CREDENTIAL_TYPES).forEach(([key, value]) => {
                const isAllowed = institution.allowed_credentials.includes(key);
                html += `<label style="display: block; margin: 5px;">
                    <input type="checkbox" name="credential_types" value="${key}" ${isAllowed ? 'checked' : ''}>
                    ${value} (${key})
                </label>`;
            });
            
            html += `<button type="submit" class="btn">Отправить на утверждение</button>
                </form>`;
            
            const dialog = window.open("", "Изменение VC", "width=500,height=600");
            dialog.document.write(html);
            dialog.document.getElementById('modifyForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData.entries());
                data.credential_types = formData.getAll('credential_types');
                
                const response = await fetch('/request-credential-modification', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    alert('Запрос отправлен на утверждение');
                    dialog.close();
                    loadModificationRequests();
                }
            };
        }
        
        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', () => {
            loadCredentialRequests();
            loadModificationRequests();
            loadInstitutions();
        });
    </script>
</body>
</html>
"""

# Глобальная переменная для хранения списка учреждений
REGISTERED_INSTITUTIONS = {}

@app.route('/')
def regulator_dashboard():
    """Панель управления регулятора"""
    return render_template_string(HTML_INTERFACE)

@app.route('/webhooks/topic/<topic>', methods=['POST'])
def handle_regulator_webhooks(topic):
    """Обработка вебхуков от агента регулятора"""
    message = request.json
    logging.info(f"[Regulator Webhook] Topic: {topic}, Message: {message}")
    
    if topic == 'endorsements':
        # Обработка запросов на эндоузинг транзакций
        state = message.get('state')
        transaction_id = message.get('transaction_id')
        
        if state == 'request-received':
            # Транзакция ожидает подписи регулятора
            logging.info(f"Получена транзакция для подписи: {transaction_id}")
            # Можно добавить бизнес-логику автоматической проверки транзакций
            # Например, проверять, что учреждение имеет право на регистрацию схемы
            
    elif topic == 'connections':
        # Обработка соединений с медицинскими учреждениями
        state = message.get('state')
        connection_id = message.get('connection_id')
        their_label = message.get('their_label')
        
        if state == 'request':
            # Автоматически принимаем запросы на соединение от зарегистрированных учреждений
            if their_label in [inst['name'] for inst in REGISTERED_INSTITUTIONS.values()]:
                accept_connection(connection_id)
    
    return jsonify({"status": "processed"}), 200

def accept_connection(connection_id):
    """Принять соединение с учреждением"""
    try:
        response = requests.post(
            f"{AGENT_ADMIN_URL}/connections/{connection_id}/accept-request",
            headers=HEADERS,
            json={}
        )
        if response.status_code == 200:
            logging.info(f"Соединение {connection_id} принято")
            return True
    except Exception as e:
        logging.error(f"Ошибка при принятии соединения: {e}")
    return False

@app.route('/register-institution', methods=['POST'])
def register_institution():
    """Регистрация медицинского учреждения и выпуск публичного DID"""
    try:
        data = request.json
        
        # Валидация
        required_fields = ['institution_name', 'license_number', 'institution_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
        
        # Проверка уникальности лицензии
        for inst in REGISTERED_INSTITUTIONS.values():
            if inst['license_number'] == data['license_number']:
                return jsonify({"error": "Учреждение с таким номером лицензии уже зарегистрировано"}), 400
        
        # Генерация уникального DID для учреждения
        institution_id = str(uuid.uuid4())
        did_seed = f"institution_{data['license_number']}_{int(time.time())}"
        
        # Регистрация DID в блокчейне через агента регулятора
        did_result = register_institution_did(
            seed=did_seed,
            alias=data['institution_name'],
            role="ENDORSER"  # Больницы могут быть эндоузерами для своих транзакций
        )
        
        if not did_result:
            return jsonify({"error": "Не удалось зарегистрировать DID в блокчейне"}), 500
        
        institution_did = did_result['did']
        
        # Сохранение информации об учреждении
        REGISTERED_INSTITUTIONS[institution_id] = {
            'institution_id': institution_id,
            'name': data['institution_name'],
            'license_number': data['license_number'],
            'type': data['institution_type'],
            'did': institution_did,
            'address': data.get('address', ''),
            'status': 'ACTIVE',
            'allowed_credentials': [],  # Пока нет разрешенных типов VC
            'registered_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
        
        logging.info(f"Зарегистрировано новое учреждение: {data['institution_name']}, DID: {institution_did}")
        
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

def register_institution_did(seed, alias, role="ENDORSER"):
    """Регистрация публичного DID учреждения в блокчейне"""
    try:
        # Создание DID в кошельке регулятора
        did_response = requests.post(
            f"{AGENT_ADMIN_URL}/wallet/did/create",
            headers=HEADERS,
            json={
                "method": "sov",
                "options": {"key_type": "ed25519"},
                "seed": seed
            }
        )
        
        if did_response.status_code != 200:
            logging.error(f"Ошибка создания DID: {did_response.text}")
            return None
        
        did_result = did_response.json()
        institution_did = did_result["result"]["did"]
        
        # Публикация DID в реестре (транзакция NYM)
        nym_response = requests.post(
            f"{AGENT_ADMIN_URL}/ledger/register-nym",
            headers=HEADERS,
            json={
                "did": institution_did,
                "verkey": did_result["result"]["verkey"],
                "alias": alias,
                "role": role
            }
        )
        
        if nym_response.status_code != 200:
            logging.error(f"Ошибка регистрации NYM: {nym_response.text}")
            return None
        
        logging.info(f"DID {institution_did} зарегистрирован для {alias}")
        
        return {
            'did': institution_did,
            'verkey': did_result["result"]["verkey"],
            'transaction_id': nym_response.json().get('transaction_id')
        }
        
    except Exception as e:
        logging.error(f"Исключение при регистрации DID: {str(e)}")
        return None

@app.route('/institutions', methods=['GET'])
def get_registered_institutions():
    """Получение списка всех зарегистрированных учреждений"""
    institutions_list = []
    for inst_id, inst_data in REGISTERED_INSTITUTIONS.items():
        institutions_list.append({
            'institution_id': inst_id,
            'name': inst_data['name'],
            'license_number': inst_data['license_number'],
            'type': inst_data['type'],
            'did': inst_data['did'],
            'status': inst_data['status'],
            'allowed_credentials': inst_data['allowed_credentials'],
            'registered_at': inst_data['registered_at']
        })
    
    return jsonify(institutions_list), 200

@app.route('/institutions/<institution_id>', methods=['GET'])
def get_institution_details(institution_id):
    """Получение детальной информации об учреждении"""
    if institution_id not in REGISTERED_INSTITUTIONS:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    return jsonify(REGISTERED_INSTITUTIONS[institution_id]), 200

@app.route('/request-credential-issuance', methods=['POST'])
def request_credential_issuance():
    """
    Обработка запроса от больницы на выпуск нового типа верифицируемых документов
    (Требование 3)
    """
    try:
        data = request.json
        
        # Валидация
        required_fields = ['hospital_did', 'credential_type', 'schema_data']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
        
        # Поиск учреждения по DID
        hospital = None
        hospital_id = None
        for inst_id, inst_data in REGISTERED_INSTITUTIONS.items():
            if inst_data['did'] == data['hospital_did']:
                hospital = inst_data
                hospital_id = inst_id
                break
        
        if not hospital:
            return jsonify({"error": "Учреждение с таким DID не найдено"}), 404
        
        # Проверка статуса учреждения
        if hospital['status'] != 'ACTIVE':
            return jsonify({"error": "Учреждение не активно"}), 403
        
        # Создание заявки
        request_id = str(uuid.uuid4())
        CREDENTIAL_ISSUANCE_REQUESTS[request_id] = {
            'request_id': request_id,
            'hospital_id': hospital_id,
            'hospital_did': data['hospital_did'],
            'hospital_name': hospital['name'],
            'credential_type': data['credential_type'],
            'schema_data': data['schema_data'],
            'status': 'pending',
            'submitted_at': datetime.now().isoformat(),
            'decision_date': None,
            'decision_reason': None
        }
        
        logging.info(f"Получена заявка на выпуск VC: {request_id} от {hospital['name']}")
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'message': 'Заявка принята на рассмотрение',
            'estimated_review_time': '3 рабочих дня'
        }), 200
        
    except Exception as e:
        logging.error(f"Ошибка при обработке заявки на выпуск VC: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

@app.route('/credential-issuance-requests', methods=['GET'])
def get_credential_issuance_requests():
    """Получение списка всех заявок на выпуск VC"""
    requests_list = list(CREDENTIAL_ISSUANCE_REQUESTS.values())
    return jsonify(requests_list), 200

@app.route('/credential-issuance-requests/<request_id>', methods=['GET'])
def get_credential_request_details(request_id):
    """Получение детальной информации о заявке"""
    if request_id not in CREDENTIAL_ISSUANCE_REQUESTS:
        return jsonify({"error": "Заявка не найдена"}), 404
    
    return jsonify(CREDENTIAL_ISSUANCE_REQUESTS[request_id]), 200

@app.route('/credential-issuance-requests/<request_id>/approve', methods=['POST'])
def approve_credential_request(request_id):
    """Одобрение заявки на выпуск VC"""
    if request_id not in CREDENTIAL_ISSUANCE_REQUESTS:
        return jsonify({"error": "Заявка не найдена"}), 404
    
    request_data = CREDENTIAL_ISSUANCE_REQUESTS[request_id]
    
    # Проверка, что учреждение существует
    hospital_id = request_data['hospital_id']
    if hospital_id not in REGISTERED_INSTITUTIONS:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    # Получение причины одобрения (опционально)
    decision_reason = request.json.get('reason', 'Одобрено регулятором')
    
    # Обновление статуса заявки
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['status'] = 'approved'
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['decision_date'] = datetime.now().isoformat()
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['decision_reason'] = decision_reason
    
    # Добавление типа VC в список разрешенных для учреждения
    credential_type = request_data['credential_type']
    if credential_type not in REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials']:
        REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials'].append(credential_type)
        REGISTERED_INSTITUTIONS[hospital_id]['last_updated'] = datetime.now().isoformat()
    
    logging.info(f"Заявка {request_id} одобрена. Учреждение {hospital_id} теперь может выпускать {credential_type}")
    
    # Отправка уведомления больнице (в реальной системе через webhook или сообщение)
    notify_hospital(
        hospital_id,
        'CREDENTIAL_ISSUANCE_APPROVED',
        {
            'request_id': request_id,
            'credential_type': credential_type,
            'decision_reason': decision_reason
        }
    )
    
    return jsonify({
        'success': True,
        'message': 'Заявка одобрена',
        'request_id': request_id,
        'credential_type': credential_type
    }), 200

@app.route('/credential-issuance-requests/<request_id>/reject', methods=['POST'])
def reject_credential_request(request_id):
    """Отклонение заявки на выпуск VC"""
    if request_id not in CREDENTIAL_ISSUANCE_REQUESTS:
        return jsonify({"error": "Заявка не найдена"}), 404
    
    # Получение причины отклонения
    decision_reason = request.json.get('reason')
    if not decision_reason:
        return jsonify({"error": "Требуется указать причину отклонения"}), 400
    
    # Обновление статуса заявки
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['status'] = 'rejected'
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['decision_date'] = datetime.now().isoformat()
    CREDENTIAL_ISSUANCE_REQUESTS[request_id]['decision_reason'] = decision_reason
    
    logging.info(f"Заявка {request_id} отклонена. Причина: {decision_reason}")
    
    # Отправка уведомления больнице
    request_data = CREDENTIAL_ISSUANCE_REQUESTS[request_id]
    notify_hospital(
        request_data['hospital_id'],
        'CREDENTIAL_ISSUANCE_REJECTED',
        {
            'request_id': request_id,
            'decision_reason': decision_reason
        }
    )
    
    return jsonify({
        'success': True,
        'message': 'Заявка отклонена',
        'request_id': request_id
    }), 200

@app.route('/request-credential-modification', methods=['POST'])
def request_credential_modification():
    """
    Обработка запроса на изменение списка выпускаемых VC
    (Требование 4)
    """
    try:
        data = request.json
        
        # Валидация
        required_fields = ['institution_id', 'action', 'credential_types']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
        
        institution_id = data['institution_id']
        action = data['action']
        credential_types = data['credential_types']
        
        if institution_id not in REGISTERED_INSTITUTIONS:
            return jsonify({"error": "Учреждение не найдено"}), 404
        
        # Проверка действия
        if action not in ['ADD', 'REMOVE']:
            return jsonify({"error": "Недопустимое действие"}), 400
        
        # Проверка типов VC
        for cred_type in credential_types:
            if cred_type not in APPROVED_CREDENTIAL_TYPES:
                return jsonify({"error": f"Недопустимый тип VC: {cred_type}"}), 400
        
        # Создание заявки на изменение
        modification_id = str(uuid.uuid4())
        CREDENTIAL_MODIFICATION_REQUESTS[modification_id] = {
            'modification_id': modification_id,
            'hospital_id': institution_id,
            'hospital_name': REGISTERED_INSTITUTIONS[institution_id]['name'],
            'action': action,
            'credential_types': credential_types,
            'status': 'pending',
            'submitted_at': datetime.now().isoformat(),
            'decision_date': None,
            'decision_reason': None
        }
        
        logging.info(f"Получен запрос на изменение VC: {modification_id} от {institution_id}")
        
        return jsonify({
            'success': True,
            'modification_id': modification_id,
            'message': 'Запрос на изменение принят на рассмотрение'
        }), 200
        
    except Exception as e:
        logging.error(f"Ошибка при обработке запроса на изменение VC: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

@app.route('/credential-modification-requests', methods=['GET'])
def get_credential_modification_requests():
    """Получение списка всех запросов на изменение VC"""
    requests_list = list(CREDENTIAL_MODIFICATION_REQUESTS.values())
    return jsonify(requests_list), 200

@app.route('/credential-modification-requests/<modification_id>/approve', methods=['POST'])
def approve_modification_request(modification_id):
    """Одобрение запроса на изменение VC"""
    if modification_id not in CREDENTIAL_MODIFICATION_REQUESTS:
        return jsonify({"error": "Запрос не найден"}), 404
    
    request_data = CREDENTIAL_MODIFICATION_REQUESTS[modification_id]
    hospital_id = request_data['hospital_id']
    action = request_data['action']
    credential_types = request_data['credential_types']
    
    # Применение изменений
    if action == 'ADD':
        for cred_type in credential_types:
            if cred_type not in REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials']:
                REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials'].append(cred_type)
    elif action == 'REMOVE':
        REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials'] = [
            ct for ct in REGISTERED_INSTITUTIONS[hospital_id]['allowed_credentials']
            if ct not in credential_types
        ]
    
    # Обновление статуса запроса
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['status'] = 'approved'
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['decision_date'] = datetime.now().isoformat()
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['decision_reason'] = 'Одобрено регулятором'
    
    REGISTERED_INSTITUTIONS[hospital_id]['last_updated'] = datetime.now().isoformat()
    
    logging.info(f"Запрос на изменение {modification_id} одобрен")
    
    return jsonify({
        'success': True,
        'message': 'Запрос на изменение одобрен',
        'modification_id': modification_id
    }), 200

@app.route('/credential-modification-requests/<modification_id>/reject', methods=['POST'])
def reject_modification_request(modification_id):
    """Отклонение запроса на изменение VC"""
    if modification_id not in CREDENTIAL_MODIFICATION_REQUESTS:
        return jsonify({"error": "Запрос не найден"}), 404
    
    decision_reason = request.json.get('reason')
    if not decision_reason:
        return jsonify({"error": "Требуется указать причину отклонения"}), 400
    
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['status'] = 'rejected'
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['decision_date'] = datetime.now().isoformat()
    CREDENTIAL_MODIFICATION_REQUESTS[modification_id]['decision_reason'] = decision_reason
    
    logging.info(f"Запрос на изменение {modification_id} отклонен")
    
    return jsonify({
        'success': True,
        'message': 'Запрос на изменение отклонен',
        'modification_id': modification_id
    }), 200

@app.route('/institutions/<institution_id>/suspend', methods=['POST'])
def suspend_institution(institution_id):
    """Приостановка деятельности учреждения"""
    if institution_id not in REGISTERED_INSTITUTIONS:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    reason = request.json.get('reason', 'Приостановлено регулятором')
    
    REGISTERED_INSTITUTIONS[institution_id]['status'] = 'SUSPENDED'
    REGISTERED_INSTITUTIONS[institution_id]['suspension_reason'] = reason
    REGISTERED_INSTITUTIONS[institution_id]['suspended_at'] = datetime.now().isoformat()
    REGISTERED_INSTITUTIONS[institution_id]['last_updated'] = datetime.now().isoformat()
    
    logging.warning(f"Учреждение {institution_id} приостановлено. Причина: {reason}")
    
    return jsonify({
        'success': True,
        'message': 'Учреждение приостановлено',
        'institution_id': institution_id
    }), 200

@app.route('/institutions/<institution_id>/activate', methods=['POST'])
def activate_institution(institution_id):
    """Активация приостановленного учреждения"""
    if institution_id not in REGISTERED_INSTITUTIONS:
        return jsonify({"error": "Учреждение не найдено"}), 404
    
    REGISTERED_INSTITUTIONS[institution_id]['status'] = 'ACTIVE'
    if 'suspension_reason' in REGISTERED_INSTITUTIONS[institution_id]:
        del REGISTERED_INSTITUTIONS[institution_id]['suspension_reason']
    if 'suspended_at' in REGISTERED_INSTITUTIONS[institution_id]:
        del REGISTERED_INSTITUTIONS[institution_id]['suspended_at']
    
    REGISTERED_INSTITUTIONS[institution_id]['last_updated'] = datetime.now().isoformat()
    
    logging.info(f"Учреждение {institution_id} активировано")
    
    return jsonify({
        'success': True,
        'message': 'Учреждение активировано',
        'institution_id': institution_id
    }), 200

def notify_hospital(hospital_id, notification_type, data):
    """
    Отправка уведомления больнице
    В реальной системе это может быть webhook или сообщение через агента
    """
    try:
        if hospital_id in REGISTERED_INSTITUTIONS:
            hospital = REGISTERED_INSTITUTIONS[hospital_id]
            logging.info(f"Уведомление отправлено {hospital['name']}: {notification_type}")
            
            # Здесь можно добавить реальную отправку уведомления
            # Например, через административный API агента больницы
            
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления: {e}")

@app.route('/verify-institution-permission', methods=['POST'])
def verify_institution_permission():
    """
    Проверка разрешений учреждения на выпуск определенного типа VC
    Используется больницами перед отправкой транзакции в блокчейн
    """
    try:
        data = request.json
        hospital_did = data.get('hospital_did')
        credential_type = data.get('credential_type')
        
        if not hospital_did or not credential_type:
            return jsonify({"error": "Отсутствуют обязательные поля"}), 400
        
        # Поиск учреждения
        hospital = None
        for inst_data in REGISTERED_INSTITUTIONS.values():
            if inst_data['did'] == hospital_did:
                hospital = inst_data
                break
        
        if not hospital:
            return jsonify({
                'authorized': False,
                'reason': 'Учреждение не зарегистрировано'
            }), 200
        
        # Проверка статуса учреждения
        if hospital['status'] != 'ACTIVE':
            return jsonify({
                'authorized': False,
                'reason': 'Учреждение приостановлено'
            }), 200
        
        # Проверка разрешения на выпуск VC
        if credential_type in hospital['allowed_credentials']:
            return jsonify({
                'authorized': True,
                'institution_name': hospital['name'],
                'credential_type': credential_type,
                'message': 'Учреждение имеет право выпускать данный тип документов'
            }), 200
        else:
            return jsonify({
                'authorized': False,
                'reason': 'Учреждение не имеет разрешения на выпуск данного типа документов',
                'allowed_credentials': hospital['allowed_credentials']
            }), 200
            
    except Exception as e:
        logging.error(f"Ошибка при проверке разрешений: {str(e)}")
        return jsonify({"error": f"Внутренняя ошибка: {str(e)}"}), 500

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/regulator.log'),
            logging.StreamHandler()
        ]
    )
    
    print("🏛️  Запуск контроллера государственного регулятора...")
    print(f"📊 Панель управления доступна по адресу: http://localhost:8070")
    print(f"🔗 Административный API агента: {AGENT_ADMIN_URL}")
    
    # Инициализация тестовых данных
    REGISTERED_INSTITUTIONS['test_hospital_001'] = {
        'institution_id': 'test_hospital_001',
        'name': 'Городская больница №1',
        'license_number': 'MED-001-2023',
        'type': 'HOSPITAL',
        'did': 'did:sov:test_hospital_did_001',
        'address': 'г. Москва, ул. Медицинская, д. 1',
        'status': 'ACTIVE',
        'allowed_credentials': ['MEDICAL_RECORD'],
        'registered_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }
    
    app.run(host='0.0.0.0', port=8070, debug=True)
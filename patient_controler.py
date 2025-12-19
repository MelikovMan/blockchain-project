import requests
import json
import logging
import time
import os
import secrets
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# =========================
# Конфигурация ACA-Py
# =========================
AGENT_ADMIN_URL = "http://localhost:8031"
AGENT_API_KEY = "patient-admin-key-456"
HEADERS = {"X-API-Key": AGENT_API_KEY, "Content-Type": "application/json"}

# =========================
# In-memory хранилища (demo)
# =========================
PENDING_OOB_INVITES = {}        # invite_id -> {"invitation": {...}, "created_at": epoch}
PENDING_PROOF_REQUESTS = {}     # pres_ex_id -> {"presentation_request": {...}|None, "created_at": epoch, "connection_id": str|None}

INVITE_TTL_SEC = 60 * 60        # 1 час
PROOF_TTL_SEC = 60 * 60         # 1 час


def _new_id():
    return secrets.token_urlsafe(12)


def _cleanup_oob_invites():
    now = int(time.time())
    to_del = [k for k, v in PENDING_OOB_INVITES.items() if now - v.get("created_at", now) > INVITE_TTL_SEC]
    for k in to_del:
        PENDING_OOB_INVITES.pop(k, None)


def _cleanup_proof_requests():
    now = int(time.time())
    to_del = [k for k, v in PENDING_PROOF_REQUESTS.items() if now - v.get("created_at", now) > PROOF_TTL_SEC]
    for k in to_del:
        PENDING_PROOF_REQUESTS.pop(k, None)


def _invite_summary(inv):
    label = inv.get("label") or inv.get("goal") or inv.get("goal_code") or "приглашение"
    service = ""
    try:
        services = inv.get("services") or []
        if isinstance(services, list) and services:
            service = str(services[0])[:160]
    except Exception:
        service = ""
    return label, service


def _safe_get(url):
    try:
        return requests.get(url, headers=HEADERS, timeout=10)
    except Exception as e:
        logging.error(f"GET {url} failed: {e}")

        class Dummy:
            status_code = 0
            text = str(e)

            def json(self):
                return {}

        return Dummy()


def _safe_post(url, body=None):
    try:
        return requests.post(url, headers=HEADERS, json=(body or {}), timeout=10)
    except Exception as e:
        logging.error(f"POST {url} failed: {e}")

        class Dummy:
            status_code = 0
            text = str(e)

            def json(self):
                return {}

        return Dummy()


def _safe_delete(url):
    try:
        return requests.delete(url, headers=HEADERS, timeout=10)
    except Exception as e:
        logging.error(f"DELETE {url} failed: {e}")

        class Dummy:
            status_code = 0
            text = str(e)

        return Dummy()


# =========================
# UI (структура контента сохранена, стили вынесены в /static/patient.css)
# =========================
PATIENT_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Мой Медицинский Кошелек</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/patient.css">
</head>
<body>

  

  <!-- Синяя панель-иконки -->
  <div class="tabbar">
    <div class="tabbar__inner">
    
      <div class="tab active">✚<span>Здоровье</span></div>
      
    </div>
  </div>

  <main class="stage">
    <!-- “Окно” как на скрине -->
    <section class="modal">
      <div class="modal__head">
        <!-- ваш исходный контент (h2) оставлен -->
        <h2>Привет, {{ patient_name }}!</h2>
      
      </div>

      <div class="modal__body">
        <!-- ЛЕВАЯ КОЛОНКА -->
        <div class="col">
          <div class="block">
            <h3>1. Получить приглашение от больницы</h3>
            <p><b>Важно:</b> приглашение будет принято только после подтверждения пользователем (п. 5.1).</p>
            <form action="/receive-invitation" method="post">
              <textarea name="invitation" placeholder="Вставьте приглашение (JSON)..." rows="7" cols="70"></textarea><br>
              <button type="submit">Дальше</button>
            </form>
          </div>

          <hr>

          <div class="block">
            <h3>1.1 Ожидающие запросы на соединение (нужно ваше согласие)</h3>
            <button onclick="fetchPendingConnections()">Обновить ожидающие</button>
            <div id="pendingConnections"></div>
          </div>

          <hr>

          <div class="block">
            <h3>1.2 Ожидающие предложения справок / VC (нужно ваше согласие)</h3>
            <button onclick="fetchPendingCreds()">Обновить предложения</button>
            <div id="pendingCreds"></div>
          </div>

          <hr>

          <div class="block">
            <h3>1.3 Запросы на медицинские данные (НЕ экстренные) — нужно ваше подтверждение</h3>
            <button onclick="fetchPendingProofs()">Обновить запросы</button>
            <div id="pendingProofs"></div>
          </div>
        </div>

        <!-- ПРАВАЯ КОЛОНКА -->
        <div class="col">
          <div class="block">
            <h3>2. Мои текущие соединения</h3>
            <button onclick="fetchConnections()">Обновить список</button>
            <div id="connections"></div>
          </div>

          <hr>

          <div class="block">
            <h3>3. Мои медицинские справки (в кошельке)</h3>
            <button onclick="fetchCredentials()">Показать справки</button>
            <div id="credentials"></div>
          </div>

          <hr>

          <div class="block">
            <h3>4. Экстренный доступ</h3>
            <p>Экстренные proof-запросы обрабатываются автоматически через webhook (см. logs/patient.log).</p>
          </div>
        </div>
      </div>
    </section>
  </main>

<script>
async function fetchPendingConnections() {
  const r = await fetch('/pending-connections');
  const items = await r.json();
  const el = document.getElementById('pendingConnections');

  if (!items.length) {
    el.innerHTML = "<p class='muted'>Нет ожидающих запросов.</p>";
    return;
  }

  el.innerHTML = items.map(c => `
    <div class="card">
      <div class="card__row"><b>ID:</b> <code>${c.id}</code></div>
      <div class="card__row"><b>Кто:</b> ${c.label}</div>
      <div class="card__row"><b>state:</b> ${c.state || ''} <b>rfc23_state:</b> ${c.rfc23_state || ''}</div>
      <div class="actions">
        <button onclick="acceptConn('${c.id}')">Принять</button>
        <button class="ghost" onclick="rejectConn('${c.id}')">Отклонить</button>
      </div>
    </div>
  `).join('');
}

async function acceptConn(id) {
  const r = await fetch(`/connections/${id}/accept`, {method:'POST'});
  alert(await r.text());
  fetchPendingConnections();
  fetchConnections();
}

async function rejectConn(id) {
  const r = await fetch(`/connections/${id}/reject`, {method:'POST'});
  alert(await r.text());
  fetchPendingConnections();
  fetchConnections();
}

async function fetchPendingCreds() {
  const r = await fetch('/pending-credential-offers');
  const items = await r.json();
  const el = document.getElementById('pendingCreds');

  if (!items.length) {
    el.innerHTML = "<p class='muted'>Нет ожидающих предложений VC.</p>";
    return;
  }

  el.innerHTML = items.map(x => `
    <div class="card">
      <div class="card__row"><b>cred_ex_id:</b> <code>${x.cred_ex_id}</code></div>
      <div class="card__row"><b>protocol:</b> ${x.protocol}</div>
      <div class="card__row"><b>state:</b> ${x.state}</div>
      <div class="card__row"><b>issuer:</b> ${x.issuer || '—'}</div>
      <div class="card__row"><b>schema_id:</b> <span class="mono">${x.schema_id || '—'}</span></div>
      <div class="card__row"><b>cred_def_id:</b> <span class="mono">${x.cred_def_id || '—'}</span></div>
      <div class="actions">
        <button onclick="acceptCred('${x.cred_ex_id}', '${x.protocol}')">Принять</button>
        <button class="ghost" onclick="rejectCred('${x.cred_ex_id}', '${x.protocol}')">Отклонить</button>
      </div>
    </div>
  `).join('');
}

async function acceptCred(id, protocol) {
  const r = await fetch(`/credential-offers/${id}/accept`, {
    method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({protocol})
  });
  alert(await r.text());
  fetchPendingCreds();
  fetchCredentials();
}

async function rejectCred(id, protocol) {
  const r = await fetch(`/credential-offers/${id}/reject`, {
    method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({protocol})
  });
  alert(await r.text());
  fetchPendingCreds();
}

async function fetchPendingProofs() {
  const r = await fetch('/pending-proof-requests');
  const items = await r.json();
  const el = document.getElementById('pendingProofs');

  if (!items.length) {
    el.innerHTML = "<p class='muted'>Нет неэкстренных запросов.</p>";
    return;
  }

  el.innerHTML = items.map(p => `
    <div class="card">
      <div class="card__row"><b>pres_ex_id:</b> <code>${p.pres_ex_id}</code></div>
      <div class="card__row"><b>connection_id:</b> <span class="mono">${p.connection_id || '—'}</span></div>
      <div class="card__row"><b>name:</b> ${p.name || '—'}</div>
      <details>
        <summary>Запрошенные атрибуты/предикаты</summary>
        <pre>${JSON.stringify(p.requested || {}, null, 2)}</pre>
      </details>
      <div class="actions">
        <button onclick="acceptProof('${p.pres_ex_id}')">Разрешить (отправить)</button>
        <button class="ghost" onclick="rejectProof('${p.pres_ex_id}')">Отклонить</button>
      </div>
    </div>
  `).join('');
}

async function acceptProof(id) {
  const r = await fetch(`/proof-requests/${id}/accept`, {method:'POST'});
  alert(await r.text());
  fetchPendingProofs();
}

async function rejectProof(id) {
  const r = await fetch(`/proof-requests/${id}/reject`, {method:'POST'});
  alert(await r.text());
  fetchPendingProofs();
}

async function fetchConnections() {
  const r = await fetch('/connections');
  const j = await r.json();
  document.getElementById('connections').innerHTML = '<pre>' + JSON.stringify(j,null,2) + '</pre>';
}

async function fetchCredentials() {
  const r = await fetch('/credentials');
  const j = await r.json();

  if (!Array.isArray(j) || j.length === 0) {
    document.getElementById('credentials').innerHTML = "<p class='muted'>Справок нет.</p>";
    return;
  }

  const html = j.map(c => `
    <div class="card">
      <div class="card__row"><b>cred_id:</b> <a href="/credentials/${c.cred_id}" target="_blank"><code>${c.cred_id}</code></a></div>
      <div class="card__row"><b>schema_id:</b> <span class="mono">${c.schema_id || '—'}</span></div>
      <div class="card__row"><b>cred_def_id:</b> <span class="mono">${c.cred_def_id || '—'}</span></div>
      <details>
        <summary>attrs</summary>
        <pre>${JSON.stringify(c.attrs || {}, null, 2)}</pre>
      </details>
    </div>
  `).join('');

  document.getElementById('credentials').innerHTML = html;
}
</script>

</body>
</html>
"""



CONFIRM_INVITE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Подтверждение приглашения</title>
  <meta charset="utf-8">
  <link rel="stylesheet" href="/static/patient.css">
</head>
<body>
  <h2>Подтверждение приглашения</h2>

  <div class="card">
    <div class="card__row"><b>Что вы принимаете:</b> {{ label }}</div>
    {% if service %}
      <div class="card__row"><b>Service:</b> <span class="mono">{{ service }}</span></div>
    {% endif %}
    <p class="muted">Если это не ваша больница — нажмите «Отклонить».</p>

    <div class="actions">
      <form action="/confirm-invitation/{{ invite_id }}" method="post" style="display:inline;">
        <button type="submit">Подтвердить и принять</button>
      </form>

      <form action="/reject-invitation/{{ invite_id }}" method="post" style="display:inline;">
        <button class="ghost" type="submit">Отклонить</button>
      </form>
    </div>
  </div>

  <p><a href="/">Назад</a></p>
</body>
</html>
"""


@app.route("/")
def patient_dashboard():
    return render_template_string(PATIENT_UI_HTML, patient_name="Иван")


# =========================
# Webhooks от ACA-Py
# =========================
@app.route("/webhooks/topic/<topic>/", methods=["POST"])
def handle_webhooks(topic):
    message = request.json or {}
    logging.info(f"[Webhook] topic={topic} payload={json.dumps(message, ensure_ascii=False)}")

    # 5.1: НЕ автопринимаем соединение
    if topic == "connections":
        state = message.get("state")
        connection_id = message.get("connection_id")
        if state == "request-received":
            logging.warning(f"⚠️ Входящий запрос на соединение. Автопринятие отключено. connection_id={connection_id}")

    # 5.2: НЕ автопринимаем credential offer — только по согласию
    elif topic == "issue_credential_v2_0":
        state = message.get("state")
        cred_ex_id = message.get("cred_ex_id")
        if state == "offer-received":
            logging.warning(f"⚠️ Получен credential offer (v2). Ждём согласие пользователя. cred_ex_id={cred_ex_id}")
        elif state == "credential-received":
            logging.info(f"📥 Credential получен (v2). Сохраняем в wallet. cred_ex_id={cred_ex_id}")
            r = _safe_post(f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}/store", {})
            if r.status_code != 200:
                logging.error(f"store(v2) error cred_ex_id={cred_ex_id}: {r.status_code} {getattr(r,'text','')}")

    elif topic == "issue_credential":
        state = message.get("state")
        cred_ex_id = message.get("cred_ex_id") or message.get("credential_exchange_id")
        if state == "offer_received":
            logging.warning(f"⚠️ Получен credential offer (v1). Ждём согласие пользователя. cred_ex_id={cred_ex_id}")
        elif state == "credential_received":
            logging.info(f"📥 Credential получен (v1). Сохраняем в wallet. cred_ex_id={cred_ex_id}")
            r = _safe_post(f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}/store", {})
            if r.status_code != 200:
                logging.error(f"store(v1) error cred_ex_id={cred_ex_id}: {r.status_code} {getattr(r,'text','')}")

    # 5.4: present-proof НЕ экстренный — только по подтверждению пользователя
    elif topic == "present_proof_v2_0":
        state = message.get("state")
        pres_ex_id = message.get("pres_ex_id")
        connection_id = message.get("connection_id")

        if state == "request-received":
            indy_req = None
            try:
                indy_req = message.get("by_format", {}).get("pres_request", {}).get("indy")
            except Exception:
                indy_req = None

            if indy_req is None:
                rr = _safe_get(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}")
                if rr.status_code == 200:
                    indy_req = rr.json().get("by_format", {}).get("pres_request", {}).get("indy")

            if indy_req is None:
                logging.error(f"❌ Не удалось получить pres_request для pres_ex_id={pres_ex_id}")
                return jsonify({"status": "error"}), 400

            if is_emergency_request(indy_req):
                emergency_response = {
                    "indy": {
                        "requested_attributes": {
                            "blood_attr": {"cred_id": get_credential_id(pres_ex_id), "revealed": True}
                        },
                        "requested_predicates": {},
                        "self_attested_attributes": {},
                    }
                }
                send = _safe_post(
                    f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/send-presentation",
                    emergency_response,
                )
                if send.status_code != 200:
                    logging.error(
                        f"send-presentation emergency error pres_ex_id={pres_ex_id}: {send.status_code} {getattr(send,'text','')}"
                    )
                logging.warning("⚠️ Автоматически предоставлены экстренные данные (emergency).")
            else:
                _cleanup_proof_requests()
                PENDING_PROOF_REQUESTS[pres_ex_id] = {
                    "presentation_request": indy_req,
                    "created_at": int(time.time()),
                    "connection_id": connection_id,
                }
                logging.warning(f"📝 Неэкстренный запрос данных: ждём подтверждение пользователя. pres_ex_id={pres_ex_id}")

        elif state in ("done", "presentation-sent", "verified", "abandoned"):
            PENDING_PROOF_REQUESTS.pop(pres_ex_id, None)

    return jsonify({"status": "ok"}), 200


def is_emergency_request(presentation_request):
    return "emergency" in (presentation_request.get("name", "") or "").lower()


def get_credential_id(pres_ex_id):
    creds_resp = _safe_get(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/credentials")
    if creds_resp.status_code != 200:
        logging.error(f"Ошибка получения credentials pres_ex_id={pres_ex_id}: {creds_resp.status_code} {creds_resp.text}")
        return None
    data = creds_resp.json() or []
    if not data:
        logging.error(f"Не найдены credentials pres_ex_id={pres_ex_id}")
        return None
    return data[0].get("cred_info", {}).get("referent")


# =========================
# 5.1 Приём out-of-band invitation ТОЛЬКО по согласию пользователя
# =========================
@app.route("/receive-invitation", methods=["POST"])
def receive_invitation():
    _cleanup_oob_invites()

    invitation_json = request.form.get("invitation")
    if not invitation_json:
        return "❌ Неверный формат приглашения", 400

    try:
        invitation = json.loads(invitation_json)
    except Exception:
        return "❌ Неверный формат приглашения", 400

    invite_id = _new_id()
    PENDING_OOB_INVITES[invite_id] = {"invitation": invitation, "created_at": int(time.time())}

    label, service = _invite_summary(invitation)
    return render_template_string(CONFIRM_INVITE_HTML, invite_id=invite_id, label=label, service=service)


@app.route("/confirm-invitation/<invite_id>", methods=["POST"])
def confirm_invitation(invite_id):
    _cleanup_oob_invites()

    rec = PENDING_OOB_INVITES.pop(invite_id, None)
    if not rec:
        return "❌ Приглашение не найдено или истекло", 404

    invitation = rec["invitation"]
    resp = _safe_post(f"{AGENT_ADMIN_URL}/out-of-band/receive-invitation", invitation)

    if resp.status_code == 200:
        return "✅ Приглашение подтверждено пользователем. Соединение устанавливается."
    logging.error(f"Ошибка receive-invitation: {resp.status_code} {getattr(resp,'text','')}")
    return "❌ Ошибка при принятии приглашения", 500


@app.route("/reject-invitation/<invite_id>", methods=["POST"])
def reject_invitation(invite_id):
    _cleanup_oob_invites()
    PENDING_OOB_INVITES.pop(invite_id, None)
    return "⛔ Приглашение отклонено пользователем"


# =========================
# Пункт 1: "ожидающие запросы на соединение" + accept/reject
# =========================
@app.route("/pending-connections", methods=["GET"])
def get_pending_connections():
    resp = _safe_get(f"{AGENT_ADMIN_URL}/connections")
    if resp.status_code != 200:
        return jsonify([])

    results = resp.json().get("results", [])
    pending = []

    for c in results:
        state = c.get("state", "")
        rfc23_state = c.get("rfc23_state", "")
        if state in ("request", "request-received") or rfc23_state == "request-received":
            pending.append(
                {
                    "id": c.get("connection_id"),
                    "label": c.get("their_label", "Неизвестный"),
                    "state": state,
                    "rfc23_state": rfc23_state,
                }
            )
    return jsonify(pending)


@app.route("/connections/<connection_id>/accept", methods=["POST"])
def accept_connection_request(connection_id):
    resp = _safe_post(f"{AGENT_ADMIN_URL}/didexchange/{connection_id}/accept-request", {})
    if resp.status_code == 200:
        return "✅ Запрос на соединение принят"
    logging.error(f"accept-request error connection_id={connection_id}: {resp.status_code} {getattr(resp,'text','')}")
    return f"❌ Ошибка accept-request: {resp.status_code}", 400


@app.route("/connections/<connection_id>/reject", methods=["POST"])
def reject_connection_request(connection_id):
    resp = _safe_post(f"{AGENT_ADMIN_URL}/didexchange/{connection_id}/reject", {"reason": "rejected by patient"})
    if resp.status_code == 200:
        return "⛔ Запрос на соединение отклонён"
    logging.error(f"reject error connection_id={connection_id}: {resp.status_code} {getattr(resp,'text','')}")
    return f"❌ Ошибка reject: {resp.status_code}", 400


# =========================
# 5.2 Ожидающие VC offers + accept/reject (send-request по согласию)
# =========================
@app.route("/pending-credential-offers", methods=["GET"])
def pending_credential_offers():
    out = []

    v2 = _safe_get(f"{AGENT_ADMIN_URL}/issue-credential-2.0/records")
    if v2.status_code == 200:
        data = v2.json()
        if isinstance(data.get("results"), list):
            for rec_nested in data["results"]:
                rec = rec_nested["cred_ex_record"]
                if rec.get("state") == "offer-received":
                    out.append(
                        {
                            "protocol": "v2",
                            "cred_ex_id": rec.get("cred_ex_id"),
                            "state": rec.get("state"),
                            "issuer": rec.get("their_label") or rec.get("connection_id"),
                            "schema_id": rec.get("schema_id"),
                            "cred_def_id": rec.get("cred_def_id"),
                        }
                    )

    v1 = _safe_get(f"{AGENT_ADMIN_URL}/issue-credential/records")
    if v1.status_code == 200:
        data = v1.json()
        if isinstance(data.get("results"), list):
            for rec in data["results"]:
                if rec.get("state") == "offer_received":
                    out.append(
                        {
                            "protocol": "v1",
                            "cred_ex_id": rec.get("cred_ex_id") or rec.get("credential_exchange_id"),
                            "state": rec.get("state"),
                            "issuer": rec.get("their_label") or rec.get("connection_id"),
                            "schema_id": rec.get("schema_id"),
                            "cred_def_id": rec.get("cred_def_id"),
                        }
                    )

    return jsonify(out)


@app.route("/credential-offers/<cred_ex_id>/accept", methods=["POST"])
def accept_credential_offer(cred_ex_id):
    data = request.json or {}
    protocol = data.get("protocol")

    if protocol in (None, "", "v2"):
        r = _safe_post(f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}/send-request", {})
        if r.status_code == 200:
            return "✅ VC offer принят (v2): отправлен send-request"
        if protocol == "v2":
            return f"❌ Ошибка send-request (v2): {r.status_code}", 400

    r = _safe_post(f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}/send-request", {})
    if r.status_code == 200:
        return "✅ VC offer принят (v1): отправлен send-request"
    return f"❌ Ошибка send-request (v1): {r.status_code}", 400


@app.route("/credential-offers/<cred_ex_id>/reject", methods=["POST"])
def reject_credential_offer(cred_ex_id):
    data = request.json or {}
    protocol = data.get("protocol")
    body = {"description": "rejected by patient"}

    if protocol in (None, "", "v2"):
        _safe_post(f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}/problem-report", body)
        _safe_delete(f"{AGENT_ADMIN_URL}/issue-credential-2.0/records/{cred_ex_id}")
        return "⛔ VC offer отклонён (v2)"

    _safe_post(f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}/problem-report", body)
    _safe_delete(f"{AGENT_ADMIN_URL}/issue-credential/records/{cred_ex_id}")
    return "⛔ VC offer отклонён (v1)"


# =========================
# 5.4 Неэкстренные proof requests: список + accept/reject
# =========================
@app.route("/pending-proof-requests", methods=["GET"])
def pending_proof_requests():
    _cleanup_proof_requests()

    out = []
    for pres_ex_id, rec in PENDING_PROOF_REQUESTS.items():
        indy_req = rec.get("presentation_request") or {}
        requested = {
            "requested_attributes": list((indy_req.get("requested_attributes") or {}).keys()),
            "requested_predicates": list((indy_req.get("requested_predicates") or {}).keys()),
        }
        out.append({
            "pres_ex_id": pres_ex_id,
            "connection_id": rec.get("connection_id"),
            "name": indy_req.get("name"),
            "requested": requested,
        })
    return jsonify(out)


def _build_indy_presentation(pres_ex_id, indy_req):
    creds_resp = _safe_get(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/credentials")
    if creds_resp.status_code != 200:
        return None, f"❌ Не удалось получить список credentials: {creds_resp.status_code}"

    creds = creds_resp.json() or []
    if not isinstance(creds, list) or len(creds) == 0:
        return None, "❌ Нет подходящих credentials для этого запроса"

    ref_to_cred = {}
    for item in creds:
        pres_refs = item.get("presentation_referents") or []
        cred_id = (item.get("cred_info") or {}).get("referent")
        if not cred_id:
            continue
        for r in pres_refs:
            if r not in ref_to_cred:
                ref_to_cred[r] = cred_id

    requested_attributes = {}
    for ref in (indy_req.get("requested_attributes") or {}).keys():
        cred_id = ref_to_cred.get(ref)
        if not cred_id:
            return None, f"❌ Не найден credential для атрибута referent={ref}"
        requested_attributes[ref] = {"cred_id": cred_id, "revealed": True}

    requested_predicates = {}
    for ref in (indy_req.get("requested_predicates") or {}).keys():
        cred_id = ref_to_cred.get(ref)
        if not cred_id:
            return None, f"❌ Не найден credential для предиката referent={ref}"
        requested_predicates[ref] = {"cred_id": cred_id}

    pres = {
        "indy": {
            "requested_attributes": requested_attributes,
            "requested_predicates": requested_predicates,
            "self_attested_attributes": {},
        }
    }
    return pres, None


@app.route("/proof-requests/<pres_ex_id>/accept", methods=["POST"])
def accept_proof_request(pres_ex_id):
    _cleanup_proof_requests()

    rec = PENDING_PROOF_REQUESTS.get(pres_ex_id)
    indy_req = rec.get("presentation_request") if rec else None

    if indy_req is None:
        rr = _safe_get(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}")
        if rr.status_code != 200:
            return f"❌ Не удалось получить proof record: {rr.status_code}", 400
        indy_req = rr.json().get("by_format", {}).get("pres_request", {}).get("indy")

    if indy_req is None:
        return "❌ Не удалось получить indy pres_request", 400

    if is_emergency_request(indy_req):
        return "❌ Это emergency-запрос (обрабатывается автоматически), ручное подтверждение не требуется", 400

    pres, err = _build_indy_presentation(pres_ex_id, indy_req)
    if err:
        return err, 400

    send = _safe_post(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/send-presentation", pres)
    if send.status_code != 200:
        return f"❌ Ошибка send-presentation: {send.status_code} {getattr(send,'text','')}", 400

    PENDING_PROOF_REQUESTS.pop(pres_ex_id, None)
    return "✅ Презентация отправлена (неэкстренный запрос подтверждён пользователем)"


@app.route("/proof-requests/<pres_ex_id>/reject", methods=["POST"])
def reject_proof_request(pres_ex_id):
    PENDING_PROOF_REQUESTS.pop(pres_ex_id, None)

    _safe_post(
        f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}/problem-report",
        {"description": "rejected by patient"},
    )
    _safe_delete(f"{AGENT_ADMIN_URL}/present-proof-2.0/records/{pres_ex_id}")

    return "⛔ Запрос данных отклонён пользователем"


# =========================
# 5.3 Просмотр credentials (полный список + деталка)
# =========================
@app.route("/credentials", methods=["GET"])
def get_credentials():
    resp = _safe_get(f"{AGENT_ADMIN_URL}/credentials")
    if resp.status_code != 200:
        return jsonify([])

    out = []
    for cred in resp.json().get("results", []):
        attrs = cred.get("attrs", {}) or {}
        out.append(
            {
                "cred_id": cred.get("referent"),
                "schema_id": cred.get("schema_id"),
                "cred_def_id": cred.get("cred_def_id"),
                "rev_reg_id": cred.get("rev_reg_id"),
                "cred_rev_id": cred.get("cred_rev_id"),
                "attrs": attrs,
            }
        )
    return jsonify(out)


@app.route("/credentials/<cred_id>", methods=["GET"])
def get_credential_by_id(cred_id):
    resp = _safe_get(f"{AGENT_ADMIN_URL}/credentials")
    if resp.status_code != 200:
        return jsonify({"error": "aca-py unavailable"}), 502

    for cred in resp.json().get("results", []):
        if cred.get("referent") == cred_id:
            return jsonify(cred)

    return jsonify({"error": "credential not found"}), 404


# =========================
# Остальные API для UI
# =========================
@app.route("/connections", methods=["GET"])
def get_connections():
    resp = _safe_get(f"{AGENT_ADMIN_URL}/connections")
    if resp.status_code == 200:
        connections = resp.json().get("results", [])
        return jsonify(
            [
                {
                    "id": c.get("connection_id"),
                    "label": c.get("their_label", "Неизвестный"),
                    "state": c.get("state"),
                    "rfc23_state": c.get("rfc23_state"),
                }
                for c in connections
            ]
        )
    return jsonify([])


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    os.makedirs("static", exist_ok=True)  # чтобы было куда положить patient.css
    logging.basicConfig(filename="logs/patient.log", level=logging.INFO, encoding="utf-8")
    app.run(port=8060, debug=True)

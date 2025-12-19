import json
import logging

from flask import Flask, jsonify, request

from hospital_controller.internal.domain.config import HttpAdapter as ConfigHttpAdapter
from hospital_controller.internal.handlers.handlers import Handler
from hospital_controller.internal.http_adapter.routes import get_routes


class HttpAdapter(object):
    app = None

    def __init__(self, name: str, handler: Handler, config: ConfigHttpAdapter):
        self.app = Flask(name)
        self.handler = handler
        self.config = config
        self.app.logger.setLevel(logging.INFO)

    def run(self):
        self.app.run(host='0.0.0.0', port=self.config.Port, debug=True)

    def add_endpoint(self, path=None, methods=None, name=None, handler=None):
        self.app.add_url_rule(rule=path, endpoint=name, methods=methods, view_func=handler)

    # --- Webhooks ---
    def handle_hospital_webhooks(self, topic: str):
        message = request.json or {}
        logging.info(f"[Hospital Webhook] Topic: {topic}, Message: {json.dumps(message, indent=2, ensure_ascii=False)}")

        ok = True
        if topic == 'connections':
            ok = self.handler.handle_connection_webhook(message)
        elif topic == 'basicmessages':
            ok = self.handler.handle_basic_message_webhook(message)
        elif topic == 'present_proof_v2_0':
            ok = self.handler.handle_present_proof_webhook(message)
        elif topic == 'issue_credential_v2_0':
            ok = self.handler.handle_issue_credential_webhook(message)

        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify({"status": "processed"}), 200

    # --- API ---
    def create_invitation(self):
        body = request.json or {}
        alias = body.get('alias', 'City Hospital')
        resp, ok = self.handler.create_invitation(alias)
        return jsonify(resp), (200 if ok else 500)

    def set_regulator_connection(self):
        body = request.json or {}
        connection_id = body.get('connection_id')
        if not connection_id:
            return jsonify({"error": "connection_id is required"}), 400
        resp, ok = self.handler.set_regulator_connection(connection_id)
        return jsonify(resp), (200 if ok else 500)

    def register_institution_did(self):
        body = request.json or {}
        alias = body.get('alias', 'City Hospital')
        resp, ok = self.handler.register_institution_did(alias)
        return jsonify(resp), (200 if ok else 500)

    def request_permission(self):
        body = request.json or {}
        vc_type = body.get('credential_type') or body.get('vc_type')
        if not vc_type:
            return jsonify({"error": "credential_type is required"}), 400
        resp, ok = self.handler.request_permission_for_vc_type(vc_type)
        return jsonify(resp), (200 if ok else 500)

    def list_permissions(self):
        resp, ok = self.handler.list_permissions()
        return jsonify(resp), (200 if ok else 500)

    def create_schema_and_cred_def(self):
        body = request.json or {}
        vc_type = body.get('vc_type')
        schema_name = body.get('schema_name')
        schema_version = body.get('schema_version', '1.0.0')
        attributes = body.get('attributes', [])

        if not all([vc_type, schema_name, isinstance(attributes, list) and attributes]):
            return jsonify({
                "error": "vc_type, schema_name, attributes(list) are required",
            }), 400

        resp, ok = self.handler.create_schema_and_cred_def(vc_type, schema_name, schema_version, attributes)
        return jsonify(resp), (200 if ok else 500)


def run_http_adapter(name: str = "hospital", handler=None, config: ConfigHttpAdapter = None):
    http_adapter = HttpAdapter(name, handler, config)

    routes = get_routes(http_adapter)

    for route in routes:
        http_adapter.add_endpoint(
            path=route['path'],
            methods=route['methods'],
            name=route['name'],
            handler=route['handler']
        )

    http_adapter.run()

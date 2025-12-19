import json
import logging

from flask import jsonify, Flask, Response, request
from regulator_controller.internal.domain.config import HttpAdapter as ConfigHttpAdapter
from regulator_controller.internal.handlers.handlers import Handler
from routes import get_routes


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
        self.app.add_url_rule(
            rule=path,
            endpoint=name,
            methods=methods,
            view_func=handler
        )

    def handle_regulator_webhooks(self, topic):
        message = request.json
        logging.info(f"[Regulator Webhook] Topic: {topic}, Message: {json.dumps(message, indent=2)}")

        ok = False

        if topic == 'connections':
            ok = self.handler.handle_connection_webhook(message)

        elif topic == 'basicmessages':
            ok = self.handler.handle_basic_message_webhook(message)

        elif topic == 'endorsements':
            ok = self.handler.handle_endorsement_webhook(message)

        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify({"status": "processed"}), 200

    def get_registered_institutions(self):
        resp, ok = self.handler.get_registered_institutions()
        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify(resp), 200

    def credential_issuance_requests(self):
        resp, ok = self.handler.get_credential_issuance_requests()
        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify(resp), 200

    def credential_issuance_requests_approve(self):
        message = request.json

        resp, ok = self.handler.credential_issuance_requests_approve(message)
        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify(resp), 200

    def credential_issuance_requests_reject(self):
        message = request.json

        resp, ok = self.handler.credential_issuance_requests_reject(message)
        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify(resp), 200

    def verify_institution_permission(self):
        message = request.json

        resp, ok = self.handler.verify_institution_permission(message)
        if not ok:
            return jsonify({"status": "failed"}), 500

        return jsonify(resp), 200


def run_http_adapter(name: str = "regulator", handler = None, config: ConfigHttpAdapter = None):
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

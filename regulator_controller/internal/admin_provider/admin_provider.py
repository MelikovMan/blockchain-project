import logging
from regulator_controller.internal.domain.config import AdminProvider as ConfigAdminProvider
import requests


def send_request(method, url, headers, json) -> (any, bool):
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json
        )

        if response.status_code == 200:
            logging.info(f"Send request to {url} completed")
            return response.json(), True
        else:
            logging.error(f"Send request error: {url} {response.text}")
            return response.text, False
    except Exception as e:
        logging.error(f"Send request exception: {url} {e}")
    return None, False


class AdminProvider:
    def __init__(self, cfg: ConfigAdminProvider):
        self.url = f'{cfg.Host}:{cfg.Port}'
        self.headers = {"X-API-Key": cfg.APIKey, "Content-Type": "application/json"}
        self.cfg = cfg

    def accept_connection(self, connection_id) -> bool:
        path = self.cfg.Endpoints.AcceptConnection.Path.replace('{connection_id}', connection_id)

        _, ok = send_request(
            method=self.cfg.Endpoints.AcceptConnection.Method,
            url=self.url + path,
            headers=self.headers,
            json={}
        )

        return ok

    def auto_endorse_transaction(self, transaction_id) -> bool:
        path = self.cfg.Endpoints.EndorseTransaction.Path.replace('{transaction_id}', transaction_id)

        _, ok = send_request(
            method=self.cfg.Endpoints.EndorseTransaction.Method,
            url=self.url + path,
            headers=self.headers,
            json={}
        )

        return ok

    def register_did(self, request) -> (any, bool):
        content, ok = send_request(
            method=self.cfg.Endpoints.RegisterDID.Method,
            url=self.url + self.cfg.Endpoints.RegisterDID.Path,
            headers=self.headers,
            json=request
        )
        if not ok:
            return content, False

        return content, True

    def register_nym(self, request) -> (any, bool):
        content, ok = send_request(
            method=self.cfg.Endpoints.RegisterNYM.Method,
            url=self.url + self.cfg.Endpoints.RegisterNYM.Path,
            headers=self.headers,
            json=request
        )
        if not ok:
            return content, False

        return content, True

    def send_message(self, request, connection_id: str) -> (any, bool):

        path = self.cfg.Endpoints.SendMessage.Path.replace('{connection_id}', connection_id)

        response, ok = send_request(
            method=self.cfg.Endpoints.SendMessage.Method,
            url=self.url + path,
            headers=self.headers,
            json=request
        )

        return response, ok

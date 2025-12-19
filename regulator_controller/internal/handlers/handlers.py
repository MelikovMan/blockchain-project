import json
import logging
import uuid
from datetime import datetime

from regulator_controller.internal.admin_provider.admin_provider import AdminProvider
from regulator_controller.internal.domain import requests


class Handler:
    def __init__(self, admin_provider: AdminProvider, repo):
        self.admin_provider = admin_provider
        self.repo = repo
        self.active_connections = dict()

    def handle_connection_webhook(self, message):
        request = requests.ConnectionWebhookRequest.model_validate(message)

        logging.info(f"[Connection Webhook] State: {request.state}, Label: {request.label}, DID: {request.did}")

        ok = False

        if request.state == 'request':
            logging.info(f"Got connection request from: {request.label}")

            ok = self.admin_provider.accept_connection(request.connection_id)
        elif request.state == 'response':
            logging.info(f"Connection established with: {request.label}")

            ok = True
        elif request.state == 'active':
            logging.info(f"Connection is active: {request.label}, ID: {request.connection_id}")

            if request.did:
                logging.info(f"Connection saved for DID {request.did}: {request.connection_id}")

                self.active_connections[request.did] = request.connection_id

                ok = True

        elif request.state == 'completed':
            logging.info(f"Connection closed: {request.connection_id}")

            self.active_connections.pop(request.did)

            ok = True

        elif request.state == 'abandoned' or request.state == 'error':
            logging.error(f"Connection error {request.connection_id}: {request.state}, {request.message}")

            self.active_connections.pop(request.did)

            ok = True

        return ok

    def handle_basic_message_webhook(self, message):
        request = requests.MessageWebhookRequest.model_validate(message)

        message_data = json.loads(request.content)

        if isinstance(message_data, dict):
            message_type = message_data.get('type')

            if message_type == 'CREDENTIAL_ISSUANCE_REQUEST':
                self.handle_credential_issuance_request(request.connection_id, message_data)

            # elif message_type == 'CREDENTIAL_MODIFICATION_REQUEST':
            #     handle_credential_modification_request(request.connection_id, message_data)

            # elif message_type == 'STATUS_UPDATE':
            #     logging.info(f"Получено обновление статуса: {message_data}")

            else:
                logging.info(f"Получено структурированное сообщение: {message_data}")

    def handle_credential_issuance_request(self, connection_id, message_data):
        try:
            hospital_did = message_data.get('hospital_did')
            credential_type = message_data.get('credential_type')

            if not all([hospital_did, credential_type]):
                logging.error(f"Неполные данные в запросе на выпуск VC: {message_data}")
                return

            sql = f'SELECT * FROM public."REGISTERED_INSTITUTIONS" WHERE institution_did={hospital_did}'

            found_institution, ok = self.repo.execute_and_fetch(sql)
            if not ok:
                logging.error(f"Учреждение с DID {hospital_did} не найдено")

                _ = self.admin_provider.send_message(
                    request={
                        'type': 'ERROR',
                        'message': 'Учреждение не зарегистрировано',
                        'hospital_did': hospital_did
                    },
                    connection_id=connection_id
                )

                return False

            request_id = str(uuid.uuid4())

            sql = (f'INSERT INTO public."CREDENTIAL_ISSUANCE_REQUESTS" (request_id, institution_did, vc_type, request_date) VALUES '
                   f'({request_id},{hospital_did},{credential_type},{datetime.now().isoformat()})')

            ok = self.repo.execute(sql)
            if not ok:
                logging.error(f"Ошибка с DID {hospital_did}")

                _ = self.admin_provider.send_message(
                    request={
                        'type': 'ERROR',
                        'message': 'Ошибка записи в БД',
                        'hospital_did': hospital_did
                    },
                    connection_id=connection_id
                )

                return False

            logging.info(f"Получена заявка на выпуск VC через сообщение: {request_id} от {found_institution['name']}")

            # Отправляем подтверждение получения заявки
            ok = self.admin_provider.send_message(
                connection_id=connection_id,
                request={
                    'type': 'CREDENTIAL_ISSUANCE_REQUEST_RECEIVED',
                    'request_id': request_id,
                    'status': 'pending',
                    'message': 'Заявка принята на рассмотрение',
                    'estimated_review_time': '3 рабочих дня'
                }
            )
            return ok

        except Exception as e:
            logging.error(f"Ошибка при обработке запроса на выпуск VC: {e}")

            return False

    def handle_endorsement_webhook(self, message):
        ok = False

        state = message.get('state')
        transaction_id = message.get('transaction_id')

        logging.info(f"Вебхук эндоузинга: {state}, Transaction ID: {transaction_id}")

        if state == 'request-received':
            ok = self.admin_provider.auto_endorse_transaction(transaction_id)

        return ok

    def send_notification_to_hospital(self, hospital_did, notification_type, data):
        try:
            connection_id = self.active_connections.get(hospital_did)

            if not connection_id:
                logging.warning(f"Нет активного соединения с больницей DID: {hospital_did}")

                sql = f'SELECT * FROM public."REGISTERED_INSTITUTIONS" WHERE institution_did={hospital_did}'

                found_institutions, _ = self.repo.execute_and_fetch(sql)

                connection_id = found_institutions['connection_id']

                if not connection_id:
                    logging.error(f"Не найдено соединение для больницы {hospital_did}")
                    return False

            response, ok = self.admin_provider.send_message(
                connection_id=connection_id,
                request={
                    'type': notification_type,
                    'from': 'REGULATOR',
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }
            )

            if ok:
                logging.info(f"Уведомление отправлено больнице {hospital_did}: {notification_type}")
                return True
            else:
                logging.error(f"Ошибка отправки уведомления: {response.text}")
                return False

        except Exception as e:
            logging.error(f"Исключение при отправке уведомления: {e}")
            return False

    def get_registered_institutions(self):
        sql = ('SELECT * FROM public."REGISTERED_INSTITUTIONS" ri '
               'JOIN public."CREDENTIAL_INSTITUTION_APPROVE" cia on cia.institution_did=ri.institution_did'
               'JOIN public."APPROVED_CREDENTIALS" ac on ac.vc_type=cia.vc_type')

        institutions, ok = self.repo.execute_and_fetch(sql)
        if ok:
            return institutions, True

        return None, False

    def get_credential_issuance_requests(self):
        sql = 'SELECT * FROM public."CREDENTIAL_ISSUANCE_REQUESTS"'

        ci_requests, ok = self.repo.execute_and_fetch(sql)
        if ok:
            return ci_requests, True

        return None, False

    def credential_issuance_requests_approve(self, message):
        request_id = message.get('request_id')

        sql = 'SELECT * FROM public."CREDENTIAL_ISSUANCE_REQUESTS" WHERE request_id={request_id}'

        cir, ok = self.repo.execute_and_fetch(sql)
        if not cir.get('institution_did'):
            return {}, False

        date_approve = datetime.now().isoformat()
        sql = 'UPDATE CREDENTIAL_ISSUANCE_REQUESTS SET approved_date={date_approve} WHERE request_id={request_id}'

        ok = self.repo.execute(sql)
        if not ok:
            return {}, False

        institution_did = cir.get('institution_did')
        vc_type = cir.get('vc_type')

        sql = 'INSERT INTO public."CREDENTIAL_INSTITUTION_APPROVE" (institution_did, vc_type, date_approve) VALUES ({institution_did}, {vc_type}, {date_approve} ON CONFLICT DO NOTHING)'
        ok = self.repo.execute(sql)
        if not ok:
            return {}, False

        ok = self.send_notification_to_hospital(
            hospital_did=institution_did,
            notification_type='CREDENTIAL_ISSUANCE_APPROVED',
            data={
                'request_id': request_id,
            }
        )

        return {
            'success': True,
            'message': 'Заявка одобрена',
            'request_id': request_id,
            'credential_type': vc_type,
            'notification_sent': ok
        }, True

    def credential_issuance_requests_reject(self, message):
        request_id = message.get('request_id')

        sql = 'SELECT * FROM public."CREDENTIAL_ISSUANCE_REQUESTS" WHERE request_id={request_id}'

        cir, ok = self.repo.execute_and_fetch(sql)
        if not cir.get('institution_did'):
            return {}, False

        reject_date = datetime.now().isoformat()
        sql = 'UPDATE CREDENTIAL_ISSUANCE_REQUESTS SET reject_date={reject_date} WHERE request_id={request_id}'

        ok = self.repo.execute(sql)
        if not ok:
            return {}, False

        institution_did = cir.get('institution_did')
        vc_type = cir.get('vc_type')

        ok = self.send_notification_to_hospital(
            hospital_did=institution_did,
            notification_type='CREDENTIAL_ISSUANCE_REJECTED',
            data={
                'request_id': request_id,
            }
        )

        return {
            'success': True,
            'message': 'Заявка отклонена',
            'request_id': request_id,
            'credential_type': vc_type,
            'notification_sent': ok
        }, True


    def verify_institution_permission(self, message):
        hospital_did = message.get('hospital_did')
        vc_type = message.get('credential_type')

        sql = f'SELECT * FROM public."REGISTERED_INSTITUTIONS" WHERE institution_did={hospital_did}'

        found_institutions, ok = self.repo.execute_and_fetch(sql)
        if not ok:
            return {}, False

        connection_id = found_institutions.get('institution_did')

        if not connection_id:
            logging.error(f"Не найдена больница {hospital_did}")
            return {
                'authorized': False,
                'reason': 'Учреждение не зарегистрировано'
            }, False

        sql = 'SELECT * FROM public."CREDENTIAL_INSTITUTION_APPROVE" cia WHERE institution_did={institution_did} AND vc_type={vc_type} AND date_approve NOT NULL'

        cir, ok = self.repo.execute_and_fetch(sql)
        if not cir.get('institution_did'):
            logging.error(f"Не найден CREDENTIAL_INSTITUTION_APPROVE {hospital_did}")
            return {
                'authorized': False,
                'vc_type': vc_type,
                'reason': 'Учреждение не имеет право выпускать данный тип документов',
            }, False

        return {
            'authorized': True,
            'vc_type': vc_type,
            'reason': 'Учреждение имеет право выпускать данный тип документов',
        }, True
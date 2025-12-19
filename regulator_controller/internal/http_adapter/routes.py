from http_adapter import HttpAdapter

def get_routes(http_adapter: HttpAdapter):
    routes = \
        [
            {
                "path": "/webhooks/topic/<string:topic>",
                "methods": ["POST"],
                "name": "regulator_webhooks",
                "handler": http_adapter.handle_regulator_webhooks
            },
            {
                "path": "/institutions",
                "methods": ["GET"],
                "name": "institutions",
                "handler": http_adapter.get_registered_institutions
            },
            {
                "path": "/credential-issuance-requests",
                "methods": ["GET"],
                "name": "credential-issuance-requests",
                "handler": http_adapter.credential_issuance_requests
            },
            {
                "path": "/credential-issuance-requests/<request_id>/approve",
                "methods": ["POST"],
                "name": "credential-issuance-requests-approve",
                "handler": http_adapter.credential_issuance_requests_approve
            },
            {
                "path": "/credential-issuance-requests/<request_id>/reject",
                "methods": ["POST"],
                "name": "credential-issuance-requests-approve",
                "handler": http_adapter.credential_issuance_requests_reject
            },
            {
                "path": "/verify-institution-permission",
                "methods": ["POST"],
                "name": "verify-institution-permission",
                "handler": http_adapter.verify_institution_permission
            },
        ]

    return routes
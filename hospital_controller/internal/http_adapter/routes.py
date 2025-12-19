from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hospital_controller.internal.http_adapter.http_adapter import HttpAdapter


def get_routes(http_adapter: 'HttpAdapter'):
    routes = [
        {
            "path": "/webhooks/topic/<string:topic>",
            "methods": ["POST"],
            "name": "hospital_webhooks",
            "handler": http_adapter.handle_hospital_webhooks,
        },
        {
            "path": "/invitation",
            "methods": ["POST"],
            "name": "create_invitation",
            "handler": http_adapter.create_invitation,
        },
        {
            "path": "/regulator/connection",
            "methods": ["POST"],
            "name": "set_regulator_connection",
            "handler": http_adapter.set_regulator_connection,
        },
        {
            "path": "/institution/register-did",
            "methods": ["POST"],
            "name": "register_institution_did",
            "handler": http_adapter.register_institution_did,
        },
        {
            "path": "/permissions/request",
            "methods": ["POST"],
            "name": "request_permission",
            "handler": http_adapter.request_permission,
        },
        {
            "path": "/permissions",
            "methods": ["GET"],
            "name": "list_permissions",
            "handler": http_adapter.list_permissions,
        },
        {
            "path": "/ledger/schema-creddef",
            "methods": ["POST"],
            "name": "create_schema_and_cred_def",
            "handler": http_adapter.create_schema_and_cred_def,
        },
    ]

    return routes

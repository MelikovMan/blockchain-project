from typing import Any, Dict, Optional
from pydantic import BaseModel


class ConnectionWebhookRequest(BaseModel):
    connection_id: str
    state: str
    their_label: Optional[str] = None
    their_did: Optional[str] = None
    my_did: Optional[str] = None


class MessageWebhookRequest(BaseModel):
    connection_id: str
    content: str
    sent_time: Optional[str] = None


class ProofWebhookRequest(BaseModel):
    pres_ex_id: str
    state: str
    connection_id: Optional[str] = None
    by_format: Optional[Dict[str, Any]] = None


class IssueCredentialWebhookRequest(BaseModel):
    cred_ex_id: str
    state: str
    connection_id: Optional[str] = None
    credential_exchange_id: Optional[str] = None

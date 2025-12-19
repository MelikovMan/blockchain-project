from pydantic import BaseModel, Field


class ConnectionWebhookRequest(BaseModel):
    state: str = Field(default="")
    connection_id: str = Field(default="")
    label: str = Field(default="")
    did: str = Field(default="")
    message: str = Field(default="")


class MessageWebhookRequest(BaseModel):
    content: str = Field(default="")
    sent_time: str = Field(default="")
    connection_id: str = Field(default="")
    message_type: str = Field(default="")

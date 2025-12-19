from pydantic import BaseModel


class HttpAdapter(BaseModel):
    Port: int


class Primary(BaseModel):
    HttpAdapter: HttpAdapter


class Endpoint(BaseModel):
    Path: str
    Method: str


class AdminProviderEndpoints(BaseModel):
    AcceptConnection: Endpoint
    EndorseTransaction: Endpoint
    RegisterDID: Endpoint
    RegisterNYM: Endpoint
    SendMessage: Endpoint


class AdminProvider(BaseModel):
    Host: str
    Port: int
    APIKey: str
    Endpoints: AdminProviderEndpoints


class RegulatorRepo(BaseModel):
    Name: str
    Host: str
    Port: int
    User: str
    Password: str
    Type: str


class Secondary(BaseModel):
    AdminProvider: AdminProvider
    RegulatorRepo: RegulatorRepo


class Adapters(BaseModel):
    Primary: Primary
    Secondary: Secondary


class App(BaseModel):
    Version: str
    Name: str


class Config(BaseModel):
    App: App
    Adapters: Adapters

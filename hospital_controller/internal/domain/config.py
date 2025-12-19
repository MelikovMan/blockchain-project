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
    CreateInvitation: Endpoint
    WalletCreateDID: Endpoint
    WalletSetPublicDID: Endpoint
    SendMessage: Endpoint

    ProofGetCredentials: Endpoint
    ProofSendPresentation: Endpoint

    CredentialSendRequest: Endpoint
    CredentialGetRecord: Endpoint

    SchemaCreated: Endpoint
    SchemaCreate: Endpoint
    CredDefCreated: Endpoint
    CredDefCreate: Endpoint


class AdminProvider(BaseModel):
    Host: str
    Port: int
    APIKey: str
    DIDSeed: str
    Endpoints: AdminProviderEndpoints


class RegulatorRepo(BaseModel):
    Name: str
    Host: str
    Port: int
    User: str
    Password: str
    Type: str
    InitSchema: bool = True


class Secondary(BaseModel):
    AdminProvider: AdminProvider
    RegulatorRepo: RegulatorRepo


class Adapters(BaseModel):
    Primary: Primary
    Secondary: Secondary


class App(BaseModel):
    Version: str
    Name: str


class Regulator(BaseModel):
    DID: str
    Alias: str = "REGULATOR"


class Config(BaseModel):
    App: App
    Regulator: Regulator
    Adapters: Adapters

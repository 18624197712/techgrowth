from pydantic import BaseModel, EmailStr, Field, HttpUrl


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class TotpRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class TaskGenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    skill: str = Field(min_length=2, max_length=120)


class SubmissionRequest(BaseModel):
    summary: str = Field(min_length=5, max_length=10_000)
    artifact_kind: str
    artifact_reference: str = Field(min_length=1, max_length=2_000)
    self_scores: dict[str, float]


class PairConnectorRequest(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=120)
    public_key: str


class NotificationSettingsRequest(BaseModel):
    channel: str
    event: str
    enabled: bool
    destination: str = ""


class NotificationPreferenceItem(BaseModel):
    channel: str
    event: str
    enabled: bool


class NotificationPreferencesRequest(BaseModel):
    preferences: list[NotificationPreferenceItem]


class RepositoryManifestRequest(BaseModel):
    external_key: str
    name: str
    default_branch: str = "main"
    languages: dict[str, int] = Field(default_factory=dict)
    last_commit: str = ""


class SyncJobRequest(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)
    idempotency_key: str


class CompleteSyncJobRequest(BaseModel):
    result: dict = Field(default_factory=dict)


class UploadCompleteRequest(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(ge=0, le=10 * 1024 * 1024)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    page_context: dict = Field(default_factory=dict)


class PushSubscriptionRequest(BaseModel):
    endpoint: HttpUrl
    keys: dict[str, str]


class DeleteDataRequest(BaseModel):
    confirmation: str

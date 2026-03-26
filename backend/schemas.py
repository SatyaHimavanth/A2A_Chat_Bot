from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    username: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class AgentConnectRequest(BaseModel):
    base_url: str
    mode: Literal['public', 'authorized']
    auth_token: str | None = None


class AgentRegistryMetadata(BaseModel):
    protocol_version: str | None = None
    preferred_transport: str | None = None
    agent_url: str | None = None
    provider: str | None = None
    version: str | None = None
    default_input_modes: list[str] = Field(default_factory=list)
    default_output_modes: list[str] = Field(default_factory=list)


class AgentBenchmark(BaseModel):
    latency_ms: int | None = None
    cost: float | None = None
    success_rate: float | None = None


class AgentAnalytics(BaseModel):
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    rating_average: float = 0.0
    rating_count: int = 0
    last_used_at: datetime | None = None


class AgentSummary(BaseModel):
    id: int
    base_url: str
    mode: str
    card_name: str
    card_description: str
    status: str = 'connected'
    supports_authenticated_extended_card: bool = False
    skills: list[dict] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    registry_metadata: AgentRegistryMetadata = Field(default_factory=AgentRegistryMetadata)
    benchmarks: AgentBenchmark = Field(default_factory=AgentBenchmark)
    analytics: AgentAnalytics = Field(default_factory=AgentAnalytics)
    created_at: datetime


class AgentModeCard(BaseModel):
    id: int
    mode: str
    status: str = 'connected'
    card_payload: dict


class AgentDetail(BaseModel):
    id: int
    base_url: str
    card_name: str
    card_description: str
    capability_tags: list[str] = Field(default_factory=list)
    registry_metadata: AgentRegistryMetadata = Field(default_factory=AgentRegistryMetadata)
    benchmarks: AgentBenchmark = Field(default_factory=AgentBenchmark)
    analytics: AgentAnalytics = Field(default_factory=AgentAnalytics)
    modes: list[AgentModeCard] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentRateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionSummary(BaseModel):
    id: int
    context_id: str
    title: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    chat_status: int = 1
    created_at: datetime
    updated_at: datetime


class MessageSummary(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
    attachments: list['AttachmentContent'] = Field(default_factory=list)
    display_message: str | None = None


class AttachmentContent(BaseModel):
    filename: str
    text: str


class AttachmentExtractResult(BaseModel):
    filename: str
    size: int
    text: str = ''
    status: Literal['ready', 'error']
    error: str | None = None


class AttachmentExtractResponse(BaseModel):
    files: list[AttachmentExtractResult] = Field(default_factory=list)


class SessionRenameRequest(BaseModel):
    title: str


class PlaygroundCompareRequest(BaseModel):
    agent_ids: list[int] = Field(min_length=1)
    message: str
    context_ids: dict[int, str] = Field(default_factory=dict)


class PlaygroundAgentResult(BaseModel):
    agent_id: int
    card_name: str
    mode: str
    context_id: str
    latency_ms: int
    response: str = ''
    error: str | None = None
    status: Literal['ok', 'error']


class PlaygroundCompareResponse(BaseModel):
    results: list[PlaygroundAgentResult] = Field(default_factory=list)

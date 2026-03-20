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


class AgentSummary(BaseModel):
    id: int
    base_url: str
    mode: str
    card_name: str
    card_description: str
    status: str = 'connected'
    supports_authenticated_extended_card: bool = False
    skills: list[dict] = Field(default_factory=list)
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
    modes: list[AgentModeCard] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


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

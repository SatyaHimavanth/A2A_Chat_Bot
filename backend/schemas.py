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
    token: str
    username: str
    expires_at: datetime


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

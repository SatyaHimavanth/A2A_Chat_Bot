from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database import Base


JSONType = JSON().with_variant(JSONB, 'postgresql')


class AgentMode(str, Enum):
    public = 'public'
    authorized = 'authorized'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    agents: Mapped[list['AgentConnection']] = relationship(back_populates='user')
    sessions: Mapped[list['ChatSession']] = relationship(back_populates='user')


class AgentConnection(Base):
    __tablename__ = 'agent_connections'
    __table_args__ = (
        UniqueConstraint('user_id', 'base_url', 'mode', name='uq_user_agent_mode'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    mode: Mapped[AgentMode] = mapped_column(SQLEnum(AgentMode), nullable=False)
    auth_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='connected')
    card_name: Mapped[str] = mapped_column(String(255), nullable=False)
    card_description: Mapped[str] = mapped_column(Text, nullable=False)
    card_payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    registry_metadata: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    capability_tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    benchmark_latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    benchmark_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rating_total: Mapped[int] = mapped_column(nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates='agents')
    sessions: Mapped[list['ChatSession']] = relationship(back_populates='agent')


class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    __table_args__ = (
        UniqueConstraint(
            'user_id',
            'agent_connection_id',
            'context_id',
            name='uq_user_agent_context',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    agent_connection_id: Mapped[int] = mapped_column(
        ForeignKey('agent_connections.id'), nullable=False
    )
    context_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default='New chat', nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    chat_status: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates='sessions')
    agent: Mapped[AgentConnection] = relationship(back_populates='sessions')
    messages: Mapped[list['ChatMessage']] = relationship(
        back_populates='session',
        order_by='ChatMessage.created_at',
        cascade='all, delete-orphan',
    )


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('chat_sessions.id'), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    session: Mapped[ChatSession] = relationship(back_populates='messages')

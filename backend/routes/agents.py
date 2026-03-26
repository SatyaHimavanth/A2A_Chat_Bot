from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from deps import require_user
from models import AgentConnection, AgentMode, ChatSession, User
from schemas import AgentConnectRequest, AgentDetail, AgentRateRequest, AgentSummary, SessionSummary
from services.agent_service import resolve_agent_card, status_manager, sync_agents_status_fast
from services.agent_registry import (
    derive_capability_tags,
    derive_registry_metadata,
    record_agent_rating,
)
from services.serialization import serialize_agent, serialize_agent_detail, serialize_session

router = APIRouter(prefix='/api', tags=['agents'])


@router.get('/agents', response_model=list[AgentSummary])
async def list_agents(
    refresh_status: bool = Query(default=False),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(AgentConnection)
        .where(AgentConnection.user_id == user.id)
        .order_by(AgentConnection.updated_at.desc())
    ).all()
    if refresh_status:
        for row in rows:
            await status_manager.refresh_now(row, db)
    else:
        await sync_agents_status_fast(rows)
    return [serialize_agent(row) for row in rows]


@router.get('/agents/{agent_id}', response_model=AgentDetail)
def get_agent_detail(
    agent_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    mode_rows = db.scalars(
        select(AgentConnection)
        .where(
            AgentConnection.user_id == user.id,
            AgentConnection.base_url == agent.base_url,
        )
        .order_by(AgentConnection.mode.asc())
    ).all()
    return serialize_agent_detail(agent, mode_rows)


@router.post('/agents', response_model=AgentSummary, status_code=201)
async def connect_agent(
    payload: AgentConnectRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    base_url = payload.base_url.rstrip('/')
    existing = db.scalar(
        select(AgentConnection).where(
            AgentConnection.user_id == user.id,
            AgentConnection.base_url == base_url,
            AgentConnection.mode == AgentMode(payload.mode),
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail='Agent already connected in this mode for your account.',
        )

    card = await resolve_agent_card(payload)
    card_payload = card.model_dump(exclude_none=True, by_alias=True)
    row = AgentConnection(
        user_id=user.id,
        base_url=base_url,
        mode=AgentMode(payload.mode),
        auth_token=payload.auth_token if payload.mode == AgentMode.authorized.value else None,
        status='connected',
        card_name=card.name,
        card_description=card.description,
        card_payload=card_payload,
        registry_metadata=derive_registry_metadata(card_payload, base_url),
        capability_tags=derive_capability_tags(card_payload),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail='Agent already connected in this mode for your account.',
        )
    db.refresh(row)
    status_manager.set_cached_status(row.id, row.status)
    return serialize_agent(row)


@router.post('/agents/{agent_id}/rate', response_model=AgentSummary)
def rate_agent(
    agent_id: int,
    payload: AgentRateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    record_agent_rating(agent, payload.rating)
    db.commit()
    db.refresh(agent)
    return serialize_agent(agent)


@router.post('/agents/{agent_id}/refresh-status', response_model=AgentSummary)
async def refresh_agent_status(
    agent_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    await status_manager.refresh_now(agent, db)
    return serialize_agent(agent)


@router.delete('/agents/{agent_id}', status_code=204)
def delete_agent(
    agent_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')

    sessions = db.scalars(
        select(ChatSession).where(
            ChatSession.user_id == user.id,
            ChatSession.agent_connection_id == agent_id,
        )
    ).all()
    for session in sessions:
        db.delete(session)
    db.delete(agent)
    db.commit()


@router.get('/agents/{agent_id}/sessions', response_model=list[SessionSummary])
def list_sessions(
    agent_id: int,
    search: str | None = Query(default=None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    sessions = db.scalars(
        select(ChatSession)
        .where(
            ChatSession.user_id == user.id,
            ChatSession.agent_connection_id == agent_id,
            ChatSession.chat_status != 0,
        )
        .order_by(ChatSession.chat_status.asc(), ChatSession.updated_at.desc())
    ).all()

    if search:
        q = search.lower().strip()
        sessions = [
            s
            for s in sessions
            if q in (s.title or '').lower()
            or q in (s.summary or '').lower()
            or any(q in (tag or '').lower() for tag in (s.tags or []))
        ]

    return [serialize_session(s) for s in sessions]

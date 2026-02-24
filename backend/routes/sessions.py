import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, TextPart, TransportProtocol
from a2a.utils.message import get_message_text
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from deps import require_user
from models import AgentConnection, AgentMode, ChatMessage, ChatSession, User
from schemas import (
    ChatRequest,
    MessageSummary,
    SessionCreateRequest,
    SessionRenameRequest,
    SessionSummary,
)
from services.agent_service import status_manager
from core.config import STREAM_CONNECT_TIMEOUT_SECONDS, STREAM_READ_TIMEOUT_SECONDS
from services.serialization import auth_context, extract_text_from_task_event, serialize_session
from services.session_intelligence import refine_title, update_session_intelligence

router = APIRouter(prefix='/api', tags=['sessions'])


@router.post('/agents/{agent_id}/sessions', response_model=SessionSummary, status_code=201)
async def create_session(
    agent_id: int,
    payload: SessionCreateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    is_connected = await status_manager.refresh_now(agent, db)
    if not is_connected:
        raise HTTPException(
            status_code=409,
            detail='Agent cannot be connected right now.',
        )

    title = payload.title.strip() if payload.title else 'New chat'
    session = ChatSession(
        user_id=user.id,
        agent_connection_id=agent_id,
        context_id=str(uuid4()),
        title=title,
        chat_status=1,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return serialize_session(session)


@router.get('/sessions/{session_id}/messages', response_model=list[MessageSummary])
def get_messages(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    msgs = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return [
        MessageSummary(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in msgs
    ]


@router.post('/sessions/{session_id}/stream')
async def stream_chat(
    session_id: int,
    payload: ChatRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')

    agent = db.get(AgentConnection, session.agent_connection_id)
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found.')
    is_connected = await status_manager.refresh_now(agent, db)
    if not is_connected:
        raise HTTPException(
            status_code=409,
            detail='Agent cannot be connected right now.',
        )

    user_message = ChatMessage(
        session_id=session.id,
        role='user',
        content=payload.message,
    )
    db.add(user_message)
    session.updated_at = datetime.now(timezone.utc)
    if session.title == 'New chat':
        session.title = refine_title(payload.message)
    if session.chat_status == -1:
        session.chat_status = 1
    db.commit()

    card = AgentCard.model_validate(agent.card_payload)
    auth_token = agent.auth_token if agent.mode == AgentMode.authorized else None

    async def event_stream():
        httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=STREAM_CONNECT_TIMEOUT_SECONDS,
                read=STREAM_READ_TIMEOUT_SECONDS,
                write=STREAM_CONNECT_TIMEOUT_SECONDS,
                pool=STREAM_CONNECT_TIMEOUT_SECONDS,
            )
        )
        cfg = ClientConfig(
            httpx_client=httpx_client,
            supported_transports=[
                TransportProtocol.jsonrpc,
                TransportProtocol.http_json,
            ],
            streaming=bool(card.capabilities.streaming),
        )
        a2a_client = ClientFactory(cfg).create(card)
        call_context = auth_context(auth_token)
        assistant_text = ''
        try:
            request = Message(
                role=Role.user,
                parts=[Part(TextPart(text=payload.message))],
                message_id=str(uuid4()),
                context_id=session.context_id,
            )
            yield f"data: {json.dumps({'type': 'start'})}\\n\\n"
            async for response in a2a_client.send_message(request, context=call_context):
                if isinstance(response, tuple):
                    task, update = response
                    text = extract_text_from_task_event(task, update)
                else:
                    text = get_message_text(response)
                if text:
                    assistant_text = text
                    yield (
                        f"data: {json.dumps({'type': 'assistant_snapshot', 'text': text})}\\n\\n"
                    )

            db2 = next(get_db())
            try:
                db_session = db2.get(ChatSession, session.id)
                if db_session:
                    if assistant_text:
                        db2.add(
                            ChatMessage(
                                session_id=db_session.id,
                                role='assistant',
                                content=assistant_text,
                            )
                        )
                    db_session.updated_at = datetime.now(timezone.utc)
                    update_session_intelligence(db2, db_session)
                    db2.commit()
            finally:
                db2.close()

            yield f"data: {json.dumps({'type': 'done'})}\\n\\n"
        except Exception as e:
            db3 = next(get_db())
            try:
                db_agent = db3.get(AgentConnection, agent.id)
                if db_agent:
                    db_agent.status = 'disconnected'
                    db3.commit()
            finally:
                db3.close()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\\n\\n"
        finally:
            await a2a_client.close()
            await httpx_client.aclose()

    return StreamingResponse(event_stream(), media_type='text/event-stream')


@router.patch('/sessions/{session_id}/rename', response_model=SessionSummary)
def rename_session(
    session_id: int,
    payload: SessionRenameRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail='Title cannot be empty.')
    session.title = title[:255]
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return serialize_session(session)


@router.post('/sessions/{session_id}/archive', response_model=SessionSummary)
def archive_session(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = -1
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return serialize_session(session)


@router.post('/sessions/{session_id}/unarchive', response_model=SessionSummary)
def unarchive_session(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = 1
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return serialize_session(session)


@router.post('/sessions/{session_id}/delete', response_model=SessionSummary)
def delete_session(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = 0
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return serialize_session(session)

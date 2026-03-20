import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from deps import require_user
from models import AgentConnection, ChatMessage, ChatSession, User
from schemas import (
    ChatRequest,
    MessageSummary,
    SessionCreateRequest,
    SessionRenameRequest,
    SessionSummary,
)
from services.agent_service import status_manager
from services.agent_transport import send_agent_message
from services.serialization import serialize_session
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

    async def event_stream():
        assistant_text = ''
        try:
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            assistant_text = await send_agent_message(agent, payload.message, session.context_id)
            if assistant_text:
                yield (
                    f"data: {json.dumps({'type': 'assistant_snapshot', 'text': assistant_text})}\n\n"
                )

            db2 = SessionLocal()
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

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            db3 = SessionLocal()
            try:
                db_agent = db3.get(AgentConnection, agent.id)
                if db_agent:
                    db_agent.status = 'disconnected'
                    db3.commit()
            finally:
                db3.close()
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

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

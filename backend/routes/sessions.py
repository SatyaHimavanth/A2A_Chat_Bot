import json
import asyncio
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from deps import require_user
from models import AgentConnection, ChatMessage, ChatSession, User
from schemas import (
    AttachmentExtractResponse,
    AttachmentExtractResult,
    ChatRequest,
    MessageSummary,
    SessionCreateRequest,
    SessionRenameRequest,
    SessionSummary,
)
from services.agent_service import status_manager
from services.agent_transport import send_agent_message
from services.file_extract import (
    MAX_ATTACHMENT_COUNT,
    MAX_ATTACHMENT_SIZE_BYTES,
    extract_text_from_upload,
)
from services.agent_registry import record_agent_usage
from services.serialization import serialize_session
from services.session_intelligence import refine_title, update_session_intelligence

router = APIRouter(prefix='/api', tags=['sessions'])


def _compose_message(message: str, attachments) -> str:
    base_message = message.strip()
    ready_attachments = [item for item in attachments if item.text.strip()]
    if not ready_attachments:
        return base_message
    attachment_sections = '\n\n'.join(
        f"[Attachment: {item.filename}]\n{item.text.strip()}"
        for item in ready_attachments
    )
    return (
        f"{base_message}\n\nAttached file context:\n{attachment_sections}"
        if base_message
        else f"Attached file context:\n{attachment_sections}"
    )


def _display_message(message: str, attachments, explicit_display: str | None) -> str:
    if explicit_display and explicit_display.strip():
        return explicit_display.strip()
    base_message = message.strip()
    ready_attachments = [item for item in attachments if item.text.strip()]
    if not ready_attachments:
        return base_message
    file_lines = '\n'.join(f'- {item.filename}' for item in ready_attachments)
    if base_message:
        return f'{base_message}\n\nAttached files:\n{file_lines}'
    return f'Attached files:\n{file_lines}'


@router.post('/attachments/extract', response_model=AttachmentExtractResponse)
async def extract_attachments(
    files: list[UploadFile] = File(...),
    user: User = Depends(require_user),
):
    del user
    if not files:
        raise HTTPException(status_code=400, detail='No files provided.')
    if len(files) > MAX_ATTACHMENT_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f'At most {MAX_ATTACHMENT_COUNT} files can be attached.',
        )

    async def _process_file(upload: UploadFile) -> AttachmentExtractResult:
        raw_bytes = await upload.read()
        if len(raw_bytes) > MAX_ATTACHMENT_SIZE_BYTES:
            return AttachmentExtractResult(
                filename=upload.filename or 'unnamed',
                size=len(raw_bytes),
                status='error',
                error='File exceeds 5 MB limit.',
            )
        try:
            text = await extract_text_from_upload(upload.filename or 'unnamed', raw_bytes)
            return AttachmentExtractResult(
                filename=upload.filename or 'unnamed',
                size=len(raw_bytes),
                text=text.strip(),
                status='ready',
            )
        except Exception as exc:
            return AttachmentExtractResult(
                filename=upload.filename or 'unnamed',
                size=len(raw_bytes),
                status='error',
                error=str(exc),
            )

    results = await asyncio.gather(*[_process_file(file) for file in files])
    return AttachmentExtractResponse(files=results)


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


@router.get('/sessions/{session_id}/export')
def export_session(
    session_id: int,
    format: str = 'markdown',
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')

    agent = db.get(AgentConnection, session.agent_connection_id)
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()

    export_format = format.strip().lower()
    if export_format == 'json':
        payload = {
            'session': {
                'id': session.id,
                'context_id': session.context_id,
                'title': session.title,
                'summary': session.summary,
                'tags': session.tags or [],
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
            },
            'agent': {
                'id': agent.id if agent else None,
                'name': agent.card_name if agent else None,
                'base_url': agent.base_url if agent else None,
                'mode': agent.mode.value if agent and hasattr(agent.mode, 'value') else None,
            },
            'messages': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        media_type = 'application/json'
        extension = 'json'
    elif export_format == 'markdown':
        header_lines = [
            f'# {session.title}',
            '',
            f'- Session ID: `{session.context_id}`',
            f'- Agent: {agent.card_name if agent else "Unknown agent"}',
        ]
        if session.summary:
            header_lines.extend(['', f'> {session.summary}'])
        if session.tags:
            header_lines.extend(['', f'Tags: {" ".join(f"#{tag}" for tag in session.tags)}'])
        body_lines = []
        for msg in messages:
            speaker = 'User' if msg.role == 'user' else 'Assistant'
            body_lines.extend(
                [
                    '',
                    f'## {speaker}',
                    '',
                    msg.content,
                ]
            )
        content = '\n'.join(header_lines + body_lines).strip() + '\n'
        media_type = 'text/markdown; charset=utf-8'
        extension = 'md'
    elif export_format == 'txt':
        parts = [
            session.title,
            f'Session ID: {session.context_id}',
            f'Agent: {agent.card_name if agent else "Unknown agent"}',
        ]
        if session.summary:
            parts.extend(['', f'Summary: {session.summary}'])
        if session.tags:
            parts.extend(['', f'Tags: {", ".join(session.tags)}'])
        for msg in messages:
            speaker = 'User' if msg.role == 'user' else 'Assistant'
            parts.extend(['', f'[{speaker}]', msg.content])
        content = '\n'.join(parts).strip() + '\n'
        media_type = 'text/plain; charset=utf-8'
        extension = 'txt'
    else:
        raise HTTPException(status_code=400, detail='Unsupported export format.')

    safe_title = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in session.title).strip('_') or 'chat-session'
    headers = {
        'Content-Disposition': f'attachment; filename="{safe_title}.{extension}"',
    }
    return Response(content=content.encode('utf-8'), media_type=media_type, headers=headers)


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

    composed_message = _compose_message(payload.message, payload.attachments)
    visible_message = _display_message(
        payload.message,
        payload.attachments,
        payload.display_message,
    )
    if not composed_message.strip():
        raise HTTPException(status_code=400, detail='Message cannot be empty.')

    user_message = ChatMessage(
        session_id=session.id,
        role='user',
        content=visible_message,
    )
    db.add(user_message)
    session.updated_at = datetime.now(timezone.utc)
    if session.title == 'New chat':
        session.title = refine_title(payload.message or visible_message or composed_message)
    if session.chat_status == -1:
        session.chat_status = 1
    db.commit()

    async def event_stream():
        assistant_text = ''
        try:
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            started = perf_counter()
            assistant_text = await send_agent_message(agent, composed_message, session.context_id)
            latency_ms = int((perf_counter() - started) * 1000)
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
                    db_agent = db2.get(AgentConnection, agent.id)
                    if db_agent:
                        record_agent_usage(
                            db_agent,
                            latency_ms=latency_ms,
                            success=bool(assistant_text.strip()),
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
                    record_agent_usage(db_agent, success=False)
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

import json
import os
import asyncio
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.client.middleware import ClientCallContext
from a2a.types import AgentCard, Message, Part, Role, TextPart, TransportProtocol
from a2a.utils.message import get_message_text
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from jose import JWTError, ExpiredSignatureError, jwt
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import AgentConnection, AgentMode, ChatMessage, ChatSession, User
from schemas import (
    AgentDetail,
    AgentModeCard,
    AgentConnectRequest,
    AgentSummary,
    ChatRequest,
    LoginRequest,
    LoginResponse,
    MessageSummary,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    SessionRenameRequest,
    SessionCreateRequest,
    SessionSummary,
)


load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)


def _run_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        # Lightweight migration for existing DBs.
        db.execute(
            text(
                "ALTER TABLE agent_connections ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'connected'"
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    try:
        db.execute(
            text(
                "ALTER TABLE chat_sessions ADD COLUMN chat_status INTEGER NOT NULL DEFAULT 1"
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    try:
        existing = db.scalar(select(User).where(User.username == 'admin'))
        if not existing:
            db.add(User(username='admin', password='admin'))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _run_startup()
    yield


app = FastAPI(
    title='A2A Agent Chat Backend',
    version='1.0.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

AGENT_STATUS_CHECK_TIMEOUT_SECONDS = float(
    os.getenv('AGENT_STATUS_CHECK_TIMEOUT_SECONDS', '12')
)
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '120'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '30'))


def _serialize_agent(agent: AgentConnection) -> AgentSummary:
    payload = agent.card_payload or {}
    return AgentSummary(
        id=agent.id,
        base_url=agent.base_url,
        mode=agent.mode.value if hasattr(agent.mode, 'value') else str(agent.mode),
        card_name=agent.card_name,
        card_description=agent.card_description,
        status=agent.status or 'connected',
        supports_authenticated_extended_card=bool(
            payload.get('supportsAuthenticatedExtendedCard')
            or payload.get('supports_authenticated_extended_card')
        ),
        skills=payload.get('skills', []),
        created_at=agent.created_at,
    )


def _serialize_agent_detail(
    agent: AgentConnection,
    mode_rows: list[AgentConnection],
) -> AgentDetail:
    mode_cards = [
        AgentModeCard(
            id=row.id,
            mode=row.mode.value if hasattr(row.mode, 'value') else str(row.mode),
            status=row.status or 'connected',
            card_payload=row.card_payload or {},
        )
        for row in mode_rows
    ]
    return AgentDetail(
        id=agent.id,
        base_url=agent.base_url,
        card_name=agent.card_name,
        card_description=agent.card_description,
        modes=mode_cards,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _serialize_session(session: ChatSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        context_id=session.context_id,
        title=session.title,
        chat_status=session.chat_status if session.chat_status is not None else 1,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _extract_text_from_task_event(task, update) -> str:
    if task and getattr(task, 'artifacts', None):
        return get_message_text(task.artifacts[-1])

    status_update = getattr(update, 'status', None)
    if status_update and getattr(status_update, 'message', None):
        return get_message_text(status_update.message)

    task_status = getattr(task, 'status', None)
    if task_status and getattr(task_status, 'message', None):
        return get_message_text(task_status.message)

    return ''


def _auth_context(auth_token: str | None) -> ClientCallContext | None:
    if not auth_token:
        return None
    return ClientCallContext(
        state={'http_kwargs': {'headers': {'Authorization': f'Bearer {auth_token}'}}}
    )


def create_auth_token(user_id: int, token_type: str = 'access') -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    if token_type == 'refresh':
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        'user_id': user_id,
        'token_type': token_type,
        'iat': now,
        'exp': expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM), expires_at


def verify_auth_token(token: str, expected_type: str = 'access') -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={'verify_exp': True},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Session expired. Please login again.',
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid auth token: {str(exc)}',
        ) from exc

    token_type = payload.get('token_type')
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid token type. Expected {expected_type}.',
        )
    return payload


def _build_login_response(user: User) -> LoginResponse:
    access_token, access_expires_at = create_auth_token(user.id, token_type='access')
    refresh_token, refresh_expires_at = create_auth_token(
        user.id,
        token_type='refresh',
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        username=user.username,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


def _normalize_card_url(card: AgentCard, base_url: str) -> AgentCard:
    raw_url = (card.url or '').strip()
    if not raw_url:
        return card.model_copy(update={'url': f'{base_url}/'})

    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or '').lower()
    if hostname in {'0.0.0.0', '127.0.0.1', 'localhost'}:
        return card.model_copy(update={'url': f'{base_url}/'})
    return card


async def _resolve_agent_card(req: AgentConnectRequest) -> AgentCard:
    base_url = req.base_url.rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=60.0)) as client:
            resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
            public_card = _normalize_card_url(await resolver.get_agent_card(), base_url)

            if req.mode == AgentMode.public.value:
                return public_card

            if req.mode != AgentMode.authorized.value:
                raise HTTPException(status_code=400, detail='Unsupported mode.')
            if not req.auth_token:
                raise HTTPException(
                    status_code=400,
                    detail='auth_token is required for authorized mode.',
                )
            if not public_card.supports_authenticated_extended_card:
                raise HTTPException(
                    status_code=400,
                    detail='Agent does not advertise authenticated extended card support.',
                )

            cfg = ClientConfig(
                httpx_client=client,
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                streaming=bool(public_card.capabilities.streaming),
            )
            a2a_client = ClientFactory(cfg).create(public_card)
            call_context = _auth_context(req.auth_token)
            try:
                extended_card = _normalize_card_url(
                    await a2a_client.get_card(context=call_context),
                    base_url,
                )
            finally:
                await a2a_client.close()

            public_json = public_card.model_dump(exclude_none=True, by_alias=True)
            extended_json = extended_card.model_dump(exclude_none=True, by_alias=True)
            if extended_json == public_json:
                raise HTTPException(
                    status_code=401,
                    detail='Auth verification failed: token did not unlock extended card.',
                )
            return extended_card
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f'Agent endpoint returned HTTP {exc.response.status_code}. '
                'Verify the base URL is publicly accessible and serves '
                '`/.well-known/agent-card.json` without browser login.'
            ),
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f'Network error while connecting to agent: {exc}.',
        ) from exc
    except Exception as exc:
        if 'Failed to parse JSON for agent card' in str(exc):
            raise HTTPException(
                status_code=503,
                detail=(
                    'Agent card endpoint did not return JSON. '
                    'This usually means the URL points to a web/login page. '
                    'Use the direct public A2A service base URL.'
                ),
            ) from exc
        raise HTTPException(
            status_code=503,
            detail='Agent cannot be connected right now.',
        ) from exc


async def _check_agent_connection(agent: AgentConnection) -> bool:
    req = AgentConnectRequest(
        base_url=agent.base_url,
        mode=agent.mode.value if hasattr(agent.mode, 'value') else str(agent.mode),
        auth_token=agent.auth_token,
    )
    try:
        await _resolve_agent_card(req)
        return True
    except HTTPException:
        return False


async def _sync_agent_status(agent: AgentConnection, db: Session) -> bool:
    is_connected = await _check_agent_connection(agent)
    new_status = 'connected' if is_connected else 'disconnected'
    if agent.status != new_status:
        agent.status = new_status
        db.commit()
        db.refresh(agent)
    return is_connected


async def _sync_agents_status(rows: list[AgentConnection], db: Session) -> None:
    if not rows:
        return

    async def _check_with_timeout(row: AgentConnection) -> bool:
        try:
            return await asyncio.wait_for(
                _check_agent_connection(row),
                timeout=AGENT_STATUS_CHECK_TIMEOUT_SECONDS,
            )
        except Exception:
            return False

    statuses = await asyncio.gather(*[_check_with_timeout(row) for row in rows])
    changed = False
    for row, is_connected in zip(rows, statuses):
        new_status = 'connected' if is_connected else 'disconnected'
        if row.status != new_status:
            row.status = new_status
            changed = True
    if changed:
        db.commit()


def _require_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or credentials.scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing bearer token.',
        )
    token = credentials.credentials.strip()
    payload = verify_auth_token(token, expected_type='access')
    user_id = payload.get('user_id')
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid auth token payload.',
        )
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User not found.',
        )
    return user


@app.get('/api/health')
def health():
    return {'status': 'ok'}


@app.post('/api/login', response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail='Invalid credentials.')
    return _build_login_response(user)


@app.post('/api/register', response_model=LoginResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters.')
    if len(password) < 3:
        raise HTTPException(status_code=400, detail='Password must be at least 3 characters.')

    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise HTTPException(status_code=409, detail='Username already exists.')

    user = User(username=username, password=password)
    db.add(user)
    db.commit()
    db.refresh(user)

    return _build_login_response(user)


@app.post('/api/refresh', response_model=RefreshResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    refresh_payload = verify_auth_token(payload.refresh_token, expected_type='refresh')
    user_id = refresh_payload.get('user_id')
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail='Invalid refresh token payload.')
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail='User not found.')

    access_token, access_expires_at = create_auth_token(user.id, token_type='access')
    refresh_token, refresh_expires_at = create_auth_token(user.id, token_type='refresh')
    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


@app.get('/api/agents', response_model=list[AgentSummary])
async def list_agents(
    refresh_status: bool = Query(default=False),
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(AgentConnection)
        .where(AgentConnection.user_id == user.id)
        .order_by(AgentConnection.updated_at.desc())
    ).all()
    if refresh_status:
        await _sync_agents_status(rows, db)
    return [_serialize_agent(row) for row in rows]


@app.get('/api/agents/{agent_id}', response_model=AgentDetail)
def get_agent_detail(
    agent_id: int,
    user: User = Depends(_require_user),
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
    return _serialize_agent_detail(agent, mode_rows)


@app.post('/api/agents', response_model=AgentSummary, status_code=201)
async def connect_agent(
    payload: AgentConnectRequest,
    user: User = Depends(_require_user),
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

    card = await _resolve_agent_card(payload)
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
    return _serialize_agent(row)


@app.post('/api/agents/{agent_id}/refresh-status', response_model=AgentSummary)
async def refresh_agent_status(
    agent_id: int,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    await _sync_agent_status(agent, db)
    return _serialize_agent(agent)


@app.get('/api/agents/{agent_id}/sessions', response_model=list[SessionSummary])
def list_sessions(
    agent_id: int,
    user: User = Depends(_require_user),
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
    return [_serialize_session(s) for s in sessions]


@app.post('/api/agents/{agent_id}/sessions', response_model=SessionSummary, status_code=201)
async def create_session(
    agent_id: int,
    payload: SessionCreateRequest,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    agent = db.get(AgentConnection, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail='Agent not found.')
    is_connected = await _sync_agent_status(agent, db)
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
    return _serialize_session(session)


@app.get('/api/sessions/{session_id}/messages', response_model=list[MessageSummary])
def get_messages(
    session_id: int,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail='Session not found.')
    if session.chat_status == 0:
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


@app.post('/api/sessions/{session_id}/stream')
async def stream_chat(
    session_id: int,
    payload: ChatRequest,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail='Session not found.')
    if session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')

    agent = db.get(AgentConnection, session.agent_connection_id)
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found.')
    is_connected = await _sync_agent_status(agent, db)
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
        session.title = payload.message[:60]
    if session.chat_status == -1:
        session.chat_status = 1
    db.commit()

    card = AgentCard.model_validate(agent.card_payload)
    auth_token = agent.auth_token if agent.mode == AgentMode.authorized else None

    async def event_stream():
        httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=60.0))
        cfg = ClientConfig(
            httpx_client=httpx_client,
            supported_transports=[
                TransportProtocol.jsonrpc,
                TransportProtocol.http_json,
            ],
            streaming=bool(card.capabilities.streaming),
        )
        a2a_client = ClientFactory(cfg).create(card)
        call_context = _auth_context(auth_token)
        assistant_text = ''
        try:
            request = Message(
                role=Role.user,
                parts=[Part(TextPart(text=payload.message))],
                message_id=str(uuid4()),
                context_id=session.context_id,
            )
            yield f"data: {json.dumps({'type': 'start'})}\n\n"
            async for response in a2a_client.send_message(request, context=call_context):
                if isinstance(response, tuple):
                    task, update = response
                    text = _extract_text_from_task_event(task, update)
                else:
                    text = get_message_text(response)
                if text:
                    assistant_text = text
                    yield (
                        f"data: {json.dumps({'type': 'assistant_snapshot', 'text': text})}\n\n"
                    )

            if assistant_text:
                db2 = next(get_db())
                try:
                    db_session = db2.get(ChatSession, session.id)
                    if db_session:
                        db2.add(
                            ChatMessage(
                                session_id=db_session.id,
                                role='assistant',
                                content=assistant_text,
                            )
                        )
                        db_session.updated_at = datetime.now(timezone.utc)
                        db2.commit()
                finally:
                    db2.close()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            db3 = next(get_db())
            try:
                db_agent = db3.get(AgentConnection, agent.id)
                if db_agent:
                    db_agent.status = 'disconnected'
                    db3.commit()
            finally:
                db3.close()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            await a2a_client.close()
            await httpx_client.aclose()

    return StreamingResponse(event_stream(), media_type='text/event-stream')


@app.patch('/api/sessions/{session_id}/rename', response_model=SessionSummary)
def rename_session(
    session_id: int,
    payload: SessionRenameRequest,
    user: User = Depends(_require_user),
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
    return _serialize_session(session)


@app.post('/api/sessions/{session_id}/archive', response_model=SessionSummary)
def archive_session(
    session_id: int,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = -1
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _serialize_session(session)


@app.post('/api/sessions/{session_id}/unarchive', response_model=SessionSummary)
def unarchive_session(
    session_id: int,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id or session.chat_status == 0:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = 1
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _serialize_session(session)


@app.post('/api/sessions/{session_id}/delete', response_model=SessionSummary)
def delete_session(
    session_id: int,
    user: User = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = db.get(ChatSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail='Session not found.')
    session.chat_status = 0
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return _serialize_session(session)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=8000)

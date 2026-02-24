import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import AgentCard, TransportProtocol
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import AGENT_STATUS_CACHE_TTL_SECONDS, AGENT_STATUS_CHECK_TIMEOUT_SECONDS
from database import SessionLocal
from models import AgentConnection, AgentMode
from schemas import AgentConnectRequest
from services.serialization import auth_context


class AgentStatusManager:
    def __init__(self, ttl_seconds: int = AGENT_STATUS_CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[int, tuple[str, datetime]] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    def get_cached_status(self, agent_id: int) -> str | None:
        value = self._cache.get(agent_id)
        if not value:
            return None
        status, checked_at = value
        if datetime.now(timezone.utc) - checked_at > timedelta(seconds=self.ttl_seconds):
            return None
        return status

    def set_cached_status(self, agent_id: int, status: str) -> None:
        self._cache[agent_id] = (status, datetime.now(timezone.utc))

    def schedule_refresh(self, agent_id: int) -> None:
        task = self._tasks.get(agent_id)
        if task and not task.done():
            return
        self._tasks[agent_id] = asyncio.create_task(self._refresh_with_new_session(agent_id))

    async def _refresh_with_new_session(self, agent_id: int) -> None:
        db = SessionLocal()
        try:
            agent = db.get(AgentConnection, agent_id)
            if not agent:
                self._cache.pop(agent_id, None)
                return
            is_connected = await asyncio.wait_for(
                check_agent_connection(agent),
                timeout=AGENT_STATUS_CHECK_TIMEOUT_SECONDS,
            )
            new_status = 'connected' if is_connected else 'disconnected'
            if agent.status != new_status:
                agent.status = new_status
                db.commit()
            self.set_cached_status(agent_id, new_status)
        except Exception:
            self.set_cached_status(agent_id, 'disconnected')
        finally:
            db.close()
            self._tasks.pop(agent_id, None)

    async def refresh_now(self, agent: AgentConnection, db: Session) -> bool:
        try:
            is_connected = await asyncio.wait_for(
                check_agent_connection(agent),
                timeout=AGENT_STATUS_CHECK_TIMEOUT_SECONDS,
            )
        except Exception:
            is_connected = False
        new_status = 'connected' if is_connected else 'disconnected'
        if agent.status != new_status:
            agent.status = new_status
            db.commit()
            db.refresh(agent)
        self.set_cached_status(agent.id, new_status)
        return is_connected


status_manager = AgentStatusManager()


def normalize_card_url(card: AgentCard, base_url: str) -> AgentCard:
    raw_url = (card.url or '').strip()
    if not raw_url:
        return card.model_copy(update={'url': f'{base_url}/'})

    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or '').lower()
    if hostname in {'0.0.0.0', '127.0.0.1', 'localhost'}:
        return card.model_copy(update={'url': f'{base_url}/'})
    return card


async def resolve_agent_card(req: AgentConnectRequest) -> AgentCard:
    base_url = req.base_url.rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=60.0)) as client:
            resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
            public_card = normalize_card_url(await resolver.get_agent_card(), base_url)

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
            call_context = auth_context(req.auth_token)
            try:
                extended_card = normalize_card_url(
                    await a2a_client.get_card(context=call_context),
                    base_url,
                )
            finally:
                await a2a_client.close()

            public_json = public_card.model_dump(exclude_none=True, by_alias=True)
            extended_json = extended_card.model_dump(exclude_none=True, by_alias=True)
            if extended_json == public_json:
                raise HTTPException(
                    status_code=400,
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


async def check_agent_connection(agent: AgentConnection) -> bool:
    req = AgentConnectRequest(
        base_url=agent.base_url,
        mode=agent.mode.value if hasattr(agent.mode, 'value') else str(agent.mode),
        auth_token=agent.auth_token,
    )
    try:
        await resolve_agent_card(req)
        return True
    except HTTPException:
        return False


async def sync_agents_status_fast(rows: list[AgentConnection]) -> None:
    # Fast path: return cached status and schedule background refresh for stale entries.
    for row in rows:
        cached = status_manager.get_cached_status(row.id)
        if cached:
            row.status = cached
        else:
            status_manager.schedule_refresh(row.id)

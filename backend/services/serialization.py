from a2a.client.middleware import ClientCallContext
from a2a.utils.message import get_message_text

from models import AgentConnection, ChatSession
from schemas import (
    AgentAnalytics,
    AgentBenchmark,
    AgentDetail,
    AgentModeCard,
    AgentRegistryMetadata,
    AgentSummary,
    SessionSummary,
)
from services.agent_registry import average_rating


def serialize_agent(agent: AgentConnection) -> AgentSummary:
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
        capability_tags=agent.capability_tags or [],
        registry_metadata=AgentRegistryMetadata(**(agent.registry_metadata or {})),
        benchmarks=AgentBenchmark(
            latency_ms=agent.benchmark_latency_ms,
            cost=agent.benchmark_cost,
            success_rate=agent.benchmark_success_rate,
        ),
        analytics=AgentAnalytics(
            usage_count=agent.usage_count or 0,
            success_count=agent.success_count or 0,
            failure_count=agent.failure_count or 0,
            rating_average=average_rating(agent),
            rating_count=agent.rating_count or 0,
            last_used_at=agent.last_used_at,
        ),
        created_at=agent.created_at,
    )


def serialize_agent_detail(
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
        capability_tags=agent.capability_tags or [],
        registry_metadata=AgentRegistryMetadata(**(agent.registry_metadata or {})),
        benchmarks=AgentBenchmark(
            latency_ms=agent.benchmark_latency_ms,
            cost=agent.benchmark_cost,
            success_rate=agent.benchmark_success_rate,
        ),
        analytics=AgentAnalytics(
            usage_count=agent.usage_count or 0,
            success_count=agent.success_count or 0,
            failure_count=agent.failure_count or 0,
            rating_average=average_rating(agent),
            rating_count=agent.rating_count or 0,
            last_used_at=agent.last_used_at,
        ),
        modes=mode_cards,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def serialize_session(session: ChatSession) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        context_id=session.context_id,
        title=session.title,
        summary=session.summary,
        tags=session.tags or [],
        chat_status=session.chat_status if session.chat_status is not None else 1,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def extract_text_from_task_event(task, update) -> str:
    if task and getattr(task, 'artifacts', None):
        return get_message_text(task.artifacts[-1])

    status_update = getattr(update, 'status', None)
    if status_update and getattr(status_update, 'message', None):
        return get_message_text(status_update.message)

    task_status = getattr(task, 'status', None)
    if task_status and getattr(task_status, 'message', None):
        return get_message_text(task_status.message)

    return ''


def auth_context(auth_token: str | None) -> ClientCallContext | None:
    if not auth_token:
        return None
    return ClientCallContext(
        state={'http_kwargs': {'headers': {'Authorization': f'Bearer {auth_token}'}}}
    )

from __future__ import annotations

from datetime import datetime, timezone

from models import AgentConnection


DEFAULT_TAG_KEYWORDS = {
    'reasoning': {'reason', 'math', 'calculation', 'analysis', 'logic'},
    'vision': {'vision', 'image', 'ocr', 'multimodal'},
    'trading': {'trading', 'market', 'stocks', 'crypto', 'finance'},
    'scraping': {'scraping', 'crawl', 'extract', 'browser', 'web'},
    'search': {'search', 'retrieval', 'rag', 'lookup'},
    'code': {'code', 'coding', 'programming', 'developer'},
    'speech': {'speech', 'voice', 'audio', 'transcribe', 'stt'},
    'workflow': {'workflow', 'automation', 'orchestrator', 'agentic'},
}


def derive_registry_metadata(card_payload: dict, base_url: str) -> dict:
    return {
        'protocol_version': card_payload.get('protocolVersion')
        or card_payload.get('protocol_version'),
        'preferred_transport': card_payload.get('preferredTransport')
        or card_payload.get('preferred_transport'),
        'agent_url': card_payload.get('url') or base_url,
        'provider': card_payload.get('provider') or 'community',
        'version': card_payload.get('version'),
        'default_input_modes': card_payload.get('defaultInputModes')
        or card_payload.get('default_input_modes')
        or [],
        'default_output_modes': card_payload.get('defaultOutputModes')
        or card_payload.get('default_output_modes')
        or [],
    }


def derive_capability_tags(card_payload: dict) -> list[str]:
    tags: set[str] = set()
    skills = card_payload.get('skills') or []
    searchable_parts = [
        str(card_payload.get('name') or ''),
        str(card_payload.get('description') or ''),
    ]
    for skill in skills:
        searchable_parts.extend(
            [
                str(skill.get('name') or ''),
                str(skill.get('description') or ''),
                ' '.join(str(tag or '') for tag in (skill.get('tags') or [])),
            ]
        )
        for tag in skill.get('tags') or []:
            if tag:
                tags.add(str(tag).strip().lower())

    combined = ' '.join(searchable_parts).lower()
    for tag_name, keywords in DEFAULT_TAG_KEYWORDS.items():
        if any(keyword in combined for keyword in keywords):
            tags.add(tag_name)
    return sorted(tag for tag in tags if tag)


def update_benchmark_latency(agent: AgentConnection, latency_ms: int) -> None:
    if latency_ms <= 0:
        return
    previous = agent.benchmark_latency_ms
    if previous is None:
        agent.benchmark_latency_ms = latency_ms
        return
    agent.benchmark_latency_ms = int(round((previous * 0.7) + (latency_ms * 0.3)))


def usage_success_rate(agent: AgentConnection) -> float:
    total = (agent.success_count or 0) + (agent.failure_count or 0)
    if total <= 0:
        return 0.0
    return round((agent.success_count or 0) / total, 4)


def average_rating(agent: AgentConnection) -> float:
    if not agent.rating_count:
        return 0.0
    return round((agent.rating_total or 0) / agent.rating_count, 2)


def record_agent_usage(
    agent: AgentConnection,
    *,
    latency_ms: int | None = None,
    success: bool,
) -> None:
    agent.usage_count = (agent.usage_count or 0) + 1
    agent.last_used_at = datetime.now(timezone.utc)
    if success:
        agent.success_count = (agent.success_count or 0) + 1
    else:
        agent.failure_count = (agent.failure_count or 0) + 1
    if latency_ms is not None:
        update_benchmark_latency(agent, latency_ms)
    agent.benchmark_success_rate = usage_success_rate(agent)


def record_agent_rating(agent: AgentConnection, rating: int) -> None:
    agent.rating_total = (agent.rating_total or 0) + rating
    agent.rating_count = (agent.rating_count or 0) + 1

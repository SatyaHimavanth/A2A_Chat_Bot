import asyncio
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from deps import require_user
from models import AgentConnection, User
from schemas import (
    PlaygroundAgentResult,
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
)
from services.agent_transport import send_agent_message

router = APIRouter(prefix='/api/playground', tags=['playground'])


async def _query_agent(
    agent: AgentConnection,
    message: str,
    context_id: str | None,
) -> PlaygroundAgentResult:
    started = perf_counter()
    resolved_context_id = context_id or str(uuid4())

    try:
        response_text = await send_agent_message(agent, message, resolved_context_id)
        return PlaygroundAgentResult(
            agent_id=agent.id,
            card_name=agent.card_name,
            mode=agent.mode.value if hasattr(agent.mode, 'value') else str(agent.mode),
            context_id=resolved_context_id,
            latency_ms=int((perf_counter() - started) * 1000),
            response=response_text,
            status='ok',
        )
    except Exception as exc:
        return PlaygroundAgentResult(
            agent_id=agent.id,
            card_name=agent.card_name,
            mode=agent.mode.value if hasattr(agent.mode, 'value') else str(agent.mode),
            context_id=resolved_context_id,
            latency_ms=int((perf_counter() - started) * 1000),
            response='',
            error=str(exc),
            status='error',
        )


@router.post('/compare', response_model=PlaygroundCompareResponse)
async def compare_agents(
    payload: PlaygroundCompareRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail='Message cannot be empty.')

    agent_ids = sorted(set(payload.agent_ids))
    rows = db.scalars(
        select(AgentConnection).where(
            AgentConnection.user_id == user.id,
            AgentConnection.id.in_(agent_ids),
        )
    ).all()
    by_id = {row.id: row for row in rows}
    missing = [aid for aid in agent_ids if aid not in by_id]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f'Agent(s) not found: {missing}',
        )

    tasks = [
        _query_agent(
            by_id[aid],
            message,
            payload.context_ids.get(aid),
        )
        for aid in agent_ids
    ]
    results = await asyncio.gather(*tasks)
    return PlaygroundCompareResponse(results=results)

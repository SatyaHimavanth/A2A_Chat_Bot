from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database import get_db
from deps import require_user
from models import AgentConnection, PromptTemplate, User
from schemas import (
    PromptTemplateCreateRequest,
    PromptTemplateSummary,
    PromptTemplateUpdateRequest,
)

router = APIRouter(prefix='/api', tags=['prompts'])


def _serialize_prompt(row: PromptTemplate) -> PromptTemplateSummary:
    return PromptTemplateSummary(
        id=row.id,
        title=row.title,
        content=row.content,
        agent_id=row.agent_connection_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get('/prompts', response_model=list[PromptTemplateSummary])
def list_prompts(
    agent_id: int | None = Query(default=None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if agent_id is not None:
        agent = db.get(AgentConnection, agent_id)
        if not agent or agent.user_id != user.id:
            raise HTTPException(status_code=404, detail='Agent not found.')
        rows = db.scalars(
            select(PromptTemplate)
            .where(
                PromptTemplate.user_id == user.id,
                or_(
                    PromptTemplate.agent_connection_id.is_(None),
                    PromptTemplate.agent_connection_id == agent_id,
                ),
            )
            .order_by(PromptTemplate.updated_at.desc())
        ).all()
    else:
        rows = db.scalars(
            select(PromptTemplate)
            .where(PromptTemplate.user_id == user.id)
            .order_by(PromptTemplate.updated_at.desc())
        ).all()
    return [_serialize_prompt(row) for row in rows]


@router.post('/prompts', response_model=PromptTemplateSummary, status_code=201)
def create_prompt(
    payload: PromptTemplateCreateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    content = payload.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail='Prompt title cannot be empty.')
    if not content:
        raise HTTPException(status_code=400, detail='Prompt content cannot be empty.')

    agent_id = payload.agent_id
    if agent_id is not None:
        agent = db.get(AgentConnection, agent_id)
        if not agent or agent.user_id != user.id:
            raise HTTPException(status_code=404, detail='Agent not found.')

    row = PromptTemplate(
        user_id=user.id,
        agent_connection_id=agent_id,
        title=title[:255],
        content=content,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_prompt(row)


@router.patch('/prompts/{prompt_id}', response_model=PromptTemplateSummary)
def update_prompt(
    prompt_id: int,
    payload: PromptTemplateUpdateRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(PromptTemplate, prompt_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail='Prompt not found.')
    title = payload.title.strip()
    content = payload.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail='Prompt title cannot be empty.')
    if not content:
        raise HTTPException(status_code=400, detail='Prompt content cannot be empty.')
    row.title = title[:255]
    row.content = content
    db.commit()
    db.refresh(row)
    return _serialize_prompt(row)


@router.delete('/prompts/{prompt_id}', status_code=204)
def delete_prompt(
    prompt_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(PromptTemplate, prompt_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail='Prompt not found.')
    db.delete(row)
    db.commit()

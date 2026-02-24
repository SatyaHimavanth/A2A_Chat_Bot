import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import ChatMessage, ChatSession

_STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'how', 'i',
    'in', 'is', 'it', 'of', 'on', 'or', 'that', 'the', 'this', 'to', 'we', 'you',
    'with', 'what', 'can', 'please', 'me', 'my', 'your', 'our', 'was', 'were',
}


def _clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def refine_title(message: str, limit: int = 60) -> str:
    text = _clean_text(message)
    if not text:
        return 'New chat'
    text = re.sub(r'^[\W_]+|[\W_]+$', '', text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + '...'


def _extract_tags(text: str, max_tags: int = 6) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", (text or '').lower())
    filtered = [w for w in words if w not in _STOPWORDS]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(max_tags)]


def _build_summary(messages: list[ChatMessage], limit: int = 220) -> str | None:
    if not messages:
        return None
    user_first = next((m.content for m in messages if m.role == 'user' and m.content), '')
    assistant_last = next(
        (m.content for m in reversed(messages) if m.role == 'assistant' and m.content),
        '',
    )
    summary = _clean_text(f"{user_first} {assistant_last}".strip())
    if not summary:
        return None
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + '...'


def update_session_intelligence(db: Session, session: ChatSession) -> None:
    msgs = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()

    if session.title == 'New chat':
        first_user = next((m.content for m in msgs if m.role == 'user'), '')
        if first_user:
            session.title = refine_title(first_user)

    session.summary = _build_summary(msgs)
    combined = ' '.join(m.content for m in msgs if m.content)
    session.tags = _extract_tags(combined)

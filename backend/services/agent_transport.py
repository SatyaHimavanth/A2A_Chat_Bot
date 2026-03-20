from uuid import uuid4

import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, TextPart, TransportProtocol
from a2a.utils.message import get_message_text

from core.config import STREAM_CONNECT_TIMEOUT_SECONDS, STREAM_READ_TIMEOUT_SECONDS
from models import AgentConnection, AgentMode
from services.serialization import auth_context, extract_text_from_task_event


def build_transport_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=STREAM_CONNECT_TIMEOUT_SECONDS,
        read=STREAM_READ_TIMEOUT_SECONDS,
        write=STREAM_CONNECT_TIMEOUT_SECONDS,
        pool=STREAM_CONNECT_TIMEOUT_SECONDS,
    )


def extract_lightweight_text(result: dict) -> str:
    message = result.get('message') or {}
    parts = message.get('parts') or []
    text_parts = [
        part.get('text', '').strip()
        for part in parts
        if isinstance(part, dict) and part.get('kind') == 'text'
    ]
    text = ' '.join(part for part in text_parts if part).strip()
    if text:
        return text

    content = result.get('content')
    if isinstance(content, str):
        return content.strip()
    return ''


async def _send_via_a2a(agent: AgentConnection, prompt: str, context_id: str) -> str:
    card = AgentCard.model_validate(agent.card_payload)
    auth_token = agent.auth_token if agent.mode == AgentMode.authorized else None
    assistant_text = ''

    httpx_client = httpx.AsyncClient(timeout=build_transport_timeout())
    cfg = ClientConfig(
        httpx_client=httpx_client,
        supported_transports=[
            TransportProtocol.jsonrpc,
            TransportProtocol.http_json,
        ],
        streaming=bool(card.capabilities.streaming),
    )
    a2a_client = ClientFactory(cfg).create(card)

    try:
        request = Message(
            role=Role.user,
            parts=[Part(TextPart(text=prompt))],
            message_id=str(uuid4()),
            context_id=context_id,
        )
        async for response in a2a_client.send_message(
            request,
            context=auth_context(auth_token),
        ):
            if isinstance(response, tuple):
                task, update = response
                text = extract_text_from_task_event(task, update)
            else:
                text = get_message_text(response)
            if text:
                assistant_text = text
        return assistant_text
    finally:
        await a2a_client.close()
        await httpx_client.aclose()


async def _send_via_lightweight_jsonrpc(
    agent: AgentConnection,
    prompt: str,
    context_id: str,
) -> str:
    headers = {'Content-Type': 'application/json'}
    if agent.mode == AgentMode.authorized and agent.auth_token:
        headers['Authorization'] = f'Bearer {agent.auth_token}'

    payload = {
        'jsonrpc': '2.0',
        'id': str(uuid4()),
        'method': 'message/send',
        'params': {
            'message': {
                'messageId': str(uuid4()),
                'contextId': context_id,
                'role': 'user',
                'parts': [{'kind': 'text', 'text': prompt}],
            },
            'configuration': {'blocking': True},
        },
    }

    async with httpx.AsyncClient(timeout=build_transport_timeout()) as client:
        response = await client.post(
            f"{agent.base_url.rstrip('/')}/",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    if data.get('error'):
        message = data['error'].get('message') or 'Lightweight agent returned an error.'
        raise RuntimeError(message)

    result = data.get('result') or {}
    return extract_lightweight_text(result)


async def send_agent_message(agent: AgentConnection, prompt: str, context_id: str) -> str:
    a2a_error: Exception | None = None
    try:
        return await _send_via_a2a(agent, prompt, context_id)
    except Exception as exc:
        a2a_error = exc

    try:
        return await _send_via_lightweight_jsonrpc(agent, prompt, context_id)
    except Exception as exc:
        if a2a_error is not None:
            raise RuntimeError(
                f'A2A transport failed: {a2a_error}; lightweight JSON-RPC failed: {exc}'
            ) from exc
        raise

import logging
from typing import Any
from uuid import uuid4

import click
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
)

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = '0.1.0'
SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']
context_history: dict[str, list[str]] = {}


def build_agent_card(host: str, port: int) -> dict[str, Any]:
    return {
        'name': 'Dummy FastAPI Agent',
        'description': 'Sample lightweight agent using an A2A-like JSON-RPC format.',
        'url': f'http://{host}:{port}/',
        'version': '1.0.0',
        'protocolVersion': PROTOCOL_VERSION,
        'preferredTransport': 'JSONRPC',
        'defaultInputModes': SUPPORTED_CONTENT_TYPES,
        'defaultOutputModes': SUPPORTED_CONTENT_TYPES,
        'capabilities': {
            'streaming': False,
            'pushNotifications': False,
        },
        'supportsAuthenticatedExtendedCard': False,
        'securitySchemes': {},
        'skills': [
            {
                'id': 'dummy_chat_agent',
                'name': 'Dummy Chat Agent',
                'description': 'Replies to text prompts and remembers prior turns by contextId.',
                'tags': ['chat', 'demo', 'echo', 'fastapi'],
                'examples': [
                    'hello',
                    'summarize what we just talked about',
                ],
            }
        ],
    }


def build_text_message(text: str, context_id: str | None) -> dict[str, Any]:
    return {
        'messageId': str(uuid4()),
        'contextId': context_id or str(uuid4()),
        'role': 'agent',
        'parts': [
            {
                'kind': 'text',
                'text': text,
            }
        ],
    }


def jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'result': result,
    }


def jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {
        'code': code,
        'message': message,
    }
    if data is not None:
        error['data'] = data
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': error,
    }


def extract_user_text(message: dict[str, Any] | None) -> str:
    if not message:
        return ''

    parts = message.get('parts') or []
    text_parts = [
        part.get('text', '').strip()
        for part in parts
        if isinstance(part, dict) and part.get('kind') == 'text'
    ]
    return ' '.join(part for part in text_parts if part).strip()


def generate_reply(user_text: str, context_id: str) -> str:
    history = context_history.setdefault(context_id, [])
    history.append(user_text)

    normalized = user_text.lower()
    if not user_text:
        return 'I did not receive any text input. Please send a text part.'
    if 'history' in normalized or 'what did i say' in normalized:
        prior_turns = ', '.join(history[:-1]) if len(history) > 1 else 'nothing yet'
        return f'Current context is {context_id}. Before this message you said: {prior_turns}.'
    if 'summary' in normalized or 'summarize' in normalized:
        return f'This conversation currently has {len(history)} user turns. Latest prompt: {user_text}'

    return (
        'Hello from the dummy FastAPI agent. '
        f'You said: {user_text}. '
        f'Context: {context_id}. '
        f'This is turn {len(history)} in the conversation.'
    )


def create_app(host: str, port: int) -> FastAPI:
    app = FastAPI(title='Dummy FastAPI Agent')
    agent_card = build_agent_card(host, port)

    @app.get('/.well-known/agent-card.json')
    async def get_agent_card() -> dict[str, Any]:
        return agent_card

    @app.post('/')
    async def jsonrpc_handler(payload: dict[str, Any]) -> JSONResponse:
        print("Request:", payload)
        request_id = payload.get('id')
        method = payload.get('method')
        params = payload.get('params') or {}

        if payload.get('jsonrpc') != '2.0':
            return JSONResponse(
                status_code=400,
                content=jsonrpc_error(request_id, -32600, 'Invalid Request', 'jsonrpc must be 2.0'),
            )

        if method == 'agent/getCard':
            return JSONResponse(content=jsonrpc_result(request_id, agent_card))

        if method == 'message/stream':
            return JSONResponse(
                status_code=400,
                content=jsonrpc_error(
                    request_id,
                    -32601,
                    'Method not supported',
                    'This sample agent only supports message/send.',
                ),
            )

        if method != 'message/send':
            return JSONResponse(
                status_code=404,
                content=jsonrpc_error(request_id, -32601, 'Method not found'),
            )

        message = params.get('message') or {}
        context_id = message.get('contextId') or str(uuid4())
        user_text = extract_user_text(message)
        reply_text = generate_reply(user_text, context_id)

        result = {
            'status': 'completed',
            'isTaskComplete': True,
            'requireUserInput': False,
            'message': build_text_message(reply_text, context_id),
        }
        return JSONResponse(content=jsonrpc_result(request_id, result))

    return app


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=11000)
def main(host: str, port: int) -> None:
    logger.info('Starting dummy FastAPI agent on http://%s:%s', host, port)
    app = create_app(host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    main()

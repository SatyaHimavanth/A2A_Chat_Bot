# Dummy FastAPI Agent

This is a sample agent that exposes:

- `GET /.well-known/agent-card.json`
- `POST /` using a lightweight JSON-RPC contract
- optional bearer-token based extended card support

It is intentionally similar to A2A, but it is not a full A2A server.

## Run

```bash
uv run .
```

Authorized token for extended mode:

```text
dummy-token-for-extended-card
```

## Supported JSON-RPC methods

### `agent/getCard`

Request:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "agent/getCard"
}
```

If the request includes:

```text
Authorization: Bearer dummy-token-for-extended-card
```

then the agent returns an extended card with additional skills.

### `message/send`

Request:

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "m-1",
      "contextId": "ctx-1",
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "hello"
        }
      ]
    },
    "configuration": {
      "blocking": true
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "result": {
    "status": "completed",
    "isTaskComplete": true,
    "requireUserInput": false,
    "message": {
      "messageId": "resp-123",
      "contextId": "ctx-1",
      "role": "agent",
      "parts": [
        {
          "kind": "text",
          "text": "Hello from the dummy FastAPI agent."
        }
      ]
    }
  }
}
```

## Notes

- `message/stream` is not implemented in this sample.
- The card sets `streaming=false` to make that explicit.

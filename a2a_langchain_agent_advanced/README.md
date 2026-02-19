# Project setup
```bash
uv sync
```

# Start hosting calculator agent (__main__.py)
```bash
uv run .
```

# Test it using 
```bash
uv run test_client.py
```

# Auth testing (advanced tools: power, root)
Set `A2A_AUTH_TOKEN` in `.env` for authorized mode, or unset it for basic mode.
Server-side valid tokens come from `A2A_AUTH_TOKENS` (comma-separated).

# Integrate it with google adk and test
```bash
adk web
```

# A2A Chat Dashboard (FastAPI + React + SQLAlchemy)
Backend API (port 8001):
```bash
uv run uvicorn backend.main:app --reload --port 8001
```

Frontend UI (port 5173):
```bash
cd frontend
npm install
npm run dev
```

Dummy login:
- username: `admin`
- password: `admin`

Notes:
- Set `DATABASE_URL` to Postgres for persistence.
- Agent sessions/messages are stored with `context_id` so conversations can continue.
- You can register both `public` and `authorized` modes for the same hosted agent URL.



# Reference links:

## langgraph agent to a2a
```bash
https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/langgraph
```

## Complete git repo
```bash
https://github.com/a2aproject/a2a-samples
```


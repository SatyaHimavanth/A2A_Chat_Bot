from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from database import Base, engine, get_db
from models import User
from routes.agents import router as agents_router
from routes.auth import router as auth_router
from routes.sessions import router as sessions_router


def _run_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        # Lightweight migrations for existing DBs.
        statements = [
            "ALTER TABLE agent_connections ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'connected'",
            "ALTER TABLE chat_sessions ADD COLUMN chat_status INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE chat_sessions ADD COLUMN summary TEXT",
            "ALTER TABLE chat_sessions ADD COLUMN tags JSON NOT NULL DEFAULT '[]'",
        ]
        for stmt in statements:
            try:
                db.execute(text(stmt))
                db.commit()
            except Exception:
                db.rollback()

        existing = db.scalar(select(User).where(User.username == 'admin'))
        if not existing:
            db.add(User(username='admin', password='admin'))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _run_startup()
    yield


app = FastAPI(
    title='A2A Agent Chat Backend',
    version='1.0.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(sessions_router)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, port=8000)

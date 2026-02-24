from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.auth_utils import build_login_response, build_refresh_response, verify_auth_token
from database import get_db
from models import User
from schemas import LoginRequest, LoginResponse, RefreshRequest, RefreshResponse, RegisterRequest

router = APIRouter(prefix='/api', tags=['auth'])


@router.get('/health')
def health():
    return {'status': 'ok'}


@router.post('/login', response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail='Invalid credentials.')
    return build_login_response(user)


@router.post('/register', response_model=LoginResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail='Username must be at least 3 characters.')
    if len(password) < 3:
        raise HTTPException(status_code=400, detail='Password must be at least 3 characters.')

    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise HTTPException(status_code=409, detail='Username already exists.')

    user = User(username=username, password=password)
    db.add(user)
    db.commit()
    db.refresh(user)

    return build_login_response(user)


@router.post('/refresh', response_model=RefreshResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    refresh_payload = verify_auth_token(payload.refresh_token, expected_type='refresh')
    user_id = refresh_payload.get('user_id')
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail='Invalid refresh token payload.')
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail='User not found.')

    return build_refresh_response(user.id)

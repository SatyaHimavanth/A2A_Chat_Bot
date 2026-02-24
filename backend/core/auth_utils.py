from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt

from core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)
from models import User
from schemas import LoginResponse, RefreshResponse


def create_auth_token(user_id: int, token_type: str = 'access') -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    if token_type == 'refresh':
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        'user_id': user_id,
        'token_type': token_type,
        'iat': now,
        'exp': expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM), expires_at


def verify_auth_token(token: str, expected_type: str = 'access') -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={'verify_exp': True},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Session expired. Please login again.',
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid auth token: {str(exc)}',
        ) from exc

    token_type = payload.get('token_type')
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid token type. Expected {expected_type}.',
        )
    return payload


def build_login_response(user: User) -> LoginResponse:
    access_token, access_expires_at = create_auth_token(user.id, token_type='access')
    refresh_token, refresh_expires_at = create_auth_token(
        user.id,
        token_type='refresh',
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        username=user.username,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )


def build_refresh_response(user_id: int) -> RefreshResponse:
    access_token, access_expires_at = create_auth_token(user_id, token_type='access')
    refresh_token, refresh_expires_at = create_auth_token(user_id, token_type='refresh')
    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
    )

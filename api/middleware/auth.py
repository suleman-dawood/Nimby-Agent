"""JWT auth middleware."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.deps import get_session
from scraper.models import User

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_current_user(
    request: Request, session: Session = Depends(get_session),
) -> User:
    """Require authenticated user. Raises 401 if missing/invalid."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    user = session.get(User, payload.get("user_id"))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def get_optional_user(
    request: Request, session: Session = Depends(get_session),
) -> User | None:
    """Return user if authenticated, None otherwise. Never raises."""
    token = _extract_token(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return session.get(User, payload.get("user_id"))
    except Exception:
        return None

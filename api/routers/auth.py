"""Google OAuth authentication endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_session
from api.middleware.auth import JWT_SECRET, JWT_ALGORITHM, get_current_user
from api.schemas.auth import AuthResponse, GoogleAuthRequest, UserResponse
from scraper.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")


def _create_jwt(user: User) -> str:
    payload = {
        "user_id": user.id,
        "email": user.email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        tokens_remaining=user.tokens_remaining,
        tokens_used=user.tokens_used,
    )


def _verify_google_token(token: str) -> dict:
    """Verify a Google token (access_token or id_token) and return user info."""
    # Try as access_token first (from useGoogleLogin implicit flow)
    resp = httpx.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        info = resp.json()
        if info.get("sub"):
            return info

    # Fallback: try as id_token via tokeninfo
    resp = httpx.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
    if resp.status_code == 200:
        info = resp.json()
        if info.get("sub"):
            return info

    raise ValueError("Invalid Google token")


@router.post("/google", response_model=AuthResponse)
def google_auth(req: GoogleAuthRequest, session: Session = Depends(get_session)):
    """Verify Google token (access or ID), create/find user, return JWT."""
    try:
        idinfo = _verify_google_token(req.id_token)
    except ValueError:
        raise HTTPException(401, "Invalid Google token")

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name")
    picture = idinfo.get("picture")
    now = datetime.now(timezone.utc)

    # Find or create user
    user = session.query(User).filter_by(google_id=google_id).first()
    if user:
        user.last_login = now
        if name:
            user.name = name
        if picture:
            user.avatar_url = picture
    else:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=picture,
            tokens_remaining=50,
            tokens_used=0,
            created_at=now,
            last_login=now,
        )
        session.add(user)
    session.commit()
    session.refresh(user)

    token = _create_jwt(user)
    return AuthResponse(token=token, user=_user_response(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return _user_response(user)

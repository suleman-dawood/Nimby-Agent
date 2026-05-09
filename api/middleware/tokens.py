"""Token deduction middleware for AI-costed endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_session
from api.middleware.auth import get_current_user
from scraper.models import TokenUsage, User


class TokenDeductor:
    """Callable that deducts tokens after a successful AI response."""

    def __init__(self, user: User, session: Session, cost: int):
        self.user = user
        self.session = session
        self.cost = cost

    def __call__(self, action: str, pp_number: str | None = None):
        self.user.tokens_remaining -= self.cost
        self.user.tokens_used += self.cost
        usage = TokenUsage(
            user_id=self.user.id,
            action=action,
            tokens_spent=self.cost,
            pp_number=pp_number,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(usage)
        self.session.commit()


def require_tokens(cost: int):
    """FastAPI dependency factory. Checks balance, returns deductor callable."""

    def dependency(
        user: User = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> TokenDeductor:
        if user.tokens_remaining < cost:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient tokens. Need {cost}, have {user.tokens_remaining}.",
            )
        return TokenDeductor(user, session, cost)

    return dependency

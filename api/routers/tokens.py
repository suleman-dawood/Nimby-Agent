"""Token balance and usage history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_session
from api.middleware.auth import get_current_user
from api.schemas.tokens import TokenBalance, TokenHistoryResponse, TokenUsageRecord
from scraper.models import TokenUsage, User

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


@router.get("/balance", response_model=TokenBalance)
def balance(user: User = Depends(get_current_user)):
    return TokenBalance(
        tokens_remaining=user.tokens_remaining,
        tokens_used=user.tokens_used,
    )


@router.get("/history", response_model=TokenHistoryResponse)
def history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    records = (
        session.query(TokenUsage)
        .filter_by(user_id=user.id)
        .order_by(TokenUsage.created_at.desc())
        .limit(50)
        .all()
    )
    return TokenHistoryResponse(
        usage=[
            TokenUsageRecord(
                id=r.id,
                action=r.action,
                tokens_spent=r.tokens_spent,
                pp_number=r.pp_number,
                created_at=r.created_at,
            )
            for r in records
        ]
    )

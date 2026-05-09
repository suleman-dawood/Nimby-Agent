"""Token schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TokenBalance(BaseModel):
    tokens_remaining: int
    tokens_used: int


class TokenUsageRecord(BaseModel):
    id: int
    action: str
    tokens_spent: int
    pp_number: str | None
    created_at: datetime


class TokenHistoryResponse(BaseModel):
    usage: list[TokenUsageRecord]

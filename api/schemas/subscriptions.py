"""Subscription and in-app notification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateSubscriptionRequest(BaseModel):
    pp_number: str
    notify_docs: bool = True
    notify_stage: bool = True
    notify_expiry: bool = True


class SubscriptionResponse(BaseModel):
    id: int
    pp_number: str
    notify_docs: bool
    notify_stage: bool
    notify_expiry: bool
    active: bool
    created_at: datetime


class InAppNotificationResponse(BaseModel):
    id: int
    pp_number: str
    event_type: str
    title: str
    message: str
    read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int

"""Watcher schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateWatcherRequest(BaseModel):
    address: str
    lat: float
    lng: float
    radius_km: float = 5.0
    webhook_url: str | None = None


class WatcherResponse(BaseModel):
    id: int
    email: str
    address: str
    lat: float
    lng: float
    radius_km: float
    webhook_url: str | None
    active: bool
    created_at: datetime


class NotificationResponse(BaseModel):
    id: int
    pp_number: str
    channel: str
    status: str
    sent_at: datetime

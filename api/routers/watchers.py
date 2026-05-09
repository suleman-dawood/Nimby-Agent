"""Watcher CRUD + admin trigger endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_session
from api.middleware.auth import get_current_user
from api.schemas.watchers import CreateWatcherRequest, NotificationResponse, WatcherResponse
from scraper.models import Notification, User, Watcher

router = APIRouter(prefix="/api/watchers", tags=["watchers"])


def _to_response(w: Watcher) -> WatcherResponse:
    return WatcherResponse(
        id=w.id,
        email=w.email,
        address=w.address,
        lat=w.lat,
        lng=w.lng,
        radius_km=w.radius_km,
        webhook_url=w.webhook_url,
        active=w.active,
        created_at=w.created_at,
    )


@router.post("", response_model=WatcherResponse)
def create_watcher(
    req: CreateWatcherRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Register a new address watcher."""
    watcher = Watcher(
        user_id=user.id,
        email=user.email,
        address=req.address,
        lat=req.lat,
        lng=req.lng,
        radius_km=req.radius_km,
        webhook_url=req.webhook_url,
        created_at=datetime.now(timezone.utc),
        active=True,
    )
    session.add(watcher)
    session.commit()
    session.refresh(watcher)
    return _to_response(watcher)


@router.get("", response_model=list[WatcherResponse])
def list_watchers(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List active watchers for current user."""
    watchers = (
        session.query(Watcher)
        .filter_by(user_id=user.id, active=True)
        .order_by(Watcher.created_at.desc())
        .all()
    )
    return [_to_response(w) for w in watchers]


@router.delete("/{watcher_id}")
def delete_watcher(
    watcher_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Deactivate a watcher. Must own it."""
    watcher = session.get(Watcher, watcher_id)
    if not watcher or watcher.user_id != user.id:
        raise HTTPException(404, "Watcher not found")
    watcher.active = False
    session.commit()
    return {"status": "deleted"}


@router.get("/{watcher_id}/notifications", response_model=list[NotificationResponse])
def get_notifications(
    watcher_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get notification history for a watcher. Must own it."""
    watcher = session.get(Watcher, watcher_id)
    if not watcher or watcher.user_id != user.id:
        raise HTTPException(404, "Watcher not found")
    notifications = (
        session.query(Notification)
        .filter_by(watcher_id=watcher_id)
        .order_by(Notification.sent_at.desc())
        .limit(50)
        .all()
    )
    return [
        NotificationResponse(
            id=n.id, pp_number=n.pp_number, channel=n.channel,
            status=n.status, sent_at=n.sent_at,
        )
        for n in notifications
    ]

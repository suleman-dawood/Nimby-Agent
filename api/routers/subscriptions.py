"""PP subscription + in-app notification endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_session
from api.middleware.auth import get_current_user
from api.schemas.subscriptions import (
    CreateSubscriptionRequest,
    InAppNotificationResponse,
    SubscriptionResponse,
    UnreadCountResponse,
)
from scraper.models import InAppNotification, Subscription, User

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# --- Subscriptions ---

@router.post("", response_model=SubscriptionResponse)
def subscribe(
    req: CreateSubscriptionRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Subscribe to a PP for change notifications."""
    existing = (
        session.query(Subscription)
        .filter_by(user_id=user.id, pp_number=req.pp_number)
        .first()
    )
    if existing:
        existing.active = True
        existing.notify_docs = req.notify_docs
        existing.notify_stage = req.notify_stage
        existing.notify_expiry = req.notify_expiry
        session.commit()
        session.refresh(existing)
        return _sub_response(existing)

    sub = Subscription(
        user_id=user.id,
        pp_number=req.pp_number,
        notify_docs=req.notify_docs,
        notify_stage=req.notify_stage,
        notify_expiry=req.notify_expiry,
        created_at=datetime.now(timezone.utc),
        active=True,
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return _sub_response(sub)


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    subs = (
        session.query(Subscription)
        .filter_by(user_id=user.id, active=True)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    return [_sub_response(s) for s in subs]


@router.delete("/{pp_number}")
def unsubscribe(
    pp_number: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sub = (
        session.query(Subscription)
        .filter_by(user_id=user.id, pp_number=pp_number)
        .first()
    )
    if not sub:
        raise HTTPException(404, "Subscription not found")
    sub.active = False
    session.commit()
    return {"status": "unsubscribed"}


# --- In-App Notifications ---

@router.get("/notifications", response_model=list[InAppNotificationResponse])
def get_notifications(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    notifs = (
        session.query(InAppNotification)
        .filter_by(user_id=user.id)
        .order_by(InAppNotification.created_at.desc())
        .limit(50)
        .all()
    )
    return [_notif_response(n) for n in notifs]


@router.get("/notifications/unread", response_model=UnreadCountResponse)
def unread_count(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    count = (
        session.query(InAppNotification)
        .filter_by(user_id=user.id, read=False)
        .count()
    )
    return UnreadCountResponse(count=count)


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    notif = session.get(InAppNotification, notification_id)
    if not notif or notif.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    notif.read = True
    session.commit()
    return {"status": "read"}


@router.post("/notifications/read-all")
def mark_all_read(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    session.query(InAppNotification).filter_by(user_id=user.id, read=False).update({"read": True})
    session.commit()
    return {"status": "all_read"}


def _sub_response(s: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=s.id, pp_number=s.pp_number,
        notify_docs=s.notify_docs, notify_stage=s.notify_stage,
        notify_expiry=s.notify_expiry, active=s.active,
        created_at=s.created_at,
    )


def _notif_response(n: InAppNotification) -> InAppNotificationResponse:
    return InAppNotificationResponse(
        id=n.id, pp_number=n.pp_number, event_type=n.event_type,
        title=n.title, message=n.message, read=n.read,
        created_at=n.created_at,
    )


# --- Email unsubscribe (no auth needed — uses email param) ---

@router.get("/unsubscribe-email")
def unsubscribe_via_email(
    email: str,
    pp: str,
    session: Session = Depends(get_session),
):
    """One-click unsubscribe from email link. No auth required."""
    from scraper.models import User
    user = session.query(User).filter_by(email=email).first()
    if not user:
        return {"status": "not_found", "message": "Email not found"}
    sub = (
        session.query(Subscription)
        .filter_by(user_id=user.id, pp_number=pp)
        .first()
    )
    if sub:
        sub.active = False
        session.commit()
    return {"status": "unsubscribed", "message": f"Unsubscribed from {pp}. You will no longer receive email notifications for this proposal."}


@router.get("/unsubscribe-all")
def unsubscribe_all_via_email(
    email: str,
    session: Session = Depends(get_session),
):
    """Unsubscribe from all proposals via email link. No auth required."""
    from scraper.models import User
    user = session.query(User).filter_by(email=email).first()
    if not user:
        return {"status": "not_found", "message": "Email not found"}
    session.query(Subscription).filter_by(user_id=user.id, active=True).update({"active": False})
    session.commit()
    return {"status": "unsubscribed_all", "message": "Unsubscribed from all proposal notifications."}

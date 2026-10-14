"""Phase 11: turning notifications on for a device, and a test push."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.push import PushSubscription
from app.models.user import User
from app.schemas.push import SubscriptionIn, SubscriptionRef
from app.services import push as svc

router = APIRouter()


@router.get("/key")
async def public_key(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The public half of the install's VAPID key, for PushManager.subscribe()."""
    return {"public_key": (await svc.vapid_keys(db)).public_key}


@router.post("/subscriptions", status_code=201)
async def subscribe(data: SubscriptionIn, request: Request, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """Turn notifications on for this device. A device someone else subscribed
    (a shared tablet) now gets this person's notifications instead."""
    sub = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))).scalar_one_or_none()
    if sub is None:
        sub = PushSubscription(endpoint=data.endpoint)
        db.add(sub)
    sub.family_id, sub.user_id = user.family_id, user.id
    sub.p256dh, sub.auth = data.keys.p256dh, data.keys.auth
    sub.user_agent = (request.headers.get("user-agent") or "")[:256] or None
    await db.flush()
    return {"ok": True}


@router.delete("/subscriptions")
async def unsubscribe(data: SubscriptionRef, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    sub = (await db.execute(select(PushSubscription).where(
        PushSubscription.endpoint == data.endpoint, PushSubscription.user_id == user.id))).scalar_one_or_none()
    if sub is not None:
        await db.delete(sub)
        await db.flush()
    return {"ok": True}


@router.post("/test")
async def test_push(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Send yourself a test notification on every device you turned on."""
    if not await svc.has_device(db, user.id):
        raise HTTPException(status_code=409, detail="Turn on notifications on this device first")
    sent = await svc.send_to_users(db, [user.id], {
        "title": "OpenFamHub", "body": "Notifications are on. You'll get your reminders here.", "url": "/me",
        "tag": "test"})
    return {"sent": sent}

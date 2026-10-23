"""Password-gated calendar subscription lifecycle operations.

All write operations require a password-gated admin session
(`require_role("admin")`).  List responses never reveal relay URLs;
create / reveal / rotate responses carry the encrypted-at-rest URL
decrypted for the requesting admin.
"""
from datetime import datetime, timezone
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.security import require_role
from app.integrations.calendar_relay import (
    RelayUnavailable,
    create_feed,
    revoke_feed,
)
from app.models.calendar_subscription import (
    CalendarSubscription,
    CalendarSubscriptionAudit,
)
from app.schemas.calendar_subscription import (
    CalendarSubscriptionDetailResponse,
    CalendarSubscriptionListResponse,
)
from app.services.calendar_subscriptions import (
    decrypt_relay_url,
    mark_family_subscriptions_dirty,
    render_ics,
    set_relay_feed,
)

# Session factory for network calls; default is production's AsyncSessionLocal.
# Tests can monkeypatch this to use the test database.
_network_session_factory: Callable = AsyncSessionLocal

router = APIRouter()


def _audit(
    db: AsyncSession,
    subscription: CalendarSubscription,
    action: Literal["created", "revealed", "rotated", "revoked"],
    actor_id: str,
) -> None:
    """Record an audit entry for the given lifecycle action."""
    db.add(CalendarSubscriptionAudit(
        subscription_id=subscription.id,
        family_id=subscription.family_id,
        action=action,
        actor_user_id=actor_id,
        created_at=datetime.now(timezone.utc),
    ))


def _detail_response(sub: CalendarSubscription) -> CalendarSubscriptionDetailResponse:
    """Build a detail response, decrypting the stored URL."""
    url = decrypt_relay_url(sub.relay_url_encrypted)
    return CalendarSubscriptionDetailResponse(
        id=sub.id,
        family_id=sub.family_id,
        kind=sub.kind,
        active=sub.active,
        last_published_at=sub.last_published_at,
        last_error=sub.last_error,
        subscription_url=url,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CalendarSubscriptionListResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    _admin: object = Depends(require_role("admin")),
):
    """List all subscriptions for the current family.

    Relay URLs are never included in list responses.
    """
    result = await db.execute(
        select(CalendarSubscription).where(
            CalendarSubscription.family_id == _admin.family_id,
        ).order_by(CalendarSubscription.kind),
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("/{kind}", response_model=CalendarSubscriptionDetailResponse, status_code=201)
async def create_subscription(
    kind: Literal["titles", "full"],
    db: AsyncSession = Depends(get_db),
    admin: object = Depends(require_role("admin")),
):
    """Create (or recreate) a subscription feed for the given kind.

    Creates a relay feed, encrypts the returned URL, marks the
    subscription active with a pending publication flag, and audits
    the action.  If a subscription already exists for this family+kind
    it is replaced atomically: the old feed is revoked, the new one
    takes its place, and the subscription row is updated.
    """
    # Render the ICS snapshot to send to the relay.
    raw = await render_ics(db, admin.family_id, kind)
    await db.commit()  # close read transaction before network I/O

    # Use an independent session for network calls and writes, so that
    # production's expire_on_commit=True does not invalidate objects.
    async with _network_session_factory() as net_db:
        # Create the relay feed.
        try:
            feed = await create_feed(kind, raw)
        except RelayUnavailable:
            raise HTTPException(
                status_code=502,
                detail="Could not reach the calendar relay",
            )

        # Re-query the subscription in the new session.
        sub_result = await net_db.execute(
            select(CalendarSubscription).where(
                CalendarSubscription.family_id == admin.family_id,
                CalendarSubscription.kind == kind,
            ),
        )
        sub = sub_result.scalar_one_or_none()

        if sub is not None:
            # Revoke the old feed if it had one.
            if sub.relay_id:
                try:
                    await revoke_feed(sub.relay_id)
                except RelayUnavailable:
                    # Safe remediation: keep the new feed active; the old
                    # one is orphaned but its URL is no longer valid.
                    pass
            # Update the existing row.
            set_relay_feed(sub, feed)
            sub.active = True
            sub.publication_pending = True
            sub.last_error = None
            _audit(net_db, sub, "created", admin.id)
            await mark_family_subscriptions_dirty(net_db, admin.family_id)
            await net_db.commit()
            return _detail_response(sub)

        # Create a new subscription row.
        sub = CalendarSubscription(
            family_id=admin.family_id,
            kind=kind,
        )
        set_relay_feed(sub, feed)
        sub.active = True
        sub.publication_pending = True
        net_db.add(sub)
        await net_db.commit()
        _audit(net_db, sub, "created", admin.id)
        await mark_family_subscriptions_dirty(net_db, admin.family_id)
        await net_db.commit()
        return _detail_response(sub)


# ---------------------------------------------------------------------------
# Reveal
# ---------------------------------------------------------------------------

@router.post("/{kind}/reveal", response_model=CalendarSubscriptionDetailResponse)
async def reveal_subscription(
    kind: Literal["titles", "full"],
    db: AsyncSession = Depends(get_db),
    admin: object = Depends(require_role("admin")),
):
    """Reveal the URL for the requested subscription kind.

    Returns only the requested feed's URL (if active).  The URL is
    decrypted from the stored ciphertext.  An audit entry records
    the reveal.
    """
    result = await db.execute(
        select(CalendarSubscription).where(
            CalendarSubscription.family_id == admin.family_id,
            CalendarSubscription.kind == kind,
        ),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if not sub.active:
        raise HTTPException(status_code=400, detail="Subscription is not active; create it first")

    _audit(db, sub, "revealed", admin.id)
    await db.commit()
    return _detail_response(sub)


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------

@router.post("/{kind}/rotate", response_model=CalendarSubscriptionDetailResponse, status_code=201)
async def rotate_subscription(
    kind: Literal["titles", "full"],
    db: AsyncSession = Depends(get_db),
    admin: object = Depends(require_role("admin")),
):
    """Rotate the relay feed for the given kind.

    Creates a replacement relay feed, revokes the old one, updates
    the subscription row atomically, and audits the rotation.  If
    revocation of the old feed fails, the new feed is retained
    (the old one simply becomes orphaned).  The subscription is
    marked dirty so the next publication carries the new feed.
    """
    result = await db.execute(
        select(CalendarSubscription).where(
            CalendarSubscription.family_id == admin.family_id,
            CalendarSubscription.kind == kind,
        ),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Render the latest snapshot for the new feed.
    raw = await render_ics(db, admin.family_id, kind)
    await db.commit()

    # Use an independent session for network calls and writes.
    async with _network_session_factory() as net_db:
        try:
            new_feed = await create_feed(kind, raw)
        except RelayUnavailable:
            raise HTTPException(
                status_code=502,
                detail="Could not reach the calendar relay",
            )

        # Re-create the subscription object in the new session.
        sub_result = await net_db.execute(
            select(CalendarSubscription).where(
                CalendarSubscription.family_id == admin.family_id,
                CalendarSubscription.kind == kind,
            ),
        )
        sub = sub_result.scalar_one_or_none()
        old_id = sub.relay_id
        set_relay_feed(sub, new_feed)
        sub.active = True
        sub.publication_pending = True
        sub.last_error = None

        # Revoke the old feed (best effort).
        if old_id:
            try:
                await revoke_feed(old_id)
            except RelayUnavailable:
                pass  # new feed is safe; old one is orphaned

        _audit(net_db, sub, "rotated", admin.id)
        await mark_family_subscriptions_dirty(net_db, admin.family_id)
        await net_db.commit()
        return _detail_response(sub)


# ---------------------------------------------------------------------------
# Revoke (delete)
# ---------------------------------------------------------------------------

@router.delete("/{kind}")
async def revoke_subscription(
    kind: Literal["titles", "full"],
    db: AsyncSession = Depends(get_db),
    admin: object = Depends(require_role("admin")),
):
    """Revoke (disable) the subscription for the given kind.

    Marks the feed inactive, calls the relay to revoke it, and
    audits the action.  A relay failure is recorded as an error
    but does not affect other kinds.
    """
    result = await db.execute(
        select(CalendarSubscription).where(
            CalendarSubscription.family_id == admin.family_id,
            CalendarSubscription.kind == kind,
        ),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Revoke the relay feed if one exists.
    if sub.relay_id:
        try:
            await revoke_feed(sub.relay_id)
        except RelayUnavailable:
            sub.last_error = "Could not reach the calendar relay"

    sub.active = False
    sub.publication_pending = False
    _audit(db, sub, "revoked", admin.id)
    await mark_family_subscriptions_dirty(db, admin.family_id)
    await db.commit()
    return {"ok": True}

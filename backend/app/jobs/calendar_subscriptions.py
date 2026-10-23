"""Durable subscription outbox: committed snapshots, coalesced minute retries."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.calendar_subscription import CalendarSubscription
from app.services.calendar_subscriptions import publish_subscription


async def publish_due_subscriptions() -> None:
    # Select IDs only. Each delivery loads its own current committed state in a
    # fresh session; one failure cannot roll back another feed's delivery state.
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(CalendarSubscription.id).where(
            CalendarSubscription.active == True,
            CalendarSubscription.publication_pending == True,
        ))).scalars().all()
    for subscription_id in ids:
        async with AsyncSessionLocal() as db:
            subscription = await db.get(CalendarSubscription, subscription_id)
            if subscription is not None:
                await publish_subscription(db, subscription)
                await db.commit()


def register_calendar_subscription_jobs(scheduler) -> None:
    scheduler.add_job(
        publish_due_subscriptions, "interval", seconds=60,
        id="calendar_subscriptions_publish_due", replace_existing=True,
        coalesce=True, max_instances=1,
    )

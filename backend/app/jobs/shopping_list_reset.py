"""Weekly shopping list reset job — runs every Monday at 7:00 AM."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update as sa_update
from app.core.database import get_async_session
from app.models.event import ShoppingListItem


async def reset_weekly_shopping_list():
    """
    Run every Monday at 7:00 AM.
    Clears checked_at timestamps for items from the previous week.
    Does NOT delete items — keeps history.
    """
    async with get_async_session() as db:
        today = datetime.now(timezone.utc).date()
        last_monday = today - timedelta(days=today.weekday()) - timedelta(weeks=1)
        
        # Uncheck any remaining checked items from last week
        await db.execute(
            sa_update(ShoppingListItem)
            .where(
                (ShoppingListItem.week_start_date == str(last_monday)) &
                (ShoppingListItem.is_checked == True)
            )
            .values(is_checked=False, checked_at=None)
        )
        await db.commit()


def init_shopping_list_job(scheduler):
    """Add the shopping list reset job to the APScheduler."""
    scheduler.add_job(
        reset_weekly_shopping_list,
        "cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        id="shopping_list_reset",
        replace_existing=True,
    )

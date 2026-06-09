from datetime import datetime, timezone
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AllowanceLedger, User


async def distribute_weekly_allowance(db: AsyncSession):
    """Distribute weekly allowance to all active users."""
    result = await db.execute(select(User).where(User.is_active == True))
    users = result.scalars().all()

    for user in users:
        # Get weekly allowance from user settings
        settings = json.loads(user.settings_json) if user.settings_json else {}
        weekly_amount = settings.get("weekly_allowance", "0.00")

        if not weekly_amount or float(weekly_amount) == 0:
            continue

        # Create allowance ledger entry
        entry = AllowanceLedger(
            user_id=user.id,
            amount=weekly_amount,
            type="allowance_weekly",
            description=f"Weekly allowance: ${weekly_amount}",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(entry)

    await db.flush()

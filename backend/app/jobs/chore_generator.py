from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chore, ChoreInstance, User


def _generate_dates_for_rule(rule: str, days: int = 7) -> list[str]:
    """Generate due dates for a recurrence rule for the next N days."""
    dates = []
    today = datetime.now(timezone.utc).date()

    if rule == "daily":
        for i in range(days):
            dates.append((today + timedelta(days=i)).isoformat())
    elif rule.startswith("weekly_"):
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        target_day = day_map.get(rule[7:])
        if target_day is not None:
            for i in range(2):  # Up to 2 weeks
                target = today + timedelta(days=(target_day - today.weekday() + 7 * i) % 7)
                if target >= today and target < today + timedelta(days=days * 2):
                    dates.append(target.isoformat())
    elif rule.startswith("monthly_"):
        try:
            day = int(rule[8:])
            for i in range(2):
                target = today + relativedelta(day=day, months=i)
                if target >= today and target < today + timedelta(days=days * 2):
                    dates.append(target.isoformat())
        except (ValueError, IndexError):
            pass
    elif rule.startswith("every_") and "_days_" in rule:
        try:
            parts = rule.split("_")
            interval = int(parts[2])
            for i in range(0, days * 2, interval):
                dates.append((today + timedelta(days=i)).isoformat())
        except (IndexError, ValueError):
            pass

    return dates


async def generate_chore_instances(db: AsyncSession):
    """Generate chore instances for the upcoming week from active templates."""
    result = await db.execute(select(Chore).where(Chore.is_active == True))
    templates = result.scalars().all()

    for template in templates:
        dates = _generate_dates_for_rule(template.recurrence_rule, 7)

        for due_date in dates:
            # Check if instance already exists for this template + date
            existing = await db.execute(
                select(ChoreInstance).where(
                    ChoreInstance.chore_template_id == template.id,
                    ChoreInstance.due_date == due_date,
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Generate instance
            if template.assignment_mode == "assigned" and template.default_assigned_to_id:
                # Assigned mode - assign to the default user
                instance = ChoreInstance(
                    chore_template_id=template.id,
                    assigned_to_id=template.default_assigned_to_id,
                    due_date=due_date,
                    status="pending",
                )
                db.add(instance)
            else:
                # Claimable mode (or assigned without default user - skip)
                instance = ChoreInstance(
                    chore_template_id=template.id,
                    assigned_to_id=None,
                    due_date=due_date,
                    status="pending",
                )
                db.add(instance)

    await db.flush()

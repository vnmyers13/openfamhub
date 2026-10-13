"""The install's family: one per install (see models/family.py)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import Family


async def install_family_id(db: AsyncSession) -> str | None:
    """The id of this install's family, or None before setup."""
    result = await db.execute(select(Family.id).order_by(Family.created_at).limit(1))
    return result.scalar_one_or_none()

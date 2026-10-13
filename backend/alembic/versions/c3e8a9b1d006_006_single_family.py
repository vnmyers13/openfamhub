"""006_single_family

One family per install (review backlog #5): a trigger rejects a second row in
`families`. Setup already refuses a second family; this closes the race where
two setup requests both pass that check.

Revision ID: c3e8a9b1d006
Revises: b7d2e1f0a005
Create Date: 2026-10-12
"""
import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.family import SINGLE_FAMILY_TRIGGER


revision: str = 'c3e8a9b1d006'
down_revision: Union[str, None] = 'b7d2e1f0a005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM families")).scalar()
    if count and count > 1:
        # Not expected (setup never created two), but don't brick the install:
        # sign-in uses the oldest family, and no further families can be added.
        logger.warning("families has %s rows; sign-in will use the oldest one", count)
    op.execute(SINGLE_FAMILY_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS families_single_row")

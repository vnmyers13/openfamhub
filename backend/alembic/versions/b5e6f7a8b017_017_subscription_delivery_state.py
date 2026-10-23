"""017_subscription_delivery_state

Revision ID: b5e6f7a8b017
Revises: a4d5e6f7a016
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.types import UTCDateTime

revision: str = "b5e6f7a8b017"
down_revision: Union[str, None] = "a4d5e6f7a016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calendar_subscriptions", sa.Column("auth_paused_config", sa.String(64), nullable=True))
    op.add_column("calendar_subscriptions", sa.Column("next_attempt_at", UTCDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_subscriptions", "next_attempt_at")
    op.drop_column("calendar_subscriptions", "auth_paused_config")

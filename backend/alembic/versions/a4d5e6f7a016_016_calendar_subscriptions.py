"""016_calendar_subscriptions

Revision ID: a4d5e6f7a016
Revises: f3c4d5e6f015
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.types import UTCDateTime

revision: str = "a4d5e6f7a016"
down_revision: Union[str, None] = "f3c4d5e6f015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("relay_id", sa.String(128), nullable=True),
        sa.Column("relay_url_encrypted", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("publication_pending", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_published_at", UTCDateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("family_id", "kind", name="uq_calendar_subscription_family_kind"),
        sa.CheckConstraint("kind IN ('titles', 'full')", name="ck_calendar_subscription_kind"),
    )
    op.create_table(
        "calendar_subscription_audits",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('created', 'revealed', 'rotated', 'revoked')", name="ck_calendar_subscription_audit_action"),
    )
    op.create_index("ix_calendar_subscription_audits_family_created", "calendar_subscription_audits", ["family_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_calendar_subscription_audits_family_created", table_name="calendar_subscription_audits")
    op.drop_table("calendar_subscription_audits")
    op.drop_table("calendar_subscriptions")

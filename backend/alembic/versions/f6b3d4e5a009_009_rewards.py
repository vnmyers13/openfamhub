"""009_rewards

Phase 6: the reward catalog and redemptions, badges, and the weekly
allowance (plans plus an append-only ledger in whole cents). Points stay in
the Phase 5 points_ledger.

Revision ID: f6b3d4e5a009
Revises: e5a2c3d4f008
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b3d4e5a009'
down_revision: Union[str, None] = 'e5a2c3d4f008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table('rewards',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=16), nullable=True),
        sa.Column('point_cost', sa.Integer(), nullable=False),
        sa.Column('needs_approval', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_rewards_family', 'rewards', ['family_id', 'is_active'])

    op.create_table('reward_redemptions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('reward_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('reward_name', sa.String(length=128), nullable=False),
        sa.Column('point_cost', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('note', sa.String(length=256), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decided_by', sa.String(), nullable=True),
    )
    op.create_index('ix_redemptions_family', 'reward_redemptions', ['family_id', 'status'])

    op.create_table('badge_definitions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=256), nullable=True),
        sa.Column('icon', sa.String(length=16), nullable=True),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('bonus_points', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_badges_family', 'badge_definitions', ['family_id', 'is_active'])

    op.create_table('user_badges',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('badge_id', sa.String(), nullable=False),
        sa.Column('earned_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'badge_id', name='uq_user_badge'),
    )
    op.create_index('ix_user_badges_family', 'user_badges', ['family_id', 'user_id'])

    op.create_table('allowance_plans',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('weekly_cents', sa.Integer(), nullable=False),
        sa.Column('start_week', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('user_id', name='uq_allowance_plan_user'),
    )

    op.create_table('allowance_ledger',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('delta_cents', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('user_id', 'week_start', name='uq_allowance_week'),
        sa.UniqueConstraint('source_type', 'source_id', name='uq_allowance_source'),
    )
    op.create_index('ix_allowance_family_user', 'allowance_ledger', ['family_id', 'user_id'])


def downgrade() -> None:
    op.drop_index('ix_allowance_family_user', table_name='allowance_ledger')
    op.drop_table('allowance_ledger')
    op.drop_table('allowance_plans')
    op.drop_index('ix_user_badges_family', table_name='user_badges')
    op.drop_table('user_badges')
    op.drop_index('ix_badges_family', table_name='badge_definitions')
    op.drop_table('badge_definitions')
    op.drop_index('ix_redemptions_family', table_name='reward_redemptions')
    op.drop_table('reward_redemptions')
    op.drop_index('ix_rewards_family', table_name='rewards')
    op.drop_table('rewards')

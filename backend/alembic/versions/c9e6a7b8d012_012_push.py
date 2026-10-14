"""012_push

Phase 11: Web Push keys, subscriptions, and what has been sent.

Revision ID: c9e6a7b8d012
Revises: b8d5f6a7c011
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e6a7b8d012'
down_revision: Union[str, None] = 'b8d5f6a7c011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table('push_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('private_pem', sa.Text(), nullable=False),
        sa.Column('public_key', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_table('push_subscriptions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('endpoint', sa.String(length=2048), nullable=False, unique=True),
        sa.Column('p256dh', sa.String(length=256), nullable=False),
        sa.Column('auth', sa.String(length=64), nullable=False),
        sa.Column('user_agent', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_push_subscriptions_user', 'push_subscriptions', ['user_id'])
    op.create_table('notifications_sent',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('ref', sa.String(length=160), nullable=False),
        sa.Column('sent_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('user_id', 'kind', 'ref', name='uq_notifications_sent'),
    )


def downgrade() -> None:
    op.drop_table('notifications_sent')
    op.drop_index('ix_push_subscriptions_user', table_name='push_subscriptions')
    op.drop_table('push_subscriptions')
    op.drop_table('push_keys')

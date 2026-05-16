"""003_calendar

Revision ID: 12c7ab6cf8c5
Revises: 4c6b1ca5fd2c
Create Date: 2026-05-15 21:03:03.229199
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '12c7ab6cf8c5'
down_revision: Union[str, None] = '4c6b1ca5fd2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('calendar_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('family_id', sa.String(), nullable=False),
    sa.Column('external_uid', sa.String(length=512), nullable=True),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('start_dt', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_dt', sa.DateTime(timezone=True), nullable=False),
    sa.Column('all_day', sa.Boolean(), nullable=False),
    sa.Column('location', sa.String(length=256), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'external_uid', name='uq_event_external_uid')
    )
    op.create_index('ix_calendar_events_source_dates', 'calendar_events', ['source_id', 'start_dt', 'end_dt'], unique=False)
    op.create_table('calendar_sources',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('family_id', sa.String(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('display_name', sa.String(length=128), nullable=False),
    sa.Column('color_hex', sa.String(length=7), nullable=False),
    sa.Column('ics_url', sa.String(length=1024), nullable=True),
    sa.Column('sync_interval_hours', sa.Float(), nullable=False),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sync_error', sa.Text(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sync_logs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('events_upserted', sa.Integer(), nullable=False),
    sa.Column('events_deleted', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('sync_logs')
    op.drop_table('calendar_sources')
    op.drop_index('ix_calendar_events_source_dates', table_name='calendar_events')
    op.drop_table('calendar_events')

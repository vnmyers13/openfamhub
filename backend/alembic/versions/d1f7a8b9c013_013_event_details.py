"""013_event_details

Event details (2026-10-15): a web link, the organizer and the attendees,
kept from calendar feeds (iCal URL, ORGANIZER, ATTENDEE); local events can
have a link too.

Revision ID: d1f7a8b9c013
Revises: c9e6a7b8d012
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f7a8b9c013'
down_revision: Union[str, None] = 'c9e6a7b8d012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('calendar_events') as batch:
        batch.add_column(sa.Column('url', sa.String(2048), nullable=True))
        batch.add_column(sa.Column('organizer', sa.String(256), nullable=True))
        batch.add_column(sa.Column('attendees', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('calendar_events') as batch:
        batch.drop_column('attendees')
        batch.drop_column('organizer')
        batch.drop_column('url')

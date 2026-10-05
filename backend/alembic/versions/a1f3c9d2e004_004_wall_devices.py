"""004_wall_devices

Revision ID: a1f3c9d2e004
Revises: 12c7ab6cf8c5
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f3c9d2e004'
down_revision: Union[str, None] = '12c7ab6cf8c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('wall_devices',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('family_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )


def downgrade() -> None:
    op.drop_table('wall_devices')

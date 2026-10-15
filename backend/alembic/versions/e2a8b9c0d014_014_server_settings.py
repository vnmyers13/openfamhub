"""014_server_settings

Server settings changed in Admin › Settings (Home Assistant, ntfy, email,
backups, the wall's idle timeout); secrets are stored encrypted.

Revision ID: e2a8b9c0d014
Revises: d1f7a8b9c013
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a8b9c0d014'
down_revision: Union[str, None] = 'd1f7a8b9c013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('server_settings',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('secret', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)')),
    )


def downgrade() -> None:
    op.drop_table('server_settings')

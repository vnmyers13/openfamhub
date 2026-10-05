"""005_session_auth_method

Sessions now back every login token (jti = sessions.id) and record how the
user signed in, so PIN sessions can be kept out of admin actions.

Revision ID: b7d2e1f0a005
Revises: a1f3c9d2e004
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2e1f0a005'
down_revision: Union[str, None] = 'a1f3c9d2e004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sessions') as batch:
        batch.add_column(sa.Column('auth_method', sa.String(length=16), nullable=False, server_default='password'))
        batch.add_column(sa.Column('elevated_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sessions') as batch:
        batch.drop_column('elevated_until')
        batch.drop_column('auth_method')

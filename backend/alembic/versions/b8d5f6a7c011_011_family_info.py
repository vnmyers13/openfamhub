"""011_family_info

Phase 8: books, announcements, and a birthday on each user.

Revision ID: b8d5f6a7c011
Revises: a7c4e5f6b010
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d5f6a7c011'
down_revision: Union[str, None] = 'a7c4e5f6b010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table('books',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('author', sa.String(length=256), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('reader_id', sa.String(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('added_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_books_family', 'books', ['family_id', 'owner_id'])

    op.create_table('announcements',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('pinned', sa.Boolean(), nullable=False),
        sa.Column('author_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_announcements_family', 'announcements', ['family_id', 'pinned'])

    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('birthday', sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('birthday')
    op.drop_index('ix_announcements_family', table_name='announcements')
    op.drop_table('announcements')
    op.drop_index('ix_books_family', table_name='books')
    op.drop_table('books')

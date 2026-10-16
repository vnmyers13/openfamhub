"""015_notes_board

Revision ID: f3c4d5e6f015
Revises: e2a8b9c0d014
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c4d5e6f015"
down_revision: Union[str, None] = "e2a8b9c0d014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "note_boards",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("scene_json", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_note_boards_family", "note_boards", ["family_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_note_boards_family", table_name="note_boards")
    op.drop_table("note_boards")

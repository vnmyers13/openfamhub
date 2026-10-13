"""008_chores

Phase 5: chore templates and instances, the completion log, the points
ledger, routines and to-dos.

Revision ID: e5a2c3d4f008
Revises: d4f1b2c3e007
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a2c3d4f008'
down_revision: Union[str, None] = 'd4f1b2c3e007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table('chore_templates',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('assignment', sa.String(length=16), nullable=False),
        sa.Column('assigned_to', sa.String(), nullable=True),
        sa.Column('repeat', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('routine_id', sa.String(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_chore_templates_family', 'chore_templates', ['family_id', 'is_active'])

    op.create_table('chore_instances',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('assigned_to', sa.String(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('claimed_by', sa.String(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by', sa.String(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('template_id', 'due_date', name='uq_chore_instance_template_date'),
    )
    op.create_index('ix_chore_instances_family_date', 'chore_instances', ['family_id', 'due_date'])

    op.create_table('chore_completions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('instance_id', sa.String(), nullable=False),
        sa.Column('completed_by', sa.String(), nullable=False),
        sa.Column('credited_to', sa.String(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False),
        sa.Column('undone_at', sa.DateTime(), nullable=True),
        sa.Column('undone_by', sa.String(), nullable=True),
    )
    op.create_index('ix_chore_completions_family', 'chore_completions', ['family_id', 'completed_at'])

    op.create_table('points_ledger',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('source_type', 'source_id', name='uq_points_source'),
    )
    op.create_index('ix_points_family_user', 'points_ledger', ['family_id', 'user_id'])

    op.create_table('routines',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('assigned_to', sa.String(), nullable=True),
        sa.Column('start_time', sa.String(length=5), nullable=True),
        sa.Column('repeat', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_routines_family', 'routines', ['family_id', 'is_active'])

    op.create_table('todos',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.String(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_todos_family', 'todos', ['family_id', 'completed_at'])


def downgrade() -> None:
    for index, table in [('ix_todos_family', 'todos'), ('ix_routines_family', 'routines'),
                         ('ix_points_family_user', 'points_ledger'), ('ix_chore_completions_family', 'chore_completions'),
                         ('ix_chore_instances_family_date', 'chore_instances'), ('ix_chore_templates_family', 'chore_templates')]:
        op.drop_index(index, table_name=table)
        op.drop_table(table)

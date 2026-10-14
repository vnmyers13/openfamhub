"""010_meals

Phase 7: recipes, the weekly meal plan, the shopping list and the pantry.

Revision ID: a7c4e5f6b010
Revises: f6b3d4e5a009
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c4e5f6b010'
down_revision: Union[str, None] = 'f6b3d4e5a009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    op.create_table('recipes',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('servings', sa.Integer(), nullable=True),
        sa.Column('prep_minutes', sa.Integer(), nullable=True),
        sa.Column('cook_minutes', sa.Integer(), nullable=True),
        sa.Column('ingredients', sa.JSON(), nullable=False),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('video_url', sa.String(length=2048), nullable=True),
        sa.Column('catalog_key', sa.String(length=64), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_recipes_family', 'recipes', ['family_id', 'is_deleted'])

    op.create_table('meal_plan_entries',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('slot', sa.String(length=16), nullable=False),
        sa.Column('recipe_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('note', sa.String(length=256), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.UniqueConstraint('family_id', 'day', 'slot', name='uq_meal_plan_slot'),
    )

    op.create_table('shopping_items',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('quantity', sa.String(length=64), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('recipe_id', sa.String(), nullable=True),
        sa.Column('recipe_title', sa.String(length=128), nullable=True),
        sa.Column('week_start', sa.Date(), nullable=True),
        sa.Column('checked', sa.Boolean(), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=True),
        sa.Column('checked_by', sa.String(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_shopping_family', 'shopping_items', ['family_id', 'archived_at'])

    op.create_table('pantry_items',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('family_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('low_at', sa.Float(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=NOW, nullable=False),
    )
    op.create_index('ix_pantry_family', 'pantry_items', ['family_id'])


def downgrade() -> None:
    op.drop_index('ix_pantry_family', table_name='pantry_items')
    op.drop_table('pantry_items')
    op.drop_index('ix_shopping_family', table_name='shopping_items')
    op.drop_table('shopping_items')
    op.drop_table('meal_plan_entries')
    op.drop_index('ix_recipes_family', table_name='recipes')
    op.drop_table('recipes')

"""add scale columns to GameSystem and Variant

Revision ID: 20250902_add_scale_fields
Revises: 20250830_kit_container_support
Create Date: 2025-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = '20250902_add_scale_fields'
down_revision = '20250830_kit_container_support'
branch_labels = None
depends_on = None

def upgrade():
    # Variant.scale_name
    op.add_column('variant', sa.Column('scale_name', sa.String(length=64), nullable=True))
    # GameSystem defaults
    op.add_column('game_system', sa.Column('default_scale_den', sa.Integer(), nullable=True))
    op.add_column('game_system', sa.Column('default_scale_name', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('game_system', 'default_scale_name')
    op.drop_column('game_system', 'default_scale_den')
    op.drop_column('variant', 'scale_name')

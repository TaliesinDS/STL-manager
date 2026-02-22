"""add scale columns to GameSystem and Variant

Revision ID: 20250902_add_scale_fields
Revises: 20250830_kit_container_support
Create Date: 2025-09-02
"""
import sqlalchemy as sa

from alembic import op

revision = '20250902_add_scale_fields'
down_revision = '20250830_kit'
branch_labels = None
depends_on = None

def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {c['name'] for c in insp.get_columns(table)}
    except Exception:
        return set()

def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade():
    # Only attempt to modify tables that exist; on fresh DBs, initial migration will create them.
    if _has_table('variant'):
        vcols = _cols('variant')
        if 'scale_name' not in vcols:
            op.add_column('variant', sa.Column('scale_name', sa.String(length=64), nullable=True))
    if _has_table('game_system'):
        gcols = _cols('game_system')
        if 'default_scale_den' not in gcols:
            op.add_column('game_system', sa.Column('default_scale_den', sa.Integer(), nullable=True))
        if 'default_scale_name' not in gcols:
            op.add_column('game_system', sa.Column('default_scale_name', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('game_system', 'default_scale_name')
    op.drop_column('game_system', 'default_scale_den')
    op.drop_column('variant', 'scale_name')

"""Add lineage table for lineage SSOT

Revision ID: 20250903_add_lineage_table
Revises: 20250903_expand_variant_core_fields
Create Date: 2025-09-03
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250903_add_lineage_table'
down_revision = '20250903_expand_variant_core_fields'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if not _has_table('lineage'):
        op.create_table(
            'lineage',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('family_key', sa.String(length=64), nullable=False),
            sa.Column('primary_key', sa.String(length=128), nullable=True),
            sa.Column('family_name', sa.String(length=128), nullable=True),
            sa.Column('name', sa.String(length=256), nullable=False),
            sa.Column('context_tags', sa.JSON(), nullable=True),
            sa.Column('aliases_strong', sa.JSON(), nullable=True),
            sa.Column('aliases_weak', sa.JSON(), nullable=True),
            sa.Column('locale_aliases', sa.JSON(), nullable=True),
            sa.Column('excludes', sa.JSON(), nullable=True),
            sa.Column('source_file', sa.String(length=512), nullable=True),
            sa.Column('source_anchor', sa.String(length=256), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_lineage_family_key', 'lineage', ['family_key'])
        op.create_index('ix_lineage_primary_key', 'lineage', ['primary_key'])
        op.create_index('ix_lineage_name', 'lineage', ['name'])


def downgrade() -> None:
    try:
        op.drop_index('ix_lineage_name', table_name='lineage')
    except Exception:
        pass
    try:
        op.drop_index('ix_lineage_primary_key', table_name='lineage')
    except Exception:
        pass
    try:
        op.drop_index('ix_lineage_family_key', table_name='lineage')
    except Exception:
        pass
    try:
        op.drop_table('lineage')
    except Exception:
        pass

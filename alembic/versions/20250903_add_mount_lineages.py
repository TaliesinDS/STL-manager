"""Add mount_lineages to Variant

Revision ID: 20250903_add_mount_lineages
Revises: 20250903_expand_variant_core_fields
Create Date: 2025-09-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250903_add_mount_lineages'
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


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {c['name'] for c in insp.get_columns(table)}
    except Exception:
        return set()


def upgrade() -> None:
    if not _has_table('variant'):
        return
    cols = _cols('variant')
    with op.batch_alter_table('variant') as batch_op:
        if 'mount_lineages' not in cols:
            batch_op.add_column(sa.Column('mount_lineages', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('variant') as batch_op:
        try:
            batch_op.drop_column('mount_lineages')
        except Exception:
            pass

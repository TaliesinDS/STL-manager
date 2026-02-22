"""Add kit container support to Variant (idempotent)

Revision ID: 20250830_kit
Revises: 0001_canonical_initial
Create Date: 2025-08-30
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250830_kit'
down_revision = '0001_canonical_initial'
branch_labels = None
depends_on = None


def _get_columns(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {col['name'] for col in insp.get_columns(table)}
    except Exception:
        return set()


def _get_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {idx['name'] for idx in insp.get_indexes(table)}
    except Exception:
        return set()


def upgrade():
    cols = _get_columns('variant')
    idxs = _get_indexes('variant')
    with op.batch_alter_table('variant') as batch_op:
        if 'parent_id' not in cols:
            batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        if 'is_kit_container' not in cols:
            batch_op.add_column(sa.Column('is_kit_container', sa.Boolean(), nullable=True))
        if 'kit_child_types' not in cols:
            batch_op.add_column(sa.Column('kit_child_types', sa.JSON(), nullable=True))
        if 'ix_variant_parent_id' not in idxs and 'parent_id' in (cols | {'parent_id'}):
            batch_op.create_index('ix_variant_parent_id', ['parent_id'])
        if 'ix_variant_is_kit_container' not in idxs and 'is_kit_container' in (cols | {'is_kit_container'}):
            batch_op.create_index('ix_variant_is_kit_container', ['is_kit_container'])
        # Create FK only if parent_id exists; SQLite will ignore named fks if duplicates
        try:
            if 'parent_id' in (cols | {'parent_id'}):
                batch_op.create_foreign_key('fk_variant_parent', 'variant', ['parent_id'], ['id'], ondelete='SET NULL')
        except Exception:
            pass


def downgrade():
    with op.batch_alter_table('variant') as batch_op:
        try:
            batch_op.drop_constraint('fk_variant_parent', type_='foreignkey')
        except Exception:
            pass
        try:
            batch_op.drop_index('ix_variant_is_kit_container')
        except Exception:
            pass
        try:
            batch_op.drop_index('ix_variant_parent_id')
        except Exception:
            pass
        for col in ('kit_child_types','is_kit_container','parent_id'):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass

"""Add kit container support to Variant

Revision ID: 20250830_kit
Revises: 0001_canonical_initial
Create Date: 2025-08-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250830_kit'
down_revision = '0001_canonical_initial'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('variant') as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_kit_container', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('kit_child_types', sa.JSON(), nullable=True))
        batch_op.create_index('ix_variant_parent_id', ['parent_id'])
        batch_op.create_index('ix_variant_is_kit_container', ['is_kit_container'])
        batch_op.create_foreign_key('fk_variant_parent', 'variant', ['parent_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('variant') as batch_op:
        batch_op.drop_constraint('fk_variant_parent', type_='foreignkey')
        batch_op.drop_index('ix_variant_is_kit_container')
        batch_op.drop_index('ix_variant_parent_id')
        batch_op.drop_column('kit_child_types')
        batch_op.drop_column('is_kit_container')
        batch_op.drop_column('parent_id')

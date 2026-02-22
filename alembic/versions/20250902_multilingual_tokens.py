"""add token_locale and english_tokens to variant

Revision ID: 20250902_multilingual_tokens
Revises: 20250902_add_scale_fields
Create Date: 2025-09-02 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20250902_multilingual_tokens'
down_revision = '20250902_add_scale_fields'
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {c['name'] for c in insp.get_columns(table)}
    except Exception:
        return set()


def _idx(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {i['name'] for i in insp.get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    cols = _cols('variant')
    idxs = _idx('variant')
    with op.batch_alter_table('variant') as batch_op:
        if 'token_locale' not in cols:
            batch_op.add_column(sa.Column('token_locale', sa.String(length=16), nullable=True))
        if 'english_tokens' not in cols:
            batch_op.add_column(sa.Column('english_tokens', sa.JSON(), nullable=True))
        if 'ui_display_en' not in cols:
            batch_op.add_column(sa.Column('ui_display_en', sa.Text(), nullable=True))
        if 'ix_variant_token_locale' not in idxs and 'token_locale' in (cols | {'token_locale'}):
            # Pass a list of column names, not a string, to avoid per-character iteration bugs
            batch_op.create_index('ix_variant_token_locale', ['token_locale'])


def downgrade() -> None:
    with op.batch_alter_table('variant') as batch_op:
        try:
            batch_op.drop_index('ix_variant_token_locale')
        except Exception:
            pass
        batch_op.drop_column('ui_display_en')
        batch_op.drop_column('english_tokens')
        batch_op.drop_column('token_locale')

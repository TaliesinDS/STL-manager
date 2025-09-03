"""Merge heads: lineage table and mount_lineages

Revision ID: 20250903_merge_heads_lineage_mounts
Revises: 20250903_add_lineage_table, 20250903_add_mount_lineages
Create Date: 2025-09-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250903_merge_heads_lineage_mounts'
down_revision = ('20250903_add_lineage_table', '20250903_add_mount_lineages')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merge-only revision, no ops
    pass


def downgrade() -> None:
    # merge-only revision, no ops
    pass

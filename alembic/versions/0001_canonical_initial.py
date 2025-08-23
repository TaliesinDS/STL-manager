"""canonical initial migration

Revision ID: 0001_canonical_initial
Revises: 
Create Date: 2025-08-23T19:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = '0001_canonical_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'archive',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rel_path', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('hash_sha256', sa.String(length=128), nullable=True),
        sa.Column('nested_archive_flag', sa.Boolean(), nullable=True),
        sa.Column('scan_first_seen_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('resource_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('field', sa.String(length=128), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('actor', sa.String(length=128), nullable=True),
        sa.Column('ts', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'character',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('franchise', sa.String(length=256), nullable=True),
        sa.Column('actor_likeness', sa.String(length=256), nullable=True),
        sa.Column('actor_confidence', sa.String(length=32), nullable=True),
        sa.Column('info_url', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'collection',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('original_label', sa.String(length=512), nullable=True),
        sa.Column('publisher', sa.String(length=256), nullable=True),
        sa.Column('cycle', sa.String(length=16), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=True),
        sa.Column('theme', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'job',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'variant',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('rel_path', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=True),
        sa.Column('extension', sa.String(length=32), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('mtime_iso', sa.String(length=64), nullable=True),
        sa.Column('is_archive', sa.Boolean(), nullable=True),
        sa.Column('hash_sha256', sa.String(length=128), nullable=True),
        sa.Column('designer', sa.String(length=256), nullable=True),
        sa.Column('franchise', sa.String(length=256), nullable=True),
        sa.Column('content_flag', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'vocab_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('domain', sa.String(length=64), nullable=False),
        sa.Column('key', sa.String(length=256), nullable=False),
        sa.Column('aliases', sa.JSON(), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'file',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('variant_id', sa.Integer(), sa.ForeignKey('variant.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rel_path', sa.String(length=1024), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('extension', sa.String(length=32), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('mtime_iso', sa.String(length=64), nullable=True),
        sa.Column('is_archive', sa.Boolean(), nullable=True),
        sa.Column('hash_sha256', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'variant_archive',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('variant_id', sa.Integer(), sa.ForeignKey('variant.id', ondelete='CASCADE'), nullable=False),
        sa.Column('archive_id', sa.Integer(), sa.ForeignKey('archive.id', ondelete='CASCADE'), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('variant_archive')
    op.drop_table('file')
    op.drop_table('vocab_entry')
    op.drop_table('variant')
    op.drop_table('job')
    op.drop_table('collection')
    op.drop_table('character')
    op.drop_table('audit_log')
    op.drop_table('archive')

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


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade():
    if not _has_table('archive'):
        try:
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
        except Exception:
            pass

    if not _has_table('audit_log'):
        try:
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
        except Exception:
            pass

    if not _has_table('character'):
        try:
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
        except Exception:
            pass

    if not _has_table('collection'):
        try:
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
        except Exception:
            pass

    if not _has_table('job'):
        try:
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
        except Exception:
            pass

    if not _has_table('variant'):
        try:
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
        except Exception:
            pass

    # Core codex/parts baseline tables so future migrations can add columns safely
    if not _has_table('game_system'):
        try:
            op.create_table(
                'game_system',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('key', sa.String(length=64), nullable=False),
                sa.Column('name', sa.String(length=128), nullable=False),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('faction'):
        try:
            op.create_table(
                'faction',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('system_id', sa.Integer(), sa.ForeignKey('game_system.id', ondelete='CASCADE'), nullable=False),
                sa.Column('key', sa.String(length=128), nullable=False),
                sa.Column('name', sa.String(length=256), nullable=False),
                sa.Column('parent_id', sa.Integer(), sa.ForeignKey('faction.id', ondelete='CASCADE'), nullable=True),
                sa.Column('full_path', sa.JSON(), nullable=True),
                sa.Column('aliases', sa.JSON(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('unit'):
        try:
            op.create_table(
                'unit',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('system_id', sa.Integer(), sa.ForeignKey('game_system.id', ondelete='CASCADE'), nullable=False),
                sa.Column('faction_id', sa.Integer(), sa.ForeignKey('faction.id', ondelete='SET NULL'), nullable=True),
                sa.Column('key', sa.String(length=128), nullable=False),
                sa.Column('name', sa.String(length=256), nullable=False),
                sa.Column('role', sa.String(length=64), nullable=True),
                sa.Column('unique_flag', sa.Boolean(), nullable=True),
                sa.Column('category', sa.String(length=64), nullable=True),
                sa.Column('aliases', sa.JSON(), nullable=True),
                sa.Column('legal_in_editions', sa.JSON(), nullable=True),
                sa.Column('available_to', sa.JSON(), nullable=True),
                sa.Column('base_profile_key', sa.String(length=64), nullable=True),
                sa.Column('attributes', sa.JSON(), nullable=True),
                sa.Column('raw_data', sa.JSON(), nullable=True),
                sa.Column('source_file', sa.String(length=512), nullable=True),
                sa.Column('source_anchor', sa.String(length=256), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('unit_alias'):
        try:
            op.create_table(
                'unit_alias',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('unit_id', sa.Integer(), sa.ForeignKey('unit.id', ondelete='CASCADE'), nullable=False),
                sa.Column('alias', sa.String(length=256), nullable=False),
            )
        except Exception:
            pass

    if not _has_table('variant_unit_link'):
        try:
            op.create_table(
                'variant_unit_link',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('variant_id', sa.Integer(), sa.ForeignKey('variant.id', ondelete='CASCADE'), nullable=False),
                sa.Column('unit_id', sa.Integer(), sa.ForeignKey('unit.id', ondelete='CASCADE'), nullable=False),
                sa.Column('is_primary', sa.Boolean(), nullable=True),
                sa.Column('match_method', sa.String(length=64), nullable=True),
                sa.Column('match_confidence', sa.Float(), nullable=True),
                sa.Column('notes', sa.Text(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('part'):
        try:
            op.create_table(
                'part',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('system_id', sa.Integer(), sa.ForeignKey('game_system.id', ondelete='CASCADE'), nullable=False),
                sa.Column('faction_id', sa.Integer(), sa.ForeignKey('faction.id', ondelete='SET NULL'), nullable=True),
                sa.Column('key', sa.String(length=128), nullable=False),
                sa.Column('name', sa.String(length=256), nullable=False),
                sa.Column('part_type', sa.String(length=64), nullable=False),
                sa.Column('category', sa.String(length=64), nullable=True),
                sa.Column('slot', sa.String(length=64), nullable=True),
                sa.Column('slots', sa.JSON(), nullable=True),
                sa.Column('aliases', sa.JSON(), nullable=True),
                sa.Column('legal_in_editions', sa.JSON(), nullable=True),
                sa.Column('legends_in_editions', sa.JSON(), nullable=True),
                sa.Column('available_to', sa.JSON(), nullable=True),
                sa.Column('attributes', sa.JSON(), nullable=True),
                sa.Column('raw_data', sa.JSON(), nullable=True),
                sa.Column('source_file', sa.String(length=512), nullable=True),
                sa.Column('source_anchor', sa.String(length=256), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('part_alias'):
        try:
            op.create_table(
                'part_alias',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('part_id', sa.Integer(), sa.ForeignKey('part.id', ondelete='CASCADE'), nullable=False),
                sa.Column('alias', sa.String(length=256), nullable=False),
            )
        except Exception:
            pass

    if not _has_table('variant_part_link'):
        try:
            op.create_table(
                'variant_part_link',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('variant_id', sa.Integer(), sa.ForeignKey('variant.id', ondelete='CASCADE'), nullable=False),
                sa.Column('part_id', sa.Integer(), sa.ForeignKey('part.id', ondelete='CASCADE'), nullable=False),
                sa.Column('is_primary', sa.Boolean(), nullable=True),
                sa.Column('match_method', sa.String(length=64), nullable=True),
                sa.Column('match_confidence', sa.Float(), nullable=True),
                sa.Column('notes', sa.Text(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('unit_part_link'):
        try:
            op.create_table(
                'unit_part_link',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('unit_id', sa.Integer(), sa.ForeignKey('unit.id', ondelete='CASCADE'), nullable=False),
                sa.Column('part_id', sa.Integer(), sa.ForeignKey('part.id', ondelete='CASCADE'), nullable=False),
                sa.Column('relation_type', sa.String(length=32), nullable=True),
                sa.Column('required_slot', sa.String(length=64), nullable=True),
                sa.Column('notes', sa.Text(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('vocab_entry'):
        try:
            op.create_table(
                'vocab_entry',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('domain', sa.String(length=64), nullable=False),
                sa.Column('key', sa.String(length=256), nullable=False),
                sa.Column('aliases', sa.JSON(), nullable=True),
                sa.Column('meta', sa.JSON(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass

    if not _has_table('file'):
        try:
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
        except Exception:
            pass

    if not _has_table('variant_archive'):
        try:
            op.create_table(
                'variant_archive',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('variant_id', sa.Integer(), sa.ForeignKey('variant.id', ondelete='CASCADE'), nullable=False),
                sa.Column('archive_id', sa.Integer(), sa.ForeignKey('archive.id', ondelete='CASCADE'), nullable=False),
                sa.Column('first_seen_at', sa.DateTime(), nullable=True),
            )
        except Exception:
            pass


def downgrade():
    for name in [
        'unit_part_link','variant_part_link','part_alias','part',
        'variant_unit_link','unit_alias','unit','faction','game_system',
        'variant_archive','file','vocab_entry','variant','job','collection','character','audit_log','archive'
    ]:
        try:
            op.drop_table(name)
        except Exception:
            pass

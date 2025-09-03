"""Expand Variant core fields to match ORM (idempotent)

Revision ID: 20250903_expand_variant_core_fields
Revises: 20250903_add_variant_raw_tokens
Create Date: 2025-09-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250903_expand_variant_core_fields'
down_revision = '20250903_add_variant_raw_tokens'
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


def _idx(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return {i['name'] for i in insp.get_indexes(table)}
    except Exception:
        return set()


def upgrade() -> None:
    if not _has_table('variant'):
        return
    cols = _cols('variant')
    idxs = _idx('variant')
    with op.batch_alter_table('variant') as batch_op:
        # Additional P0/P1 fields
        if 'root_id' not in cols:
            batch_op.add_column(sa.Column('root_id', sa.String(length=256), nullable=True))
        if 'scan_batch_id' not in cols:
            batch_op.add_column(sa.Column('scan_batch_id', sa.String(length=128), nullable=True))
        if 'depth' not in cols:
            batch_op.add_column(sa.Column('depth', sa.Integer(), nullable=True))
        if 'is_dir' not in cols:
            batch_op.add_column(sa.Column('is_dir', sa.Boolean(), nullable=True))
        if 'model_group_id' not in cols:
            batch_op.add_column(sa.Column('model_group_id', sa.String(length=64), nullable=True))

        # Workflow / review fields
        if 'review_status' not in cols:
            batch_op.add_column(sa.Column('review_status', sa.String(length=32), nullable=True))
        if 'confidence_score' not in cols:
            batch_op.add_column(sa.Column('confidence_score', sa.Float(), nullable=True))
        if 'designer_confidence' not in cols:
            batch_op.add_column(sa.Column('designer_confidence', sa.String(length=32), nullable=True))
        if 'collection_id' not in cols:
            batch_op.add_column(sa.Column('collection_id', sa.String(length=64), nullable=True))
        if 'collection_original_label' not in cols:
            batch_op.add_column(sa.Column('collection_original_label', sa.String(length=512), nullable=True))
        if 'collection_cycle' not in cols:
            batch_op.add_column(sa.Column('collection_cycle', sa.String(length=16), nullable=True))
        if 'collection_sequence_number' not in cols:
            batch_op.add_column(sa.Column('collection_sequence_number', sa.Integer(), nullable=True))
        if 'collection_theme' not in cols:
            batch_op.add_column(sa.Column('collection_theme', sa.String(length=128), nullable=True))

        # Tabletop / franchise / character fields
        if 'game_system' not in cols:
            batch_op.add_column(sa.Column('game_system', sa.String(length=128), nullable=True))
        if 'codex_faction' not in cols:
            batch_op.add_column(sa.Column('codex_faction', sa.String(length=256), nullable=True))
        if 'codex_unit_name' not in cols:
            batch_op.add_column(sa.Column('codex_unit_name', sa.String(length=256), nullable=True))
        if 'character_name' not in cols:
            batch_op.add_column(sa.Column('character_name', sa.String(length=256), nullable=True))
        if 'character_aliases' not in cols:
            batch_op.add_column(sa.Column('character_aliases', sa.JSON(), nullable=True))
        if 'proxy_type' not in cols:
            batch_op.add_column(sa.Column('proxy_type', sa.String(length=64), nullable=True))
        if 'loadout_variants' not in cols:
            batch_op.add_column(sa.Column('loadout_variants', sa.JSON(), nullable=True))
        if 'supported_loadout_codes' not in cols:
            batch_op.add_column(sa.Column('supported_loadout_codes', sa.JSON(), nullable=True))
        if 'base_size_mm' not in cols:
            batch_op.add_column(sa.Column('base_size_mm', sa.Integer(), nullable=True))

        # Lineage and faction hints
        if 'lineage_family' not in cols:
            batch_op.add_column(sa.Column('lineage_family', sa.String(length=64), nullable=True))
        if 'lineage_primary' not in cols:
            batch_op.add_column(sa.Column('lineage_primary', sa.String(length=128), nullable=True))
        if 'lineage_aliases' not in cols:
            batch_op.add_column(sa.Column('lineage_aliases', sa.JSON(), nullable=True))
        if 'faction_general' not in cols:
            batch_op.add_column(sa.Column('faction_general', sa.String(length=128), nullable=True))
        if 'faction_path' not in cols:
            batch_op.add_column(sa.Column('faction_path', sa.JSON(), nullable=True))
        if 'franchise_hints' not in cols:
            batch_op.add_column(sa.Column('franchise_hints', sa.JSON(), nullable=True))
        if 'tabletop_role' not in cols:
            batch_op.add_column(sa.Column('tabletop_role', sa.String(length=64), nullable=True))
        if 'pc_candidate_flag' not in cols:
            batch_op.add_column(sa.Column('pc_candidate_flag', sa.Boolean(), nullable=True))
        if 'human_subtype' not in cols:
            batch_op.add_column(sa.Column('human_subtype', sa.String(length=64), nullable=True))
        if 'role_confidence' not in cols:
            batch_op.add_column(sa.Column('role_confidence', sa.String(length=32), nullable=True))
        if 'lineage_confidence' not in cols:
            batch_op.add_column(sa.Column('lineage_confidence', sa.String(length=32), nullable=True))

        # Classification and attributes
        if 'asset_category' not in cols:
            batch_op.add_column(sa.Column('asset_category', sa.String(length=64), nullable=True))
        if 'terrain_subtype' not in cols:
            batch_op.add_column(sa.Column('terrain_subtype', sa.String(length=64), nullable=True))
        if 'vehicle_type' not in cols:
            batch_op.add_column(sa.Column('vehicle_type', sa.String(length=64), nullable=True))
        if 'vehicle_era' not in cols:
            batch_op.add_column(sa.Column('vehicle_era', sa.String(length=64), nullable=True))
        if 'base_theme' not in cols:
            batch_op.add_column(sa.Column('base_theme', sa.String(length=64), nullable=True))
        if 'intended_use_bucket' not in cols:
            batch_op.add_column(sa.Column('intended_use_bucket', sa.String(length=64), nullable=True))
        if 'nsfw_level' not in cols:
            batch_op.add_column(sa.Column('nsfw_level', sa.String(length=32), nullable=True))
        if 'nsfw_exposure_top' not in cols:
            batch_op.add_column(sa.Column('nsfw_exposure_top', sa.String(length=32), nullable=True))
        if 'nsfw_exposure_bottom' not in cols:
            batch_op.add_column(sa.Column('nsfw_exposure_bottom', sa.String(length=32), nullable=True))
        if 'nsfw_act_tags' not in cols:
            batch_op.add_column(sa.Column('nsfw_act_tags', sa.JSON(), nullable=True))
        if 'segmentation' not in cols:
            batch_op.add_column(sa.Column('segmentation', sa.String(length=32), nullable=True))
        if 'internal_volume' not in cols:
            batch_op.add_column(sa.Column('internal_volume', sa.String(length=32), nullable=True))
        if 'support_state' not in cols:
            batch_op.add_column(sa.Column('support_state', sa.String(length=32), nullable=True))
        if 'has_slicer_project' not in cols:
            batch_op.add_column(sa.Column('has_slicer_project', sa.Boolean(), nullable=True))

        # Size/scale and variants
        if 'pose_variant' not in cols:
            batch_op.add_column(sa.Column('pose_variant', sa.String(length=128), nullable=True))
        if 'version_num' not in cols:
            batch_op.add_column(sa.Column('version_num', sa.Integer(), nullable=True))
        if 'part_pack_type' not in cols:
            batch_op.add_column(sa.Column('part_pack_type', sa.String(length=64), nullable=True))
        if 'has_bust_variant' not in cols:
            batch_op.add_column(sa.Column('has_bust_variant', sa.Boolean(), nullable=True))
        if 'scale_ratio_den' not in cols:
            batch_op.add_column(sa.Column('scale_ratio_den', sa.Integer(), nullable=True))
        # scale_name is handled by earlier migration
        if 'height_mm' not in cols:
            batch_op.add_column(sa.Column('height_mm', sa.Integer(), nullable=True))
        if 'mm_declared_conflict' not in cols:
            batch_op.add_column(sa.Column('mm_declared_conflict', sa.Boolean(), nullable=True))

        # Style
        if 'style_primary' not in cols:
            batch_op.add_column(sa.Column('style_primary', sa.String(length=64), nullable=True))
        if 'style_primary_confidence' not in cols:
            batch_op.add_column(sa.Column('style_primary_confidence', sa.String(length=32), nullable=True))
        if 'style_aesthetic_tags' not in cols:
            batch_op.add_column(sa.Column('style_aesthetic_tags', sa.JSON(), nullable=True))

        # Compatibility
        if 'addon_type' not in cols:
            batch_op.add_column(sa.Column('addon_type', sa.String(length=64), nullable=True))
        if 'requires_base_model' not in cols:
            batch_op.add_column(sa.Column('requires_base_model', sa.Boolean(), nullable=True))
        if 'compatibility_scope' not in cols:
            batch_op.add_column(sa.Column('compatibility_scope', sa.String(length=64), nullable=True))
        if 'compatible_units' not in cols:
            batch_op.add_column(sa.Column('compatible_units', sa.JSON(), nullable=True))
        if 'compatible_factions' not in cols:
            batch_op.add_column(sa.Column('compatible_factions', sa.JSON(), nullable=True))
        if 'multi_faction_flag' not in cols:
            batch_op.add_column(sa.Column('multi_faction_flag', sa.Boolean(), nullable=True))
        if 'compatible_model_group_ids' not in cols:
            batch_op.add_column(sa.Column('compatible_model_group_ids', sa.JSON(), nullable=True))
        if 'compatible_variant_ids' not in cols:
            batch_op.add_column(sa.Column('compatible_variant_ids', sa.JSON(), nullable=True))
        if 'compatibility_assertions' not in cols:
            batch_op.add_column(sa.Column('compatibility_assertions', sa.JSON(), nullable=True))
        if 'attachment_points' not in cols:
            batch_op.add_column(sa.Column('attachment_points', sa.JSON(), nullable=True))
        if 'replaces_parts' not in cols:
            batch_op.add_column(sa.Column('replaces_parts', sa.JSON(), nullable=True))
        if 'additive_only_flag' not in cols:
            batch_op.add_column(sa.Column('additive_only_flag', sa.Boolean(), nullable=True))
        if 'clothing_variant_flag' not in cols:
            batch_op.add_column(sa.Column('clothing_variant_flag', sa.Boolean(), nullable=True))
        if 'magnet_ready_flag' not in cols:
            batch_op.add_column(sa.Column('magnet_ready_flag', sa.Boolean(), nullable=True))

        # Tagging & notes
        if 'user_tags' not in cols:
            batch_op.add_column(sa.Column('user_tags', sa.JSON(), nullable=True))
        if 'notes' not in cols:
            batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

        # Residual/diagnostic fields
        if 'residual_tokens' not in cols:
            batch_op.add_column(sa.Column('residual_tokens', sa.JSON(), nullable=True))
        if 'token_version' not in cols:
            batch_op.add_column(sa.Column('token_version', sa.Integer(), nullable=True))
        if 'normalization_warnings' not in cols:
            batch_op.add_column(sa.Column('normalization_warnings', sa.JSON(), nullable=True))

        # Indexes for frequently queried fields
        if 'ix_variant_rel_path' not in idxs and 'rel_path' in (cols | {'rel_path'}):
            batch_op.create_index('ix_variant_rel_path', ['rel_path'])
        if 'ix_variant_extension' not in idxs and 'extension' in (cols | {'extension'}):
            batch_op.create_index('ix_variant_extension', ['extension'])
        if 'ix_variant_hash_sha256' not in idxs and 'hash_sha256' in (cols | {'hash_sha256'}):
            batch_op.create_index('ix_variant_hash_sha256', ['hash_sha256'])
        if 'ix_variant_designer' not in idxs and 'designer' in (cols | {'designer'}):
            batch_op.create_index('ix_variant_designer', ['designer'])
        if 'ix_variant_franchise' not in idxs and 'franchise' in (cols | {'franchise'}):
            batch_op.create_index('ix_variant_franchise', ['franchise'])
        if 'ix_variant_model_group_id' not in idxs and 'model_group_id' in (cols | {'model_group_id'}):
            batch_op.create_index('ix_variant_model_group_id', ['model_group_id'])
        if 'ix_variant_review_status' not in idxs and 'review_status' in (cols | {'review_status'}):
            batch_op.create_index('ix_variant_review_status', ['review_status'])
        if 'ix_variant_game_system' not in idxs and 'game_system' in (cols | {'game_system'}):
            batch_op.create_index('ix_variant_game_system', ['game_system'])
        if 'ix_variant_codex_faction' not in idxs and 'codex_faction' in (cols | {'codex_faction'}):
            batch_op.create_index('ix_variant_codex_faction', ['codex_faction'])
        if 'ix_variant_character_name' not in idxs and 'character_name' in (cols | {'character_name'}):
            batch_op.create_index('ix_variant_character_name', ['character_name'])
        if 'ix_variant_asset_category' not in idxs and 'asset_category' in (cols | {'asset_category'}):
            batch_op.create_index('ix_variant_asset_category', ['asset_category'])
        if 'ix_variant_is_dir' not in idxs and 'is_dir' in (cols | {'is_dir'}):
            batch_op.create_index('ix_variant_is_dir', ['is_dir'])


def downgrade() -> None:
    # Best-effort: drop indexes first, then a subset of columns if needed.
    with op.batch_alter_table('variant') as batch_op:
        for idx in (
            'ix_variant_is_dir','ix_variant_asset_category','ix_variant_character_name','ix_variant_codex_faction',
            'ix_variant_game_system','ix_variant_review_status','ix_variant_model_group_id','ix_variant_franchise',
            'ix_variant_designer','ix_variant_hash_sha256','ix_variant_extension','ix_variant_rel_path'
        ):
            try:
                batch_op.drop_index(idx)
            except Exception:
                pass
        for col in (
            'normalization_warnings','token_version','residual_tokens','notes','user_tags','magnet_ready_flag',
            'clothing_variant_flag','additive_only_flag','replaces_parts','attachment_points','compatibility_assertions',
            'compatible_variant_ids','compatible_model_group_ids','multi_faction_flag','compatible_factions',
            'compatible_units','compatibility_scope','requires_base_model','addon_type','style_aesthetic_tags',
            'style_primary_confidence','style_primary','mm_declared_conflict','height_mm','scale_ratio_den',
            'has_bust_variant','part_pack_type','version_num','pose_variant','has_slicer_project','support_state',
            'internal_volume','segmentation','nsfw_act_tags','nsfw_exposure_bottom','nsfw_exposure_top','nsfw_level',
            'intended_use_bucket','base_theme','vehicle_era','vehicle_type','terrain_subtype','asset_category',
            'lineage_confidence','role_confidence','human_subtype','pc_candidate_flag','tabletop_role','franchise_hints',
            'faction_path','faction_general','lineage_aliases','lineage_primary','lineage_family','base_size_mm',
            'supported_loadout_codes','loadout_variants','proxy_type','character_aliases','character_name',
            'codex_unit_name','codex_faction','game_system','collection_theme','collection_sequence_number',
            'collection_cycle','collection_original_label','collection_id','designer_confidence','confidence_score',
            'review_status','model_group_id','is_dir','depth','scan_batch_id','root_id'
        ):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass

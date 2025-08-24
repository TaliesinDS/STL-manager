"""One-off migration helper to ensure new nullable columns/tables exist.
This script is safe to run against an existing DB; it will call SQLAlchemy's
create_all() to create new tables and will use PRAGMA + ALTER TABLE to add
nullable columns to existing SQLite tables.
"""
from pathlib import Path
import sys

proj_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(proj_root))

from db.session import engine
from db.models import Base
from sqlalchemy import text


def run_migration():
    print("Running create_all() to add missing tables (if any)...")
    Base.metadata.create_all(bind=engine)

    # For existing tables, SQLite doesn't support ALTER COLUMN via SQLAlchemy
    # so we add missing nullable columns with raw ALTER TABLE statements.
    conn = engine.connect()

    def table_columns(table_name: str):
        res = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        # PRAGMA returns rows like: (cid, name, type, notnull, dflt_value, pk)
        return {row[1] for row in res}

    def add_column_if_missing(table_name: str, column_sql: str, column_name: str):
        cols = table_columns(table_name)
        if column_name in cols:
            print(f"Column '{column_name}' already exists on {table_name}")
            return False
        print(f"Adding column '{column_name}' to {table_name}")
        conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
        return True

    # Variant table additions
    variant_adds = [
        ("root_id TEXT", "root_id"),
        ("scan_batch_id TEXT", "scan_batch_id"),
        ("raw_path_tokens TEXT DEFAULT '[]'", "raw_path_tokens"),
        ("depth INTEGER", "depth"),
        ("is_dir BOOLEAN DEFAULT 0", "is_dir"),
        ("model_group_id TEXT", "model_group_id"),
        ("review_status TEXT", "review_status"),
        ("confidence_score REAL", "confidence_score"),
        ("designer_confidence TEXT", "designer_confidence"),
        ("collection_id TEXT", "collection_id"),
        ("collection_original_label TEXT", "collection_original_label"),
        ("collection_cycle TEXT", "collection_cycle"),
        ("collection_sequence_number INTEGER", "collection_sequence_number"),
        ("collection_theme TEXT", "collection_theme"),
        ("game_system TEXT", "game_system"),
        ("codex_faction TEXT", "codex_faction"),
        ("codex_unit_name TEXT", "codex_unit_name"),
    ("character_name TEXT", "character_name"),
    ("character_aliases TEXT DEFAULT '[]'", "character_aliases"),
        ("proxy_type TEXT", "proxy_type"),
        ("loadout_variants TEXT DEFAULT '[]'", "loadout_variants"),
        ("supported_loadout_codes TEXT DEFAULT '[]'", "supported_loadout_codes"),
        ("base_size_mm INTEGER", "base_size_mm"),
        ("lineage_family TEXT", "lineage_family"),
        ("lineage_primary TEXT", "lineage_primary"),
        ("lineage_aliases TEXT DEFAULT '[]'", "lineage_aliases"),
        ("faction_general TEXT", "faction_general"),
        ("faction_path TEXT DEFAULT '[]'", "faction_path"),
        ("tabletop_role TEXT", "tabletop_role"),
        ("pc_candidate_flag BOOLEAN DEFAULT 0", "pc_candidate_flag"),
        ("human_subtype TEXT", "human_subtype"),
        ("role_confidence TEXT", "role_confidence"),
        ("lineage_confidence TEXT", "lineage_confidence"),
        ("asset_category TEXT", "asset_category"),
        ("terrain_subtype TEXT", "terrain_subtype"),
        ("vehicle_type TEXT", "vehicle_type"),
        ("vehicle_era TEXT", "vehicle_era"),
        ("base_theme TEXT", "base_theme"),
        ("intended_use_bucket TEXT", "intended_use_bucket"),
        ("nsfw_level TEXT", "nsfw_level"),
        ("nsfw_exposure_top TEXT", "nsfw_exposure_top"),
        ("nsfw_exposure_bottom TEXT", "nsfw_exposure_bottom"),
        ("nsfw_act_tags TEXT DEFAULT '[]'", "nsfw_act_tags"),
        ("segmentation TEXT", "segmentation"),
        ("internal_volume TEXT", "internal_volume"),
        ("support_state TEXT", "support_state"),
        ("has_slicer_project BOOLEAN DEFAULT 0", "has_slicer_project"),
        ("pose_variant TEXT", "pose_variant"),
        ("version_num INTEGER", "version_num"),
        ("part_pack_type TEXT", "part_pack_type"),
        ("has_bust_variant BOOLEAN DEFAULT 0", "has_bust_variant"),
        ("scale_ratio_den INTEGER", "scale_ratio_den"),
        ("height_mm INTEGER", "height_mm"),
        ("mm_declared_conflict BOOLEAN DEFAULT 0", "mm_declared_conflict"),
        ("style_primary TEXT", "style_primary"),
        ("style_primary_confidence TEXT", "style_primary_confidence"),
        ("style_aesthetic_tags TEXT DEFAULT '[]'", "style_aesthetic_tags"),
        ("addon_type TEXT", "addon_type"),
        ("requires_base_model BOOLEAN DEFAULT 0", "requires_base_model"),
        ("compatibility_scope TEXT", "compatibility_scope"),
        ("compatible_units TEXT DEFAULT '[]'", "compatible_units"),
        ("compatible_factions TEXT DEFAULT '[]'", "compatible_factions"),
        ("multi_faction_flag BOOLEAN DEFAULT 0", "multi_faction_flag"),
        ("compatible_model_group_ids TEXT DEFAULT '[]'", "compatible_model_group_ids"),
        ("compatible_variant_ids TEXT DEFAULT '[]'", "compatible_variant_ids"),
        ("compatibility_assertions TEXT DEFAULT '[]'", "compatibility_assertions"),
        ("attachment_points TEXT DEFAULT '[]'", "attachment_points"),
        ("replaces_parts TEXT DEFAULT '[]'", "replaces_parts"),
        ("additive_only_flag BOOLEAN DEFAULT 0", "additive_only_flag"),
        ("clothing_variant_flag BOOLEAN DEFAULT 0", "clothing_variant_flag"),
        ("magnet_ready_flag BOOLEAN DEFAULT 0", "magnet_ready_flag"),
        ("user_tags TEXT DEFAULT '[]'", "user_tags"),
        ("notes TEXT", "notes"),
    ]

    for sql, name in variant_adds:
        try:
            add_column_if_missing("variant", sql, name)
        except Exception as e:
            print(f"Failed to add column {name} to variant: {e}")

    # File table additions
    file_adds = [
        ("raw_path_tokens TEXT DEFAULT '[]'", "raw_path_tokens"),
        ("depth INTEGER", "depth"),
        ("is_dir BOOLEAN DEFAULT 0", "is_dir"),
    ]
    for sql, name in file_adds:
        try:
            add_column_if_missing("file", sql, name)
        except Exception as e:
            print(f"Failed to add column {name} to file: {e}")

    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    run_migration()

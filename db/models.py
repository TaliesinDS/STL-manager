from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Text,
    JSON,
    LargeBinary,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Variant(Base):
    __tablename__ = "variant"

    id = Column(Integer, primary_key=True, index=True)
    rel_path = Column(String(1024), nullable=False, index=True)
    # Variants represent logical model variants (often a folder). Filename is
    # optional because a variant may contain multiple files.
    filename = Column(String(512), nullable=True)
    extension = Column(String(32), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=True)
    mtime_iso = Column(String(64), nullable=True)
    is_archive = Column(Boolean, default=False)
    hash_sha256 = Column(String(128), nullable=True, index=True)

    # Normalized metadata fields (phase P0/P1 subset)
    designer = Column(String(256), nullable=True, index=True)
    franchise = Column(String(256), nullable=True, index=True)
    content_flag = Column(String(32), nullable=True)

    # Additional P0/P1 fields recommended by MetadataFields.md
    root_id = Column(String(256), nullable=True, index=True)
    scan_batch_id = Column(String(128), nullable=True, index=True)
    raw_path_tokens = Column(JSON, default=list)
    depth = Column(Integer, nullable=True)
    is_dir = Column(Boolean, default=False)
    model_group_id = Column(String(64), nullable=True, index=True)

    # Workflow / review fields
    review_status = Column(String(32), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)
    # Designer & collection
    designer_confidence = Column(String(32), nullable=True)
    collection_id = Column(String(64), nullable=True, index=True)
    collection_original_label = Column(String(512), nullable=True)
    collection_cycle = Column(String(16), nullable=True)
    collection_sequence_number = Column(Integer, nullable=True)
    collection_theme = Column(String(128), nullable=True)

    # Tabletop / franchise / character fields (P1/P2)
    game_system = Column(String(128), nullable=True, index=True)
    codex_faction = Column(String(256), nullable=True, index=True)
    codex_unit_name = Column(String(256), nullable=True)
    # Character fields: preferred place to store named characters/aliases
    character_name = Column(String(256), nullable=True, index=True)
    character_aliases = Column(JSON, default=list)
    proxy_type = Column(String(64), nullable=True)
    loadout_variants = Column(JSON, default=list)
    supported_loadout_codes = Column(JSON, default=list)
    base_size_mm = Column(Integer, nullable=True)

    lineage_family = Column(String(64), nullable=True, index=True)
    lineage_primary = Column(String(128), nullable=True)
    lineage_aliases = Column(JSON, default=list)
    faction_general = Column(String(128), nullable=True)
    faction_path = Column(JSON, default=list)
    franchise_hints = Column(JSON, default=list)
    tabletop_role = Column(String(64), nullable=True)
    pc_candidate_flag = Column(Boolean, default=False)
    human_subtype = Column(String(64), nullable=True)
    role_confidence = Column(String(32), nullable=True)
    lineage_confidence = Column(String(32), nullable=True)

    # Variant dimensions and classification
    asset_category = Column(String(64), nullable=True, index=True)
    terrain_subtype = Column(String(64), nullable=True)
    vehicle_type = Column(String(64), nullable=True)
    vehicle_era = Column(String(64), nullable=True)
    base_theme = Column(String(64), nullable=True)
    intended_use_bucket = Column(String(64), nullable=True)
    nsfw_level = Column(String(32), nullable=True)
    nsfw_exposure_top = Column(String(32), nullable=True)
    nsfw_exposure_bottom = Column(String(32), nullable=True)
    nsfw_act_tags = Column(JSON, default=list)
    segmentation = Column(String(32), nullable=True)
    internal_volume = Column(String(32), nullable=True)
    support_state = Column(String(32), nullable=True)
    has_slicer_project = Column(Boolean, default=False)

    pose_variant = Column(String(128), nullable=True)
    version_num = Column(Integer, nullable=True)
    part_pack_type = Column(String(64), nullable=True)
    has_bust_variant = Column(Boolean, default=False)
    scale_ratio_den = Column(Integer, nullable=True)
    height_mm = Column(Integer, nullable=True)
    mm_declared_conflict = Column(Boolean, default=False)

    style_primary = Column(String(64), nullable=True)
    style_primary_confidence = Column(String(32), nullable=True)
    style_aesthetic_tags = Column(JSON, default=list)

    addon_type = Column(String(64), nullable=True)
    requires_base_model = Column(Boolean, default=False)
    compatibility_scope = Column(String(64), nullable=True)
    compatible_units = Column(JSON, default=list)
    compatible_factions = Column(JSON, default=list)
    multi_faction_flag = Column(Boolean, default=False)
    compatible_model_group_ids = Column(JSON, default=list)
    compatible_variant_ids = Column(JSON, default=list)
    compatibility_assertions = Column(JSON, default=list)
    attachment_points = Column(JSON, default=list)
    replaces_parts = Column(JSON, default=list)
    additive_only_flag = Column(Boolean, default=False)
    clothing_variant_flag = Column(Boolean, default=False)
    magnet_ready_flag = Column(Boolean, default=False)

    # Tagging & notes
    user_tags = Column(JSON, default=list)
    notes = Column(Text, nullable=True)

    # Residual/diagnostic fields
    residual_tokens = Column(JSON, default=list)
    token_version = Column(Integer, nullable=True)
    normalization_warnings = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Kit/container relationships (self-referential)
    parent_id = Column(Integer, ForeignKey("variant.id", ondelete="SET NULL"), nullable=True, index=True)
    is_kit_container = Column(Boolean, default=False, index=True)
    kit_child_types = Column(JSON, default=list)

    # Relationship to physical files belonging to this variant
    files = relationship("File", back_populates="variant", cascade="all, delete-orphan")
    # Relationships to codex units (via association table)
    unit_links = relationship("VariantUnitLink", back_populates="variant", cascade="all, delete-orphan")
    # Convenience read-only relationship listing units linked to this variant
    units = relationship("Unit", secondary="variant_unit_link", viewonly=True)
    # Relationships to parts (wargear/bodies) via association table
    part_links = relationship("VariantPartLink", back_populates="variant", cascade="all, delete-orphan")
    parts = relationship("Part", secondary="variant_part_link", viewonly=True)
    # Parent/children self-relation
    parent = relationship("Variant", remote_side=[id], backref="children", foreign_keys=[parent_id])

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Variant id={self.id} path={self.rel_path} file={self.filename}>"


class Archive(Base):
    __tablename__ = "archive"

    id = Column(Integer, primary_key=True)
    rel_path = Column(String(1024), nullable=False)
    filename = Column(String(512), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    hash_sha256 = Column(String(128), nullable=True)
    nested_archive_flag = Column(Boolean, default=False)
    scan_first_seen_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Archive id={self.id} file={self.filename}>"


class File(Base):
    __tablename__ = "file"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variant.id", ondelete="CASCADE"), nullable=False, index=True)
    rel_path = Column(String(1024), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    extension = Column(String(32), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=True)
    mtime_iso = Column(String(64), nullable=True)
    is_archive = Column(Boolean, default=False)
    hash_sha256 = Column(String(128), nullable=True, index=True)

    # Residual tokens or diagnostics for the specific file
    residual_tokens = Column(JSON, default=list)
    token_version = Column(Integer, nullable=True)
    # Additional per-file fields useful for P0/P1
    raw_path_tokens = Column(JSON, default=list)
    depth = Column(Integer, nullable=True)
    is_dir = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    variant = relationship("Variant", back_populates="files")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<File id={self.id} path={self.rel_path} file={self.filename}>"


class VocabEntry(Base):
    __tablename__ = "vocab_entry"

    id = Column(Integer, primary_key=True)
    domain = Column(String(64), nullable=False, index=True)  # e.g., 'designer', 'franchise'
    key = Column(String(256), nullable=False, index=True)
    aliases = Column(JSON, default=list)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VocabEntry {self.domain}:{self.key}>"


class Job(Base):
    __tablename__ = "job"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    status = Column(String(32), default="pending", index=True)
    progress = Column(Integer, default=0)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Job id={self.id} name={self.name} status={self.status}>"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(Integer, nullable=True, index=True)
    field = Column(String(128), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    actor = Column(String(128), nullable=True)
    ts = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<AuditLog {self.resource_type}:{self.resource_id} {self.field}>"


class VariantArchive(Base):
    __tablename__ = "variant_archive"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variant.id", ondelete="CASCADE"), nullable=False, index=True)
    archive_id = Column(Integer, ForeignKey("archive.id", ondelete="CASCADE"), nullable=False, index=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VariantArchive variant={self.variant_id} archive={self.archive_id}>"


class Collection(Base):
    __tablename__ = "collection"

    id = Column(Integer, primary_key=True)
    original_label = Column(String(512), nullable=True)
    publisher = Column(String(256), nullable=True)
    cycle = Column(String(16), nullable=True)
    sequence_number = Column(Integer, nullable=True)
    theme = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Collection id={self.id} label={self.original_label}>"


class Character(Base):
    __tablename__ = "character"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False, index=True)
    aliases = Column(JSON, default=list)
    franchise = Column(String(256), nullable=True)
    actor_likeness = Column(String(256), nullable=True)
    actor_confidence = Column(String(32), nullable=True)
    info_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Character id={self.id} name={self.name}>"


# =========================
# Codex/Units Normalization
# =========================

class GameSystem(Base):
    """A tabletop game system, e.g., Warhammer 40,000, Age of Sigmar, Horus Heresy.

    key examples: 'w40k', 'aos', 'heresy', 'old_world'.
    """

    __tablename__ = "game_system"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    factions = relationship("Faction", back_populates="system", cascade="all, delete-orphan")
    units = relationship("Unit", back_populates="system")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<GameSystem {self.key}:{self.name}>"


class Faction(Base):
    """Faction within a game system; supports hierarchy via parent_id (e.g., Space Marines -> Dark Angels chapter)."""

    __tablename__ = "faction"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("game_system.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(128), nullable=False, index=True)  # canonical snake_case token
    name = Column(String(256), nullable=False)
    parent_id = Column(Integer, ForeignKey("faction.id", ondelete="CASCADE"), nullable=True, index=True)
    # Optional convenience fields
    full_path = Column(JSON, default=list)  # e.g., ["imperium", "adeptus_astartes", "dark_angels"]
    aliases = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    system = relationship("GameSystem", back_populates="factions")
    parent = relationship("Faction", remote_side=[id], backref="children")
    units = relationship("Unit", back_populates="faction")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Faction {self.key} system={self.system_id}>"


class Unit(Base):
    """A codex unit entry from YAML SSOT.

    Stores edition availability and base profile as simple strings/JSON for portability.
    """

    __tablename__ = "unit"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("game_system.id", ondelete="CASCADE"), nullable=False, index=True)
    faction_id = Column(Integer, ForeignKey("faction.id", ondelete="SET NULL"), nullable=True, index=True)

    key = Column(String(128), nullable=False, index=True)  # canonical snake_case YAML id
    name = Column(String(256), nullable=False, index=True)
    role = Column(String(64), nullable=True, index=True)  # e.g., HQ, Troops, Leader, etc.
    unique_flag = Column(Boolean, default=False)
    # category allows system-specific types (e.g., 'unit', 'endless_spell', 'manifestation', 'invocation', 'terrain', 'regiment')
    category = Column(String(64), nullable=True, index=True)

    # JSON fields reflecting YAML structure
    aliases = Column(JSON, default=list)
    legal_in_editions = Column(JSON, default=list)  # e.g., ["10e"], ["10e","legends_10e"], ["aos4"]
    available_to = Column(JSON, default=dict)  # e.g., {"chapters": ["dark_angels"], ...}
    base_profile_key = Column(String(64), nullable=True)  # e.g., "infantry_25", "cavalry_60_35", etc.
    # attributes captures extra per-system fields that don't merit first-class columns yet
    attributes = Column(JSON, default=dict)
    # raw_data stores the full YAML node for perfect fidelity and future migrations
    raw_data = Column(JSON, default=dict)

    # Provenance
    source_file = Column(String(512), nullable=True)  # vocab file path relative to repo
    source_anchor = Column(String(256), nullable=True)  # optional YAML path or group
    created_at = Column(DateTime, default=datetime.utcnow)

    system = relationship("GameSystem", back_populates="units")
    faction = relationship("Faction", back_populates="units")
    alias_rows = relationship("UnitAlias", back_populates="unit", cascade="all, delete-orphan")
    variant_links = relationship("VariantUnitLink", back_populates="unit", cascade="all, delete-orphan")
    variants = relationship("Variant", secondary="variant_unit_link", viewonly=True)
    # Parts linked to this unit (manual or inferred)
    part_links = relationship("UnitPartLink", back_populates="unit", cascade="all, delete-orphan")
    parts = relationship("Part", secondary="unit_part_link", viewonly=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Unit {self.key} ({self.name}) system={self.system_id}>"


class UnitAlias(Base):
    __tablename__ = "unit_alias"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("unit.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(256), nullable=False, index=True)

    unit = relationship("Unit", back_populates="alias_rows")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<UnitAlias unit={self.unit_id} alias={self.alias}>"


class VariantUnitLink(Base):
    """Association between a scanned Variant (model folder/file) and a codex Unit.

    Stores match metadata so we can audit how a link was established.
    """

    __tablename__ = "variant_unit_link"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variant.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("unit.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary = Column(Boolean, default=True)
    match_method = Column(String(64), nullable=True)  # e.g., "token", "manual", "yaml-guided"
    match_confidence = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    variant = relationship("Variant", back_populates="unit_links")
    unit = relationship("Unit", back_populates="variant_links")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VariantUnitLink v={self.variant_id} u={self.unit_id} primary={self.is_primary}>"


# =========================
# Parts (Wargear/Bodies)
# =========================

class Part(Base):
    """A modular 3D model part such as wargear (weapons, accessories) or body types.

    Designed to index third-party add-on parts and decorative bits. Not full units.
    """

    __tablename__ = "part"

    id = Column(Integer, primary_key=True)
    system_id = Column(Integer, ForeignKey("game_system.id", ondelete="CASCADE"), nullable=False, index=True)
    faction_id = Column(Integer, ForeignKey("faction.id", ondelete="SET NULL"), nullable=True, index=True)

    key = Column(String(128), nullable=False, index=True)
    name = Column(String(256), nullable=False, index=True)
    part_type = Column(String(64), nullable=False, index=True)  # e.g., 'wargear', 'body', 'decor'
    category = Column(String(64), nullable=True, index=True)  # e.g., weapon_ranged, character class, etc.
    slot = Column(String(64), nullable=True, index=True)  # singular slot for wargear (left_hand, backpack, etc.)
    slots = Column(JSON, default=list)  # multi-slot support (e.g., bodies)

    aliases = Column(JSON, default=list)
    legal_in_editions = Column(JSON, default=list)
    legends_in_editions = Column(JSON, default=list)
    available_to = Column(JSON, default=list)  # list of faction keys

    attributes = Column(JSON, default=dict)  # any extra fields from YAML
    raw_data = Column(JSON, default=dict)

    source_file = Column(String(512), nullable=True)
    source_anchor = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    system = relationship("GameSystem")
    faction = relationship("Faction")
    alias_rows = relationship("PartAlias", back_populates="part", cascade="all, delete-orphan")
    variant_links = relationship("VariantPartLink", back_populates="part", cascade="all, delete-orphan")
    variants = relationship("Variant", secondary="variant_part_link", viewonly=True)
    unit_links = relationship("UnitPartLink", back_populates="part", cascade="all, delete-orphan")
    units = relationship("Unit", secondary="unit_part_link", viewonly=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Part {self.part_type}:{self.key} ({self.name}) system={self.system_id}>"


class PartAlias(Base):
    __tablename__ = "part_alias"

    id = Column(Integer, primary_key=True)
    part_id = Column(Integer, ForeignKey("part.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(256), nullable=False, index=True)

    part = relationship("Part", back_populates="alias_rows")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<PartAlias part={self.part_id} alias={self.alias}>"


class VariantPartLink(Base):
    """Association between a scanned Variant (model) and a Part (wargear/body/decor)."""

    __tablename__ = "variant_part_link"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("variant.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("part.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary = Column(Boolean, default=False)  # parts are typically secondary to a full model
    match_method = Column(String(64), nullable=True)
    match_confidence = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    variant = relationship("Variant", back_populates="part_links")
    part = relationship("Part", back_populates="variant_links")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VariantPartLink v={self.variant_id} p={self.part_id} primary={self.is_primary}>"


class UnitPartLink(Base):
    """Association between a codex Unit and a Part to express compatibility/recommendations."""

    __tablename__ = "unit_part_link"

    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("unit.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey("part.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(32), nullable=True)  # e.g., 'compatible', 'recommended', 'required'
    required_slot = Column(String(64), nullable=True)  # optional slot constraint
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    unit = relationship("Unit", back_populates="part_links")
    part = relationship("Part", back_populates="unit_links")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<UnitPartLink u={self.unit_id} p={self.part_id} rel={self.relation_type}>"

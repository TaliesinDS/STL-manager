# Metadata Fields Specification

Status update (2025-09-03)
- Core Variant/File inventory fields are implemented and populated for the working dataset.
- Enrichment in production use: designer (+confidence), intended_use_bucket, lineage_family/primary, franchise/character (with `Character` table), system/faction/unit hints, segmentation/support_state, parts/kit fields, and multilingual columns (`english_tokens`, `token_locale`, `ui_display_en`).
- Tabletop linking is live via `variant_unit_link`; parts linking via `variant_part_link` (and `unit_part_link` for compatibility) is available.
- Scale fields exist and are populated where detectable: `scale_ratio_den`, `scale_name`, `height_mm` (with guards for false positives).
- Fields listed as FUTURE in this doc are not persisted yet; the spec intentionally overstates later phases to keep names stable.

Moved from repository root to `docs/` on 2025-08-16 (repository restructure) – content unchanged.

Purpose: Define all planned metadata fields for the STL Manager project, their intent, data type, allowed values, introduction phase, and notes so early planning stays consistent and we avoid premature complexity.

**Legend:** Fields marked with **(DB)** are already implemented in `db/models.py` (SQLAlchemy models).

### Implementation status (sections 1–11)

| Field | Section | Phase | Implemented | Notes |
|---|---:|---:|---:|---|
| id | Core identification | P1 | Yes | `variant.id` (Integer PK) |
| model_group_id | Core identification | P2 | Yes | `variant.model_group_id` (string) |
| archive_id | Core identification | P1 | Yes (via join) | `archive` + `variant_archive` join table |
| root_id | File system inventory | P0 | Yes | `variant.root_id` |
| rel_path | File system inventory | P0 | Yes | `variant.rel_path` |
| filename | File system inventory | P0 | Yes | `variant.filename` / `file.filename` |
| extension | File system inventory | P0 | Yes | `variant.extension`, `file.extension` |
| size_bytes | File system inventory | P0 | Yes | `variant.size_bytes`, `file.size_bytes` |
| mtime_iso | File system inventory | P0 | Yes | `variant.mtime_iso`, `file.mtime_iso` |
| depth | File system inventory | P0 | Yes | `variant.depth`, `file.depth` |
| is_dir | File system inventory | P0 | Yes | `variant.is_dir`, `file.is_dir` |
| is_archive | File system inventory | P0 | Yes | `variant.is_archive`, `file.is_archive` |
| scan_batch_id | File system inventory | P0 | Yes | `variant.scan_batch_id` |
| source_archives | Provenance / Source | P1 | No | Virtual/derived; rely on `variant_archive` + hashing later |
| original_archive_filename | Provenance / Source | P1 | No | Not present; could be stored on `archive` |
| distribution_source | Provenance / Source | P2 | No | Pending (enum) |
| license_status | Provenance / Source | FUTURE | No | Pending (FUTURE) |
| designer | Designer & collection | P1 | Yes | `variant.designer` |
| designer_confidence | Designer & collection | P1 | Yes | `variant.designer_confidence` |
| collection_id | Designer & collection | P2 | Yes | `variant.collection_id` (string) and `collection` table exists |
| collection_original_label | Designer & collection | P1 | Yes | `variant.collection_original_label` |
| collection_cycle | Designer & collection | P1 | Yes | `variant.collection_cycle` |
| collection_sequence_number | Designer & collection | P1 | Yes | `variant.collection_sequence_number` |
| collection_theme | Designer & collection | P2 | Yes | `variant.collection_theme` |
| franchise | Franchise & Character | P2 | Yes | `variant.franchise` |
| sub_franchise | Franchise & Character | P2 | No | Not implemented separately |
| character_name / character entity | Franchise & Character | P2 | Yes | `character` table exists (`name`, `aliases`, `actor_likeness`, `actor_confidence`) |
| actor_likeness | Franchise & Character | P2 | Yes | `character.actor_likeness` |
| actor_confidence | Franchise & Character | P2 | Yes | `character.actor_confidence` |
| game_system | Tabletop mapping | P1 | Yes | `variant.game_system` |
| codex_faction | Tabletop mapping | P1 | Yes | `variant.codex_faction` |
| codex_unit_name | Tabletop mapping | P2 | Yes | `variant.codex_unit_name` |
| proxy_type | Tabletop mapping | P2 | Yes | `variant.proxy_type` |
| multi_unit_proxy_flag | Tabletop mapping | P2 | No | Not present; derive later from relationships |
| loadout_variants | Tabletop mapping | P2 | Yes | `variant.loadout_variants` (JSON) |
| supported_loadout_codes | Tabletop mapping | P2 | Yes | `variant.supported_loadout_codes` (JSON) |
| base_size_mm | Tabletop mapping | P2 | Yes | `variant.base_size_mm` |
| lineage_family | Tabletop mapping | P1 | Yes | `variant.lineage_family` |
| lineage_primary | Tabletop mapping | P2 | Yes | `variant.lineage_primary` |
| lineage_aliases | Tabletop mapping | P2 | Yes | `variant.lineage_aliases` (JSON) |
| faction_general | Tabletop mapping | P1 | Yes | `variant.faction_general` |
| faction_path | Tabletop mapping | P2 | Yes | `variant.faction_path` (JSON) |
| tabletop_role | Tabletop mapping | P2 | Yes | `variant.tabletop_role` |
| pc_candidate_flag | Tabletop mapping | P1 | Yes | `variant.pc_candidate_flag` |
| asset_category | Variant dimensions | P1 | Yes | `variant.asset_category` |
| terrain_subtype | Variant dimensions | P2 | Yes | `variant.terrain_subtype` |
| vehicle_type | Variant dimensions | P2 | Yes | `variant.vehicle_type` |
| vehicle_era | Variant dimensions | P2 | Yes | `variant.vehicle_era` |
| base_theme | Variant dimensions | P2 | Yes | `variant.base_theme` |
| intended_use_bucket | Variant dimensions | P1 | Yes | `variant.intended_use_bucket` |
| content_flag | Variant dimensions | P1 | Yes | `variant.content_flag` |
| nsfw_level / exposures / act_tags | Variant dimensions | P2 | Yes | `variant.nsfw_level`, `nsfw_exposure_top`, `nsfw_exposure_bottom`, `nsfw_act_tags` |
| segmentation | Variant dimensions | P1 | Yes | `variant.segmentation` |
| internal_volume | Variant dimensions | P1 | Yes | `variant.internal_volume` |
| support_state | Variant dimensions | P1 | Yes | `variant.support_state` |
| has_slicer_project | Variant dimensions | P1 | Yes | `variant.has_slicer_project` |
| pose_variant | Variant dimensions | P2 | Yes | `variant.pose_variant` |
| version_num | Variant dimensions | P2 | Yes | `variant.version_num` |
| part_pack_type | Variant dimensions | P2 | Yes | `variant.part_pack_type` |
| has_bust_variant | Variant dimensions | P2 | Yes | `variant.has_bust_variant` |
| scale_ratio_den | Variant dimensions | P1 | Yes | `variant.scale_ratio_den` |
| height_mm | Variant dimensions | P1 | Yes | `variant.height_mm` |
| mm_declared_conflict | Variant dimensions | P2 | Yes | `variant.mm_declared_conflict` |
| style_primary / style_primary_confidence / style_aesthetic_tags | Variant dimensions | P1/P2 | Yes | `variant.style_primary`, `style_primary_confidence`, `style_aesthetic_tags` (JSON) |
| addon_type | Compatibility & tags | P2 | Yes | `variant.addon_type` |
| requires_base_model | Compatibility & tags | P2 | Yes | `variant.requires_base_model` |
| compatibility_scope | Compatibility & tags | P2 | Yes | `variant.compatibility_scope` |
| compatible_units | Compatibility & tags | P2 | Yes | `variant.compatible_units` (JSON) |
| compatible_factions | Compatibility & tags | P2 | Yes | `variant.compatible_factions` (JSON) |
| multi_faction_flag | Compatibility & tags | P2 | Yes | `variant.multi_faction_flag` |
| compatible_model_group_ids / compatible_variant_ids | Compatibility & tags | P2 | Yes | `variant.compatible_model_group_ids`, `compatible_variant_ids` (JSON) |
| compatibility_assertions | Compatibility & tags | P2 | Yes | `variant.compatibility_assertions` (JSON) |
| attachment_points | Compatibility & tags | P2 | Yes | `variant.attachment_points` (JSON) |
| replaces_parts | Compatibility & tags | P2 | Yes | `variant.replaces_parts` (JSON) |
| additive_only_flag / clothing_variant_flag / magnet_ready_flag | Compatibility & tags | P2 | Yes | `variant.additive_only_flag`, `clothing_variant_flag`, `magnet_ready_flag` |
| user_tags / residual_tokens / token_version / normalization_warnings | Tagging / residuals | P1 | Yes | `variant.user_tags`, `variant.residual_tokens`, `variant.token_version`, `variant.normalization_warnings` |
| notes | Audit / Workflow | P1 | Yes | `variant.notes` (Text) |
| created_at / updated_at | Audit / Workflow | P1 | Yes | `variant.created_at`, `variant.updated_at` |
| file table fields | Files / archives / joins | P0 | Yes | `file` table exists; per-file metadata present |
| archive table fields | Files / archives / joins | P0 | Yes | `archive` table exists |
| variant_archive join | Files / archives / joins | P1 | Yes | `variant_archive` table exists |
| vocab_entry / job / audit_log / collection / character tables | Other support | P1–P2 | Yes | present in models |

Fields not explicitly implemented (examples / non-exhaustive): `source_archives` (virtual array), `distribution_source`, `license_status`, `sub_franchise`, `likeness_rights_flag`, `multi_unit_proxy_flag` (derived), `loadout_coverage_summary` (virtual), `rule_edition`, and many geometry-derived fields (triangle_count, manifold_flag, bounding_box_mm, volume_cc, thin_wall_warnings).

Phase Legend:
- P0 = Phase 0 (initial passive inventory; **no archive extraction**, minimal parsing)
- P1 = Early enrichment (basic normalization, simple token parsing)
- P2 = Variant grouping & advanced classification
- P3 = Geometry analysis / hashing / dedupe
- P4 = AI-assisted tagging & inference
- FUTURE = Not scheduled yet / speculative

> Principle: Introduce only what we can reliably populate; leave placeholders for future fields so the model remains stable.

---
## 1. Core Identification
| Field | Type | Phase | Description | Notes |
|-------|------|-------|-------------|-------|
| id | UUID / integer | P1 | Primary key for a ModelVariant record | Could start as incremental in a local DB |
| model_group_id | UUID | P2 | Links variants that share the same underlying character/figure concept | Created during grouping |
| archive_id | UUID | P1 | Source archive reference | One variant can belong to multiple archives via join table |

## 2. File System Inventory
| Field | Type | Phase | Description | Notes |
| root_id | string | P0 | Logical root label for scan | e.g., `tabletop_intent_root1` |
| rel_path | string | P0 | Relative path from root (POSIX style) | Store raw; do not normalize case |
| filename | string | P0 | Leaf name | |
| extension | string | P0 | Lowercased extension (no dot) | |
| size_bytes | integer | P0 | File size | |
| mtime_iso | ISO8601 string | P0 | Last modified time (UTC) | Optional if cheap |
| depth | integer | P0 | Directory depth (root=0) | |
| is_dir | boolean | P0 | Directory flag (mostly false in inventory file view) | |
| is_archive | boolean | P0 | Extension in {zip, rar, 7z, tar, …} | Archives not unpacked in P0 |
| scan_batch_id | UUID | P0 | Batch identifier to group a scan run | Allows diffing |

## 3. Provenance / Source
| Field | Type | Phase | Description | Notes |
| source_archives | array<archive_id> | P1 | All archives containing equivalent file content | Needs hashing (P3) to fully populate |
| original_archive_filename | string | P1 | Name of archive file first seen | |
| distribution_source | enum | P2 | Platform: patreon, myminifactory, gumroad, cgtrader, unknown | Parsed from tokens / docs |
| license_status | enum | FUTURE | personal_use, commercial_license, unknown | From included license text |

## 4. Designer & Collection
| Field | Type | Phase | Description | Notes |
| designer | string | P1 | Sculptor / studio normalized name | Repetition heuristic |
| designer_confidence | enum | P1 | certain, probable, guess | Manual upgrade |
| collection_id | UUID | P2 | Monthly / thematic collection reference | Ghamak March 2023 etc. |
| collection_original_label | string | P1 | Raw folder/archive label | Preserve token form |
| collection_cycle | string (YYYY-MM) | P1 | Year-month extracted | Regex month mapping |
| collection_sequence_number | integer | P1 | Numeric prefix like 52 | Optional |
| collection_theme | string | P2 | Fantasy / Sci-Fi etc. | Simple controlled set |

## 5. Franchise & Character
| Field | Type | Phase | Description | Notes |
| franchise | string | P2 | Canonical IP (marvel, dragon_ball, lotr, lol, etc.) | Controlled vocabulary |
| sub_franchise | string | P2 | e.g., marvel_cinematic_universe | Optional |
| character_name | string | P2 | Canonical character (hermione_granger) | Snake case |
| character_aliases | array<string> | P2 | Raw tokens / alternative spellings | Kept for search |
| actor_likeness | string | P2 | Actor name if likeness-based | Manual confirm |
| actor_confidence | enum | P2 | certain, probable, stylized, composite | Starts as probable if auto-detected |
| likeness_rights_flag | enum | FUTURE | potential_issue | For filtering/export compliance |

## 6. Tabletop Game Mapping
| Field | Type | Phase | Description | Notes |
| game_system | string | P1 | warhammer_40k, age_of_sigmar, dnd5e, etc. | Token normalization |
| codex_faction | string | P1 | e.g., necrons, ossiarch_bonereapers | |
| codex_unit_name | string | P2 | Kainan's Reapers | Apostrophes preserved |
| proxy_type | enum | P2 | official, direct_clone, stylized_proxy, counts_as, kitbash_pack | Manual / heuristic (coarse overall classification for the variant as a whole) |
| multi_unit_proxy_flag | boolean | P2 | Variant can legitimately represent multiple distinct codex units depending on selected/printed loadout | Derived if >1 variant_unit row with distinct unit_ids |
| loadout_variants | array<string> | P2 | Weapon / gear options | From tokens |
| supported_loadout_codes | array<string> | P2 | Normalized loadout codes this variant (alone) can realize (e.g., bolter, plasma_gun, power_fist) | Derived from filenames / part tokens; excludes those only achievable via external kits |
| loadout_coverage_summary | JSON (virtual) | P2 | Per candidate unit: list of loadouts with status (complete, partial, missing) and missing component codes | Not persisted; computed on demand |
| base_size_mm | integer | P2 | 25, 32, 40, 60, etc. | Derived / manual |
| rule_edition | integer | FUTURE | Edition number | If encoded |
| lineage_family | string | P1 | Broad ancestry bucket (elf, human, dwarf, orc, undead, demon, construct, plantfolk, beastfolk, lizardfolk, dragonkin, angelic, aberration, goblin, halfling, giant, vampire, werebeast, slime, skeleton, insectfolk, elemental, fae, mixed, unknown) | High-level filter |
| lineage_primary | string | P2 | Specific playable/species identity within family (high_elf, dark_elf, drow, wood_elf, stormcast_human, duardin, aelf, etc.) | Distinct gameplay / lore role |
| lineage_aliases | array<string> | P2 | Raw tokens that mapped to family or primary | For transparency |
| faction_general | string | P1 | System-agnostic faction/grouping (e.g., chaos, order, death) | High-tier bucket (esp. AoS) |
| faction_path | array<string> | P2 | Ordered hierarchy e.g., [order, stormcast_eternals] | For drill-down UI |
| tabletop_role | enum | P2 | pc_candidate, npc, monster, unit, terrain, vehicle, mount, familiar, summon | Multi-select via separate table if needed |
| pc_candidate_flag | boolean | P1 | Quick boolean for likely player avatar suitability | Heuristic (humanoid + adventurer tokens) |
| human_subtype | enum | P2 | generic_human, warhammer_human, dnd_adventurer_human, historical_human, other | Differentiates human contexts |
| role_confidence | enum | P2 | certain, probable, guess | Manual upgrade |
| lineage_confidence | enum | P1 | certain, probable, guess | Starts low if inferred indirectly |

## 7. Variant Dimensions
| Field | Type | Phase | Description | Notes |
| asset_category | enum | P1 | High-level asset class | miniature (default), terrain, vehicle, foliage, base_set, scatter, accessory_pack, other; conservative auto-detect via tokens else miniature |
| terrain_subtype | enum | P2 | Terrain classification | building, ruin, wall, gate, tower, bridge, platform, scatter, tree, stump, rock, crystal, hill; only if asset_category=terrain |
| vehicle_type | enum | P2 | Vehicle platform | tank, apc, car, truck, halftrack, walker, mech, aircraft, dropship, artillery, boat, submarine, train_locomotive; only if asset_category=vehicle |
| vehicle_era | enum | P2 | Historical / thematic era | ww2, interwar, modern, near_future, scifi, fantasy, dieselpunk, steampunk; derived from tokens (e.g., panzer, sherman -> ww2) |
| base_theme | enum | P2 | Decorative base set environment | urban, desert, snow, tundra, jungle, forest, swamp, industrial, ruined, alien, cavern, ship_deck, volcanic, icy, wasteland |
| intended_use_bucket | enum | P1 | tabletop_intent, display_large, mixed, unknown | From directory context |
| content_flag | enum | P1 | sfw, nsfw | Coarse binary used early (quick filter) |
| nsfw_level | enum | P2 | none, lingerie, topless, bottomless, nude, explicit_act | Granular; `none` mirrors sfw; assigned per variant |
| nsfw_exposure_top | enum | P2 | covered, lingerie, sheer, exposed | Optional finer axis (can defer) |
| nsfw_exposure_bottom | enum | P2 | covered, lingerie, sheer, exposed | Separate from overall level for asymmetric variants |
| nsfw_act_tags | array<string> | P2 | Specific acts (e.g., kiss, fondling, penetration, implied) | Controlled subset; empty if none |
| segmentation | enum | P1 | split, merged, unknown | |
| internal_volume | enum | P1 | solid, hollowed, unknown | |
| support_state | enum | P1 | presupported, supported, unsupported, unknown | |
| has_slicer_project | boolean | P1 | Presence of .lychee, .chitubox, etc. | Not a support proxy |
| pose_variant | string | P2 | pose1, variantB, alt_pose, etc. | Normalized token |
| version_num | integer | P2 | Numeric version extracted (v2, v3) | Separate from pose |
| part_pack_type | enum | P2 | full_model, parts, bust_only, base_only, accessory, upgrade_kit, conversion_bits, weapon_pack, head_swap_pack, clothing_set, decorative_bits | Refined classification for addon packs; legacy values retained |
| has_bust_variant | boolean | P2 | True if both full + bust forms present | |
| scale_ratio_den | integer | P1 | Denominator of ratio 1:den | Accept 4,6,7,9,10,12 etc. |
| height_mm | integer | P1 | Explicit mm size if token present | No inference yet |
| mm_declared_conflict | boolean | P2 | Ratio + mm mismatch flag | Review queue |
| style_primary | enum | P1 | Anatomical style axis (realistic, heroic, anime) | Focuses on proportion realism vs heroic exaggeration vs anime stylization; MUST remain null unless an explicit high-confidence token (e.g., "anime", "bishoujo", "waifu", "heroic_scale", "true scale") is present or manually set; ambiguous borderline anime-realistic hybrids stay null for manual judgment |
| style_primary_confidence | enum | P1 | certain, probable, guess | Mirrors other *_confidence fields; starts guess if inferred by fallback |
| style_aesthetic_tags | array<string> | P2 | Non-anatomical aesthetic descriptors (grimdark, baroque, gothic, biomechanical, ornate, chibi, toon, low_poly, painterly, gritty) | Multi-tag; renamed from style_secondary_tags |
| addon_type | enum | P2 | weapon_swap, armor_panel, decorative, iconography, clothing_set, head_swap, basing_upgrade, pose_rebuilder, alt_turret, magnet_adapter, vehicle_stowage | Functional upgrade role (nullable) |
| requires_base_model | boolean | P2 | True if unusable standalone | Derive from absence of core body parts |
| compatibility_scope | enum | P2 | single_unit, faction_wide, multi_faction, system_wide, generic | Breadth of applicability |
| compatible_units | array<string> | P2 | Canonical unit names targeted (e.g., rhino) | Will become FK list |
| compatible_factions | array<string> | P2 | Factions explicitly referenced | Subset codex_faction |
| multi_faction_flag | boolean | P2 | True if >1 compatible_factions | Derived |
| compatible_model_group_ids | array<UUID> | P2 | Model groups (base bodies) this variant's components are explicitly designed to fit | Preferred over per-variant linkage for stability |
| compatible_variant_ids | array<UUID> | P2 | Specific variant shells/bodies confirmed compatible (fallback when group not yet formed) | Transitional until grouping mature |
| compatibility_assertions | JSON (virtual) | P2 | Expanded structured list: each { target_type: model_group|variant, target_id, fit_type, confidence, evidence_tokens } | Derived from relationship table |
| attachment_points | array<string> | P2 | turret_ring, sponson_left, sponson_right, hull_top, hull_side_left, hull_side_right, head, left_arm, right_arm, backpack, shoulder_left, shoulder_right, base_top | Controlled vocab list |
| replaces_parts | array<string> | P2 | Parts replaced (turret, sponson, head, hatch, weapon) | Review targeting |
| additive_only_flag | boolean | P2 | No original part removal required | Derived |
| clothing_variant_flag | boolean | P2 | Apparel/outfit overlay set | Subset of addon packs |
| magnet_ready_flag | boolean | P2 | Magnet prep tokens present | Heuristic now, geometry later |

## 8. Geometry & Integrity (Future Phases)
| Field | Type | Phase | Description | Notes |
| hash_sha256 | hex string | P3 | File content hash | Dedupe / provenance |
| triangle_count | integer | P3 | Mesh complexity | Requires geometry parse |
| manifold_flag | boolean | P3 | Basic mesh validity | |
| bounding_box_mm | array<float>(3) | P3 | X,Y,Z extents | For scale sanity |
| volume_cc | float | P3 | Print volume | Potential resin calc |
| thin_wall_warnings | array<string> | P4 | Problem areas | From analysis tool |

## 9. Tagging & Classification
| Field | Type | Phase | Description | Notes |
| user_tags | array<string> | P1 | Manual freeform tags | Stored normalized lower |
| auto_tags | array<string> | P4 | ML-suggested tags | Marked unconfirmed until accepted |
| tag_conflicts | array<string> | P4 | Collisions needing review | |

## 10. Audit / Workflow
| Field | Type | Phase | Description | Notes |
| created_at | ISO8601 | P1 | Record creation timestamp | |
| updated_at | ISO8601 | P1 | Last mutation timestamp | |
| review_status | enum | P2 | unreviewed, flagged, confirmed | Human workflow |
| normalization_warnings | array<string> | P1 | e.g., ambiguous_bust, ambiguous_support | Drives review queue |
| confidence_score | float (0-1) | P2 | Aggregate heuristic | Weighted components |
| notes | text | P1 | Freeform user note | |

## 11. Residual / Transparency
| Field | Type | Phase | Description | Notes |
| raw_path_tokens | array<string> | P0 | Tokenized original path segments | Re-process safe |
| residual_tokens | array<string> | P1 | Unclassified tokens post-normalization | Mining for new rules |
| token_version | integer | P1 | Normalization ruleset version applied | Migration aid |

## 12. Archive Entity (Separate Table Concept)
| Field | Type | Phase | Description | Notes |
| archive_id | UUID | P1 | Primary key | |
| rel_path | string | P0 | Path within root | |
| filename | string | P0 | Archive filename | |
| size_bytes | integer | P0 | Raw size | |
| hash_sha256 | hex string | P3 | Hash for integrity / dedupe | Defer until P3 |
| nested_archive_flag | boolean | P2 | True if discovered inside another archive | |
| scan_first_seen_at | ISO8601 | P0 | First inventory detection time | |

## 13. Collection Entity (Separate Table)
| Field | Type | Phase | Description | Notes |
| collection_id | UUID | P2 | Primary key | |
| publisher | string | P2 | Designer / studio | |
| cycle | string (YYYY-MM) | P2 | Month | |
| sequence_number | integer | P2 | Numeric order | |
| theme | string | P2 | e.g., fantasy | |
| original_label | string | P2 | Raw folder name | |

## 14. Character Entity
| Field | Type | Phase | Description | Notes |
| character_id | UUID | P2 | Primary key | |
| name | string | P2 | Canonical | |
| aliases | array<string> | P2 | Alternative spellings | |
| franchise | string | P2 | IP | |
| sub_franchise | string | P2 | Optional | |
| actor_likeness | string | P2 | Actor if applicable | |
| actor_confidence | enum | P2 | certain / probable / stylized / composite | |
| info_url | string (URL) | P2 | External canonical info page (wiki/fandom page) | Optional minimal pointer; no local bio storage |

## 15. Unit Entity (Tabletop)
| Field | Type | Phase | Description | Notes |
| unit_id | UUID | P2 | Primary key | |
| game_system | string | P2 | warhammer_40k etc. | |
| faction | string | P2 | e.g., necrons | |
| unit_name | string | P2 | Official unit name | |
| canonical_base_size_mm | integer | P2 | Standard base | |
| edition_introduced | integer | FUTURE | Rule edition | |
| rules_url | string (URL) | P2 | External link to official/public rules reference for the unit | Optional; pointer only, no rule text stored |

## 16. Relationship Tables (Concepts)
| Table | Fields | Purpose |
|-------|--------|---------|
| model_group_variant | model_group_id, variant_id | Associate variants to group |
| variant_archive | variant_id, archive_id | Multi-archive provenance |
| variant_tag | variant_id, tag | Manual tags many-to-many |
| variant_unit | variant_id, unit_id, proxy_type | Link variant to unit with proxy classification |
| variant_unit_proxy | variant_id, unit_id, proxy_type, proxy_role, confidence, loadout_code, evidence_tokens | Granular per-unit (and optionally per-loadout) proxy assertion rows; supersets simple variant_unit; proxy_role examples: full_alt_sculpt, counts_as, conversion_kit, weapon_swap, upgrade_bits |
| variant_component | variant_id, component_id | Associate a variant file/group providing a reusable component (weapon arm, backpack) |
| component | component_id, code, component_type, attachment_points, replaces_parts, weapon_profile_code | Catalog of discrete parts enabling loadouts |
| unit_loadout | unit_loadout_id, unit_id, loadout_code, required_component_codes[], optional_component_codes[], exclusivity_groups[] | Canonical loadout definition for a unit |
| unit_loadout_requirement | (alt if not array) unit_loadout_id, component_code, requirement_type(required|optional), group_key | Normalized relational form if arrays not stored inline |
| variant_component_supply | variant_id, component_code, supply_scope (self_only|faction_wide|multi_faction|system_wide|generic), confidence | Declares that a variant supplies a component usable for loadout fulfillment |
| variant_component_compatibility | component_variant_id, target_model_group_id (nullable), target_variant_id (nullable), fit_type (exact|near|generic|uncertain), confidence (certain|probable|guess), evidence_tokens[] | Explicit compatibility assertion enabling UI to show which base models this component fits |
| variant_character | variant_id, character_id, likeness_confidence | Link variant to character |
| collection_variant | collection_id, variant_id | Membership in monthly release |

---
## 17. Controlled Vocabularies (Initial Seeds)

These will live in separate small config files later.

- intended_use_bucket: tabletop_intent, display_large, mixed, unknown
- content_flag: sfw, nsfw
// NSFW granularity (introduced P2; `none` implied when content_flag=sfw)
- nsfw_level: none, lingerie, topless, bottomless, nude, explicit_act
- nsfw_exposure_top: covered, lingerie, sheer, exposed
- nsfw_exposure_bottom: covered, lingerie, sheer, exposed
- nsfw_act_tags: (controlled list e.g., kiss, fondling, penetration, implied, other)
- segmentation: split, merged, unknown
- internal_volume: solid, hollowed, unknown
- support_state: presupported, supported, unsupported, unknown
- part_pack_type: full_model, parts, bust_only, base_only, accessory
	- extended (P2): upgrade_kit, conversion_bits, weapon_pack, head_swap_pack, clothing_set, decorative_bits
- proxy_type: official, direct_clone, stylized_proxy, counts_as, kitbash_pack
- lineage_family: elf, human, dwarf, orc, undead, demon, construct, plantfolk, beastfolk, lizardfolk, dragonkin, angelic, aberration, goblin, halfling, giant, vampire, werebeast, slime, skeleton, insectfolk, elemental, fae, mixed, unknown
- lineage_primary (examples across families, non-exhaustive):
	- elf: high_elf, wood_elf, dark_elf, drow, sylvan_elf, sea_elf, desert_elf, moon_elf, sun_elf, generic_elf
	- human: stormcast_human, freeguild_human, dnd_adventurer_human, historical_human, barbarian_human, cleric_human, rogue_human, paladin_human
	- dwarf: mountain_dwarf, duardin, chaos_dwarf, deep_dwarf, hill_dwarf
	- orc: ork, orruk, savage_orc, black_orc, ironjaw_orc
	- undead: vampire, skeleton_warrior, zombie, lich, wight, mummy, ghoul
	- demon: generic_demon, greater_demon, succubus, incubus, imp, balor_like
	- construct: golem_stone, golem_iron, animated_armor, warforged_like, clockwork_construct
	- plantfolk: dryad, treant, spriggan, fungal_creature
	- beastfolk: beastman, minotaur, satyr, faun, centaur, catfolk, foxfolk, ratfolk, kobold (alt: kobolt), lizardfolk, birdfolk, insectfolk_subtypes (antfolk, beetlefolk)
	- dragonkin: dragonborn_generic, half_dragon, drakekin
	- angelic: angel, seraph, deva, archangel
	- aberration: mindflayer_like, beholder_like, tentacle_horror
	- goblin: goblin, hobgoblin, bugbear
	- halfling: lightfoot_halfling, stout_halfling, generic_halfling
	- giant: hill_giant, fire_giant, frost_giant, storm_giant, stone_giant, ogre, troll
	- werebeast: werewolf, werebear, wererat, wereboar
	- slime: ooze, gelatinous_cube, slime_generic
	- skeleton: skeleton_archer, skeleton_knight, skeleton_mage
	- elemental: fire_elemental, water_elemental, earth_elemental, air_elemental
	- fae: pixie, sprite, nymph, fairy, banshee (optionally also undead), eladrin
	- mixed: hybrid_dragon_elf, chimera, multi_species_fusion
	- unknown: placeholder when tokens insufficient

Note: A lineage_primary always belongs to exactly one lineage_family, but some ambiguous creatures (e.g., banshee) may map to a primary under multiple candidate families; in such cases choose the dominant lore classification and add a normalization_warning for review.
- human_subtype: generic_human, warhammer_human, dnd_adventurer_human, historical_human, other
- tabletop_role: pc_candidate, npc, monster, unit, terrain, vehicle, mount, familiar, summon
- addon_type: weapon_swap, armor_panel, decorative, iconography, clothing_set, head_swap, basing_upgrade, pose_rebuilder, alt_turret, magnet_adapter, vehicle_stowage
- compatibility_scope: single_unit, faction_wide, multi_faction, system_wide, generic
- attachment_points: turret_ring, sponson_left, sponson_right, hull_top, hull_side_left, hull_side_right, head, left_arm, right_arm, backpack, shoulder_left, shoulder_right, base_top
- style_primary: realistic, heroic, anime
- style_aesthetic_tags (examples): grimdark, baroque, gothic, biomechanical, organic, ornate, minimalist, gritty, painterly, chibi, toon, low_poly, stylized
- style_primary_confidence: certain, probable, guess
- review_status: unreviewed, flagged, confirmed
- designer_confidence / actor_confidence: certain, probable, stylized (actor only), composite (actor only), guess (designer only)
// Asset categorization (new)
- asset_category: miniature, terrain, vehicle, foliage, base_set, scatter, accessory_pack, other
- terrain_subtype: building, ruin, wall, gate, tower, bridge, platform, scatter, tree, stump, rock, crystal, hill
- vehicle_type: tank, apc, car, truck, halftrack, walker, mech, aircraft, dropship, artillery, boat, submarine, train_locomotive
- vehicle_era: ww2, interwar, modern, near_future, scifi, fantasy, dieselpunk, steampunk
- base_theme: urban, desert, snow, tundra, jungle, forest, swamp, industrial, ruined, alien, cavern, ship_deck, volcanic, icy, wasteland

---
## 18. Introduction Roadmap (High-Level)

- P0: rel_path, filename, extension, size_bytes, depth, is_archive, root_id, raw_path_tokens, scan_batch_id
- P1: designer, intended_use_bucket, basic variant axes (content_flag, segmentation, internal_volume, support_state, scale_ratio_den, height_mm), collection_basic (collection_original_label, collection_cycle, sequence), game_system, codex_faction, residual_tokens, token_version, normalization_warnings
	- (add) asset_category (minimal heuristic); defaults miniature when uncertain
- P2: grouping (model_group_id), franchise/character, proxy_type, codex_unit_name, part_pack_type, pose_variant, version_num, has_bust_variant, loadout_variants, base_size_mm, collection_id linkage, actor_likeness, lineage_subrace, faction_path, tabletop_role, human_subtype, nsfw_level + exposure fields + nsfw_act_tags, confidence fields, review workflow, user_tags, notes
- P3: hashing, geometry metrics, provenance expansion (source_archives), dedupe logic
- P4: auto_tags, thin_wall_warnings, ML confidence scoring refinement
- FUTURE: licensing, rights flags, rule edition, advanced quality analytics

---
## 19. Open Questions (To Refine Later)
- How to assign model_group boundaries automatically vs manual seeding?
- Minimum confidence threshold for auto-creating Character vs requiring manual confirm?
- Strategy for updating derived fields when normalization rules (token_version) change (recompute all vs incremental)?
- Handling potential legal sensitivity of actor likeness (local-only flag vs export suppression)?
- Distinguishing ‘bust’ as variant versus segmentation part in ambiguous sets.
- Clear policy for borderline categories (e.g., transparent lingerie counted as lingerie vs sheer; mapping to nsfw_level).
- Whether explicit_act requires presence of act tags or can be inferred from file/folder naming only.
- Exact heuristics for pc_candidate_flag (humanoid + gear tokens vs explicit unit names) and when to auto-clear for monsters.
- Strategy for mapping system-specific faction terms into lineage_primary (e.g., aelf -> elf, duardin -> dwarf) while keeping original tokens.
- How to formalize addon compatibility confidence scoring (threshold for auto-link vs manual confirm).
- Distinguishing upgrade_kit vs conversion_bits (e.g., replacement vs purely decorative augmentation criteria).
- Policy for multi_faction_flag when factions share chassis naming (avoid false positives).
 - Conservative heuristic order for asset_category (e.g., explicit vehicle tokens before terrain nouns to avoid 'tank_wall' misparse).
 - Handling ambiguous tokens like 'base' in character base vs base_set pack context (need pack-level plural or thematic tokens?).
 - Vehicle era inference fallback when mixed tokens (e.g., scifi + sherman) appear—prefer ww2 or mark conflict?
 - Whether foliage remains separate asset_category or folds into terrain_subtype=foliage; tradeoff between filtering convenience vs taxonomy simplicity.

---
## 20. Change Management
When a field is added or semantics shift:
1. Increment token_version (if normalization impacted).
2. Add entry to `DECISIONS.md` with date + rationale.
3. Provide a lightweight migration note (even if just “backfill null”).

---
## 21. Non-Goals (For Now)
- Automatic watermark / signature removal detection
- Commercial license validation automation
- Full-text OCR of included PDFs
- Automatic actor likeness model inference (manual flag only initially)

---
## 22. Summary
This spec captures the superset of metadata we have discussed. Early phases (P0/P1) stay intentionally small and reliable; later phases enrich without forcing retroactive renames. We will resist adding geometry or ML-derived fields until grouping & manual review workflows stabilize.

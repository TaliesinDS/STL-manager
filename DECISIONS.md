# Decisions

2025-08-15: Created separate repo (STL-manager) to isolate code/planning from blog and avoid large binary history.
2025-08-15: Phase 0 limited to read-only inventory of already extracted files; archives untouched.
2025-08-15: Adopted graded NSFW metadata (nsfw_level + exposure + act tags) to enable nuanced filtering beyond binary content_flag; detailed fields deferred until Phase 2 to avoid premature manual burden.
2025-08-15: Added cross-system lineage/race taxonomy (lineage_primary + subrace + aliases) and tabletop_role / pc_candidate_flag to support filtering (e.g., all elves, DnD adventurer humans vs Warhammer humans) without overfitting early; most advanced facets deferred to P2.
2025-08-15: Refined lineage model to two-tier (lineage_family vs lineage_primary) so distinct elf subtypes (high_elf, wood_elf, dark_elf, drow) remain separate while enabling broad family filters; lineage_primary postponed to P2.
2025-08-15: Expanded lineage_primary examples across all lineage families (not only elves) to ensure specificity (e.g., mountain_dwarf vs chaos_dwarf, ork vs orruk, vampire vs lich) and documented non-exhaustive controlled vocabulary strategy.
2025-08-15: Introduced versioned token normalization map (`tokenmap.md`) covering designer aliases, lineage tokens, faction/family mappings, NSFW cues, variant axis indicators, and confidence / warning rule ordering; baseline declared as token_map_version 1 for Phase 1 rollout.
2025-08-15: Expanded Warhammer 40K & Age of Sigmar faction coverage in token map (added full mainline armies & common aliases, corrected 'adeptus_astartes' typo) and bumped token_map_version to 2 to preserve reproducibility.
2025-08-15: Drafted normalization flow specification (`NormalizationFlow.md`) to formalize deterministic ordering, conflict handling, confidence scoring, and re-run strategy separate from vocabulary content.
2025-08-15: Added addon / upgrade fields (expanded part_pack_type; new addon_type, requires_base_model, compatibility_scope, compatible_units, compatible_factions, multi_faction_flag, attachment_points, replaces_parts, additive_only_flag, clothing_variant_flag, magnet_ready_flag) to support weapon/clothing/conversion packs in Phase 2.

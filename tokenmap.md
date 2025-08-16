# Token Normalization Map (Version 11)

Purpose: Central, versioned mapping of raw path/file tokens -> canonical normalized values used in metadata fields (see `MetadataFields.md`). Keeps heuristic logic transparent and auditable. Phase 1 scope focuses on high-confidence, low-ambiguity mappings only. Ambiguous or low-frequency tokens route to `residual_tokens` + `normalization_warnings`.

Version: 11
Applies to fields first introduced in Phase 1 (designer, intended_use_bucket, basic variant axes, game_system, codex_faction, lineage_family (high-level), pc_candidate_flag proto heuristics, scale basics) and seeds for Phase 2 (lineage_primary examples) for forward compatibility (but Phase 2 tokens flagged if matched early).

---
## 1. Structure

YAML-like conceptual structure (stored here as Markdown for discussion). Future: may externalize into separate small files per domain.

Sections:
1. meta
2. designers
3. lineage
4. factions (system-specific)
5. general_faction (system-agnostic high tier like chaos/order)
6. nsfw_cues (coarse; fine levels only Phase 2)
7. variant_axes (segmentation, internal_volume, support_state, part_pack_type, bust indicators)
8. scale_tokens
9. intended_use
10. role_cues (pc_candidate heuristics seeds)
11. stopwords / noise
12. token_patterns (regex style)
13. precedence (ordering & scoring)

---
## 2. Meta
```
token_map_version: 11
min_token_length: 2
case_sensitive: false
strip_chars: ["(", ")", "[", "]", ",", ";", "{", "}"]
normalize_spaces: true
split_on: ["_", "-", " "]
```

---
## 3. Designers (External Reference)
Designer aliases fully externalized. See `designers_tokenmap.md` (separately versioned) for the canonical list. This main map intentionally excludes designer entries to minimize noise in diffs.

```
designers: external_reference
```

		death_guard: ["death_guard"]
		thousand_sons: ["thousand_son", "thousand_sons", "1ksons"]
		chaos_daemons: ["chaos_daemon", "chaos_daemons", "daemon", "daemons"]
		chaos_knights: ["chaos_knight", "chaos_knights"]
		tyranids: ["tyranid", "tyranids", "nids"]
		genestealer_cults: ["genestealer_cult", "genestealer_cults", "gsc", "genecult"]
		necrons: ["necron", "necrons"]
		orks: ["ork", "orks", "orkan", "greenskin", "greenskins"]
		tau_empire: ["tau", "t'au", "t_au", "tau_empire"]
		kroot: ["kroot", "kroots"]
		aeldari: ["aeldari", "eldar", "craftworld", "craftworlds", "asuriyani"]
		drukhari: ["drukhari", "dark_eldar", "dark-eldar"]
		harlequins: ["harlequin", "harlequins", "harliquin", "harliquins"]
		ynnari: ["ynnari", "yvaine"]
		leagues_of_votann: ["leagues_of_votann", "league_of_votann", "votann", "squats", "leov"]
		grey_knights: ["grey_knight", "grey_knights", "gk"]
		adeptus_titanicus: ["titanicus", "adeptus_titanicus", "titan_legion", "titan_legions"]
		fallen: ["fallen", "the_fallen"]
		black_templars: ["black_templar", "black_templars"]  # chapter example (optional early include)
		blood_angels: ["blood_angel", "blood_angels"]       # chapter example
		ultramarines: ["ultramarine", "ultramarines"]        # chapter example
		space_wolves: ["space_wolf", "space_wolves", "vlka_fenryka"]
		dark_angels: ["dark_angel", "dark_angels"]

	age_of_sigmar:
		stormcast_eternals: ["stormcast", "stormcasts", "stormcast_eternal", "stormcast_eternals"]
		cities_of_sigmar: ["cities_of_sigmar", "city_of_sigmar", "cities", "freeguild", "free_guild"]
		fyreslayers: ["fyreslayer", "fyreslayers"]
		kharadron_overlords: ["kharadron", "kharadrons", "kharadron_overlord", "sky_dwarf", "sky_dwarves"]
		seraphon: ["seraphon", "lizardmen", "lizardman", "saurus"]
		sylvaneth: ["sylvaneth", "sylvan"]
		daughters_of_khaine: ["daughters_of_khaine", "dok", "witch_aelf", "witch_aelves", "witch_elf", "witch_elves"]
		idoneth_deepkin: ["idoneth", "deepkin", "aelf_sea", "sea_aelf"]
		lumineth_realm_lords: ["lumineth", "lumineth_realm_lords", "realm_lords"]
		ossiarch_bonereapers: ["ossiarch", "bonereaper", "bonereapers"]
		soulblight_gravelords: ["soulblight", "gravelords", "soulblight_gravelords"]
		flesh_eater_courts: ["flesh_eater_courts", "flesh_eater_court", "fec", "ghoul_king", "ghoul_kings"]
		nighthaunt: ["nighthaunt", "night_haunt", "night_haunts"]
		blades_of_khorne: ["blades_of_khorne", "khorne", "bloodbound"]
		maggotkin_of_nurgle: ["maggotkin", "maggotkin_of_nurgle", "nurgle"]
		disciples_of_tzeentch: ["disciples_of_tzeentch", "tzeentch"]
		headonites_of_slaanesh: ["hedonites", "hedonites_of_slaanesh", "slaanesh"]
		slaves_to_darkness: ["slaves_to_darkness", "std", "everchosen"]
		beasts_of_chaos: ["beasts_of_chaos", "beast_of_chaos", "beastmen", "beastman"]
		gloomspite_gitz: ["gloomspite_gitz", "gloomspite", "gitz", "moonclan", "squig", "squigs"]
		orruk_warclans: ["orruk_warclans", "orruk", "orruks", "greenskin", "greenskins", "ironjawz", "bonesplitterz", "kruleboyz", "big_waaagh", "waaagh"]
		ogor_mawtribes: ["ogor_mawtribes", "ogor", "ogors", "ogre", "ogres", "mawtribe", "mawtribes"]
		skaven: ["skaven", "skavenblight", "rat", "rats", "ratmen"]
		sons_of_behemat: ["sons_of_behemat", "behemat", "mega_gargant", "gargant", "gargants"]
		kruleboyz: ["kruleboy", "kruleboyz"]  # explicit subset if isolated in names
		ironjawz: ["ironjaw", "ironjawz"]      # explicit subset
		bonesplitterz: ["bonesplitter", "bonesplitterz"]
```

If `game_system` unresolved, faction tokens are ignored (prevent misclassification) but any high-signal rare name (e.g., "Astra Militarum") may still emit `faction_without_system` warning for review.

---
## 5.1 Codex Unit Names (Externalized – P2 Planning)
Phase: Planned (P2). NOT active in Phase 1 normalization. Unit vocabulary moved to external files for modular growth and to minimize core file churn.

External Files:
- `codex_units_w40k.md`
- `codex_units_aos.md`
- `codex_units_oldworld.md`

Sentinel Reference:
```
codex_units: external_reference
```

Activation Criteria (future): Evaluate only when BOTH `game_system` and (where relevant) `codex_faction` resolved. Generic tokens ("tactical", "warrior", "archer") require contextual reinforcement.

Gating Rule: Mapping step runs post faction resolution, pre variant axes, only if `enable_unit_extraction=true` and phase >= P2.

Deferral Rationale: Large, context-sensitive list; externalization allows iterative safe expansion and reduces false positives (e.g., decorative base pack named with generic unit word).

---
## 6. General Faction Buckets
```
general_faction:
	chaos: ["chaos", "khorne", "slaanesh", "nurgle", "tzeentch"]
	order: ["order"]
	death: ["death", "deathrattle", "soulblight"]
	destruction: ["destruction"]
```

---
## 7. NSFW Cues (Phase 1 coarse filtering only)
Phase 1 only sets `content_flag=nsfw` if any strong cue. Fine granularity waits.

```
nsfw_cues:
	strong: ["nude", "naked", "topless", "nsfw", "lewd", "futa"]  # added futa per new content observations
	weak: ["sexy", "pinup", "pin-up", "lingerie"]  # pinup kept weak (broad range); may stay SFW contextually
	exclude_false_positive_context: ["weapon", "nude_color_scheme"]
```

Rule: strong -> nsfw; weak -> nsfw unless conflicting safe context words present (not listed yet) else add warning `nsfw_weak_confidence`.

---
## 8. Variant Axes
```
variant_axes:
	segmentation:
		split: ["split", "parts", "multi-part", "multi_part"]
		merged: ["onepiece", "one_piece", "merged", "solidpiece", "uncut"]  # 'uncut' treated as fully merged/not split
	internal_volume:
		hollowed: ["hollow", "hollowed"]
		solid: ["solid"]
	support_state:
		presupported: ["presupported", "pre-supported", "pre_supported"]
		supported: ["supported"]
		unsupported: ["unsupported", "no_supports", "clean"]
	part_pack_type:
		bust_only: ["bust"]
		base_only: ["base_pack", "bases_only", "base_set"]
		accessory: ["bits", "bitz", "accessories"]
	bust_indicators: ["bust"]
```

Logic: If both segmentation tokens appear (e.g., folder has both 'split' and 'merged') -> set segmentation=unknown + warning `segmentation_conflict`.

---
## 9. Scale Tokens
```
scale_tokens:
	ratio_pattern: "^1[\-_:]([0-9]{1,3})$"  # capture group = denominator
	mm_pattern: "^([0-9]{2,3})mm$"          # 2-3 digit mm height token
	allowed_denominators: [4,6,7,9,10,12]
	suspect_denominators: [5,8,11]
```

If denominator not in allowed list -> warning `uncommon_scale_ratio` (still record). If both ratio + mm with mismatch -> set `mm_declared_conflict=true`.

---
## 10. Intended Use Bucket
Directory path segment heuristics (top-level only considered in Phase 1).

```
intended_use:
	tabletop_intent: ["tabletop", "gaming", "game"]
	display_large: ["display", "showcase", "gallery"]
	mixed: ["mixed"]
```

If multiple buckets triggered -> fallback unknown + warning `intended_use_conflict`.

---
## 11. Role Cues (Proto for pc_candidate_flag)
```
role_cues:
	pc_positive: ["hero", "rogue", "wizard", "fighter", "paladin", "cleric", "barbarian", "ranger", "sorcerer", "warlock", "bard"]
	pc_negative: ["horde", "swarm", "minion", "mob", "unit", "regiment"]
	monster_terms: ["dragon", "troll", "ogre", "beholder", "hydra"]
```

Heuristic (Phase 1 simplified): if any pc_positive and no pc_negative/monster_terms -> pc_candidate_flag=true.

---
## 12. Stopwords / Noise Tokens
Remove before classification; keep in `raw_path_tokens` but exclude from positive matches.

```
stopwords: ["the", "and", "of", "for", "set", "pack", "stl", "model", "models", "mini", "minis", "figure", "figures", "files", "printing", "print"]
```

---
## 13. Token Patterns (Regex)
Patterns applied after basic splitting before alias map lookup.

```
token_patterns:
	version: "^v([0-9]{1,2})$"          # captures version_num
	pose: "^(pose|alt|variant)[-_]?([a-z0-9]{1,3})$"  # pose_variant
```

---
## 14. Precedence & Scoring
Order of operations to reduce false positives:
1. Extract structural patterns (scale, version, pose)
2. Designer aliases
3. System + faction (system before faction)
4. Lineage family (skip if system-specific faction already deterministically implies lineage; e.g., stormcast -> human subtype later)
5. Variant axes (segmentation/internal_volume/support_state)
6. NSFW strong cues
7. Intended use bucket (top-level only)
8. Role cues (derive pc_candidate_flag)
9. Weak NSFW cues (if still SFW)
10. Record residual tokens

Each match increments a confidence accumulator; collisions or conflicting signals decrease it and append warnings.

---
## 15. Warnings Catalog (Referenced by normalization_warnings)
```
warnings:
	designer_alias_collision: Designer token matched more than one alias set
	segmentation_conflict: Both split and merged tokens detected
	intended_use_conflict: Multiple intended use categories triggered
	ambiguous_lineage_token: Token could map to multiple lineage families (held back)
	uncommon_scale_ratio: Ratio denominator outside allowed list
	nsfw_weak_confidence: Only weak NSFW cues present
	faction_without_system: Faction-like token seen but game_system unresolved
	pc_candidate_conflict: Both pc_positive and pc_negative/monster terms present
	scale_mm_ratio_conflict: Both mm and ratio present with mismatch
```

---
## 16. Future Additions (Not in Version 1)
- Detailed lineage_primary activation
- Actor likeness token seeds
- More granular NSFW exposure tokens
- Human subtype disambiguation (stormcast_human etc.)
- Additional monster taxonomy (aberration, construct breakdown)
- Weapon loadout extraction (sword, shield, bow) feeding `loadout_variants`

Added for Version 2 (completed here): Expanded Warhammer 40K & Age of Sigmar faction alias coverage.

Added for Version 3:
- New designers: tinylegend, azerama.
- Lineage family expansions: ratfolk, kobold (high-frequency cross-system species in collection names).
- Future seed (flagged): minotaur (pending decision to treat as lineage vs monster taxonomy in Phase 2).
- Planning notes for tabletop-specific optional fields (equipment_type, pose_index, base_size_mm, base_shape, unit_role) — NOT active mappings yet to avoid overfitting non-tabletop assets.

---
## 19. Planned Tabletop-Specific Field Concepts (Documentation Only; Not Yet Normalized)

These fields are frequently relevant for Warhammer / similar game-system minis but often noise for display sculpts or generic terrain. They remain out of active normalization to prevent misclassification until selective activation criteria (e.g., intended_use=tabletop_intent OR presence of system/faction token) are implemented.

```
tabletop_planned_fields:
	equipment_type: # weapon / gear categories (sword, axe, spear, shield, banner, bolter, flamer, plasma, chainsword, rifle, launcher, cannon, turret)
		status: planned
		activation_condition: game_system resolved OR codex_faction resolved
		strategy: whitelist high-signal tokens; map to enum; capture multiples
	pose_index:
		pattern: ^p(\d{2})$
		status: planned
		notes: Only extract when variant tokens co-occur with obvious unit identifiers
	base_size_mm:
		pattern: ^(25|28|30|32|35|36|40|50|60|75)mm?$
		status: planned
		notes: Distinguish from generic numbers by proximity to 'base' or base shape tokens
	base_shape:
		tokens: ["round", "square", "oval"]
		status: planned
	unit_role:
		tokens_example: ["infantry", "cavalry", "champion", "commander", "knight", "ranger", "marauder", "musician", "banner", "rider", "mount"]
		status: planned
		notes: Some overlap with existing role_cues (pc_candidate heuristics) – integrate later via precedence update
```

Implementation gating: Add only after establishing a two-phase normalization where tabletop-intent classification precedes extraction of tabletop_planned_fields.

---
## 17. Change Policy
When editing this map:
1. Increment `token_map_version`.
2. Add DECISIONS.md entry (date + rationale).
3. Backfill affected records by re-running normalization pipeline with old residual snapshot.

---
## 18. Summary
This version establishes conservative, high-signal mappings to avoid early misclassification while providing scaffolding for richer Phase 2 fields. Ambiguous or low-frequency tokens deliberately flow into residual analysis to iteratively harden the map.


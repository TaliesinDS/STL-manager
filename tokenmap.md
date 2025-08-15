# Token Normalization Map (Version 5)

Purpose: Central, versioned mapping of raw path/file tokens -> canonical normalized values used in metadata fields (see `MetadataFields.md`). Keeps heuristic logic transparent and auditable. Phase 1 scope focuses on high-confidence, low-ambiguity mappings only. Ambiguous or low-frequency tokens route to `residual_tokens` + `normalization_warnings`.

Version: 5
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
token_map_version: 5
min_token_length: 2
case_sensitive: false
strip_chars: ["(", ")", "[", "]", ",", ";", "{", "}"]
normalize_spaces: true
split_on: ["_", "-", " "]
```

---
## 3. Designers (Aliases -> canonical)
Only include high-frequency designers you actually have; others go to residual until observed 2+ times.

```
designers:
	ghamak: ["ghamak", "ghmk", "ghamak_studio"]
	rn_estudio: ["rn_estudio", "rn-estudio", "rnestudio"]
	archvillain: ["archvillain", "arch_villain", "archvillain_games", "avg"]
	puppetswar: ["puppetswar", "puppets_war"]
	tinylegend: ["tinylegend"]
	azerama: ["azerama"]
	hybris_studio: ["hybris", "hybris_studio", "hybrisstudio"]
	pikky_prints: ["pikky", "pikky_prints"]
	warsteel_miniatures: ["warsteel", "warsteel_miniatures", "warsteel_miniaturs", "warsteelminiatures"]
	momoji: ["momoji", "momoji3d", "3dmomoji"]
	moonfigures: ["moonfigures"]
	three_dmoonn: ["3dmoonn"]
	funservicestl: ["funservicestl"]
	miyo_studio: ["miyo", "miyo_studio", "miyo studio"]
	megha: ["megha", "megha_l", "megha l"]  # include observed variant with initial
	kuton: ["kuton"]
	zahen_studio: ["zahen", "zahen_studio", "zahen studio"]
	chuya_factory: ["chuya", "chuya_factory", "chuya factory"]
	kuru_figure: ["kuru", "kuru_figure", "kuru figure"]
	nomnom: ["nomnom"]
	nympha3d: ["nympha3d", "nympha"]
	moxomor: ["moxomor"]
	mezgike: ["mezgike"]
	abe3d: ["abe3d"]
	ca3d: ["ca3d"]
	jigglystix: ["jigglystix"]
	torrida: ["torrida", "torrida_minis", "torrida minis"]
	skarix: ["skarix"]
	xo3d: ["oxo3d", "xo3d", "oxo_3d"]
	rubim: ["rubim"]
	pink_studio: ["pink_studio", "pink studio"]
	dinamuuu3d: ["dinamuuu3d", "dinamuu3d", "dinamuuu3d"]  # minor spelling drift
	zf3d: ["zf3d"]
	gsculpt_art: ["gsculpt", "gsculpt_art", "gsculpt art"]
	aliance: ["aliance"]
	messias3d_figure: ["messias", "messias3d", "messias_3d", "messias 3d", "messias3d_figure", "messias 3d figure"]
	obstetrician_m_booth: ["obstetrician-m.booth", "obstetrician_m_booth", "obstetricianmbooth"]
	vx_labs: ["vx-labs", "vx_labs", "vxlabs"]
	cw_studio: ["cw_studio", "cw studio", "chickenwar", "cw studio (chickenwar)"]
	es_monster: ["e.s.monster", "es_monster", "esmonster"]
	gm3d: ["gm3d"]
	kangyong: ["kangyong", "kang_yong", "kang yong"]
	manilovefigures: ["manilovefigures", "mani_love_figures", "mani love figures"]
	peachfigure: ["peachfigure", "peach_figure", "peach figure"]
	officer_rhu: ["officer-rhu", "officer_rhu", "officerrhu"]
	exclusive3dprinting: ["exclusive3dprinting", "exclusive_3d_printing", "exclusive 3d printing"]
	rushzilla: ["rushzilla"]
	francis_quez: ["francis quez", "francis_quez", "francisquez"]
```

Collision rule: If a token matches aliases for >1 designer (should not in curated list) emit `warning: designer_alias_collision` and push token to residual.

---
## 4. Lineage
High-level Phase 1: lineage_family only. Provide forward-looking primary seeds (flagged future=true) so we don't later reclassify unexpectedly.

```
lineage:
	family_map:
		elf: ["elf", "elves", "aelf", "aelves"]
		human: ["human", "humans", "man", "men"]
		dwarf: ["dwarf", "dwarves", "duardin"]
		orc: ["orc", "orcs", "ork", "orks", "orruk", "orruks"]
		undead: ["undead", "skeleton", "skeletons", "ghoul", "ghouls", "zombie", "zombies", "wight", "wights"]
		demon: ["demon", "daemon", "daemons", "demons"]
		goblin: ["goblin", "goblins", "grot", "grots"]
		halfling: ["halfling", "halflings", "hobbit", "hobbits"]
		lizardfolk: ["lizardfolk", "lizardman", "lizardmen", "saurus"]
		dragonkin: ["dragonborn", "draconian", "draconian", "drake"]
		vampire: ["vampire", "vampires", "vampiric"]
		ratfolk: ["ratfolk", "ratkin", "ratmen"]  # generic rodent lineage outside specific system 'skaven'
		kobold: ["kobold", "kobolds"]
	primary_seeds:  # Phase 2 enable (mark future for now)
		high_elf: { tokens: ["high_elf", "high-elf"], family: elf, future: true }
		dark_elf: { tokens: ["dark_elf", "dark-elf", "drow"], family: elf, future: true }
		wood_elf: { tokens: ["wood_elf", "wood-elf", "sylvan_elf", "sylvan"], family: elf, future: true }
		stormcast_human: { tokens: ["stormcast", "stormcast_eternal", "stormcast_eternals"], family: human, future: true }
		duardin: { tokens: ["duardin"], family: dwarf, future: true }
		minotaur: { tokens: ["minotaur", "minotaurs"], family: ???, future: true }  # decide if separate family or monster taxonomy later
```

Ambiguity examples (not mapped now): "lich", "banshee" (would map to undead later). If encountered -> residual + warning `ambiguous_lineage_token`.

---
## 5. Factions (System Specific)
Separate mapping per game_system. Keys list canonical `codex_faction` (or Battletome faction) and alias array. Coverage aims for current (2025) main armies only; deprecated/legends or micro-subfactions excluded for now (flow to residual for later decision). Aliases include common abbreviations, singular/plural, and frequent spelling variants.

```
factions:
	warhammer_40k:
		space_marines: ["space_marine", "space_marines", "adeptus_astartes", "astartes", "aastartes", "marine", "marines"]
		adepta_sororitas: ["adepta_sororitas", "sisters_of_battle", "sister_of_battle", "sororitas", "sob"]
		adeptus_custodes: ["adeptus_custodes", "custodes", "custodian", "custodians"]
		astra_militarum: ["astra_militarum", "imperial_guard", "guard", "am"]
		adeptus_mechanicus: ["adeptus_mechanicus", "admech", "mechanicus", "skitarii", "cult_mechanicus"]
		agents_of_the_imperium: ["agents_imperium", "inquisition", "ordo_malleus", "ordo_xenos", "ordo_hereticus", "rogue_trader", "assassinorum", "assassin"]
		imperial_knights: ["imperial_knight", "imperial_knights", "ik"]
		chaos_space_marines: ["chaos_space_marine", "chaos_space_marines", "csm"]
		world_eaters: ["world_eater", "world_eaters"]
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
		hedonites_of_slaanesh: ["hedonites", "hedonites_of_slaanesh", "slaanesh"]
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
Only capture explicit ratio (1_10, 1-10, 1:10) or mm values (32mm, 75mm). Do not infer mm from ratio yet.

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


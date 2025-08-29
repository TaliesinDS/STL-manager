# Codex Units Schema and Linking (SSOT Integration)

This document explains how the YAML SSOT (single source of truth) vocab files (e.g., `vocab/codex_units_w40k.yaml`, `codex_units_aos.yaml`, `codex_units_horus_heresy.yaml`) are represented in the database and how scanned model `Variant`s get linked to those units for filtering (e.g., "all Sylvaneth" or "all Grey Knights").

It also covers third-party add-on parts vocabularies (e.g., `vocab/wargear_w40k.yaml`, `vocab/bodies_w40k.yaml`) so the app can show both full 3D models and parts/mods (weapons, shoulder pads, decorative bits, body classes) when viewing a unit.

## Goals
- Normalize the SSOT into relational tables for fast queries and stable IDs
- Preserve YAML structure: system → faction → unit, with aliases, availability, base profile
- Enable many-to-many linking from `Variant` (model) to `Unit` with provenance of how the link happened
 - Model modular parts separately from units and support two result types in the UI: full models and parts/mods

## Tables

### `game_system`
- `id` (PK)
- `key` unique, e.g., `w40k`, `aos`, `heresy`, `old_world`
- `name` display name

Examples:
- (`w40k`, `Warhammer 40,000`)
- (`aos`, `Age of Sigmar`)
- (`heresy`, `Horus Heresy`)

### `faction`
- `id` (PK)
- `system_id` → `game_system.id`
- `key` canonical token, e.g., `adeptus_astartes`, `grey_knights`, `sylvaneth`
- `name`
- `parent_id` self-ref for hierarchies (e.g., Space Marines → Dark Angels chapter)
- `full_path` JSON array of path tokens (optional convenience)
- `aliases` JSON array of known synonym tokens

Notes:
- Hierarchy allows chapter/sub-faction scoping without duplicating units.

### `unit`
- `id` (PK)
- `system_id` → `game_system.id`
- `faction_id` → `faction.id` (nullable for cross-faction/common units)
- `key` canonical snake_case ID from YAML (e.g., `strike_squad`, `custodian_guard`)
- `name` display name
- `role` string (e.g., `HQ`, `Troops`, `Leader`, `Monster`, etc.)
- `unique_flag` bool for named/unique units
- `category` string to support system-specific kinds: `unit` (default), `endless_spell`, `manifestation`, `invocation`, `terrain`, `regiment` (AoS), etc.
- `aliases` JSON array
- `legal_in_editions` JSON array (e.g., `["10e"]`, `["aos4"]`, `["10e","legends_10e"]`)
- `available_to` JSON object (e.g., chapter/subfaction gating)
- `base_profile_key` canonical key to basing profile (matches YAML `base_profile`)
- `attributes` JSON object for extra per-system fields (e.g., `keywords`, `restrictions`, `subfaction`, freeform `notes`)
- `raw_data` JSON snapshot of the entire YAML node for future-proofing and audits (full fidelity)
- `source_file` relative vocab file path
- `source_anchor` optional YAML anchor/path for traceability

### `unit_alias`
- `id` (PK)
- `unit_id` → `unit.id`
- `alias` single alias string (redundant to `unit.aliases`, but indexed for fast lookup)

Rationale: we keep the array on `unit` for round-trip fidelity and also flatten into rows for indexed searches.

### `variant_unit_link`
- `id` (PK)
- `variant_id` → `variant.id`
- `unit_id` → `unit.id`
- `is_primary` bool (a model can proxy multiple units; choose a single primary)
- `match_method` string (e.g., `token`, `manual`, `yaml-guided`)
- `match_confidence` float 0..1
- `notes` freeform
- `created_at`

This association allows your app to ask: "show me all Variants for faction X" by joining Units in that faction to the link table to Variants.

### Parts (Wargear/Bodies/Decor)

Third-party modular parts are modeled as first-class entries so they can be ingested from dedicated vocab files and linked to both units (compatibility) and variants (actual printed parts):

#### `part`
- `id` (PK)
- `system_id` → `game_system.id`
- `faction_id` → `faction.id` (nullable; often faction-scoped for bodies; wargear may be cross-faction)
- `key` canonical snake_case ID (e.g., `bolt_rifle`, `sm_infantry_primaris`)
- `name` display name
- `part_type` string: `wargear` | `body` | `decor` (extensible)
- `category` string: domain-specific category (e.g., `weapon_ranged`, `terminator`, `gravis`)
- `slot` string (singular) for typical placement (e.g., `left_hand`, `backpack`) — mainly for wargear
- `slots` JSON array for multi-slot items (e.g., bodies: `head`, `left_hand`, `backpack`, ...)
- `aliases` JSON array
- `legal_in_editions` JSON array (optional)
- `legends_in_editions` JSON array (optional)
- `available_to` JSON array of faction keys (optional; some wargear is cross-faction)
- `attributes` JSON object for extra fields
- `raw_data` JSON full YAML node snapshot
- `source_file`, `source_anchor`

Connector metadata (lightweight, optional):
- Store connector/fit details inside `part.attributes.connectors` as an array of objects. No migration needed; loader already preserves unknown keys into `attributes`.
- Suggested shape (both for plugs on wargear and sockets on bodies):
	- `role`: `plug` | `socket`
	- `type`: `balljoint` | `peg` | `tab` | `magnet` | `flat`
	- `standard_key`: freeform token, e.g., `titanforge_modular`, `gw_primaris_ball_4mm`, `gw_terminator_shoulder_large`
	- `size_mm`: number (nominal diameter for ball/peg; width for tab)
	- `tolerance_mm`: number (optional; +/- fit guidance)
	- `positions`: array of logical mount points, e.g., `left_shoulder`, `right_shoulder`, `neck`, `backpack`, `waist`
	- `system_keys`: `["w40k", "heresy"]` (optional scope)
	- `fit_class`: `exact` | `near` | `needs_trim` (optional, curator-added)
	- `notes`: string (optional)

Example (wargear, plug):
```
attributes: {
	connectors: [
		{ role: "plug", type: "balljoint", standard_key: "titanforge_modular", size_mm: 4.0, positions: ["right_shoulder"], system_keys: ["w40k","heresy"] }
	]
}
```

Example (body, socket):
```
attributes: {
	connectors: [
		{ role: "socket", type: "balljoint", standard_key: "titanforge_modular", size_mm: 4.0, positions: ["right_shoulder","left_shoulder"] }
	]
}
```

#### `part_alias`
- `id` (PK)
- `part_id` → `part.id`
- `alias` single alias string (flattened for indexed search)

#### `variant_part_link`
- `id` (PK)
- `variant_id` → `variant.id`
- `part_id` → `part.id`
- `is_primary` bool (typically `false` for parts; variants are usually primary models)
- `match_method`, `match_confidence`, `notes`, `created_at`

Purpose: lets the normalizer mark a scanned variant as a part package (e.g., "Ultramarines shoulder pads") and tie it to the canonical `part`.

#### `unit_part_link`
- `id` (PK)
- `unit_id` → `unit.id`
- `part_id` → `part.id`
- `relation_type` string: `compatible` | `recommended` | `required`
- `required_slot` optional slot constraint (e.g., `backpack`, `left_hand`)
- `notes`, `created_at`

Purpose: expresses compatibility or recommendations so the unit detail view can list relevant parts/mods alongside full models.

## Supported YAML Schemas and Sections (Units)

The loader accepts both flat and nested SSOT schemas and adapts per system:

- Warhammer 40,000 (W40K)
	- Root: `codex_units.warhammer_40k`
	- Ingests:
		- Top-level `units`
		- `factions.{faction}.units`
		- Known nested subkeys under a faction: `subfactions`, `chapters`, `orders`, `septs`, `dynasties`, `hives`, `temples`
	- `available_to` can be a dict (chapter-gated) or list (wildcards like `"space_marines/*"`).

- Horus Heresy (30K)
	- Root: `codex_units.warhammer_30k`
	- Ingests:
		- Top-level `units`
		- `factions` including a `legions` subkey (recognized like other nested subkeys)
	- Factions are upserted even if they don’t list `units` directly (to preserve hierarchy).

- Age of Sigmar (AoS)
	- Root: `codex_units.age_of_sigmar`
	- Ingests:
		- `grand_alliances.{GA}.factions.{faction}.unit_types.{leaders|battleline|...}`
			(both dict- and list-style entries are supported; list entries derive `name`, `role`, and `legal_in_editions` from `meta.editions`)
		- Faction-level special sections (imported as `unit` rows with `category`):
			- `endless_spells` → `endless_spell`
			- `manifestations` → `manifestation`
			- `invocations` → `invocation`
			- `warscroll_terrain` → `terrain`
		- Top-level shared sections (cross-faction; no `faction_id`):
			- `shared_endless_spells` → `endless_spell`
			- `regiments_of_renown` → `regiment`
			- `shared_manifestations` → `manifestation`
			- `shared_invocations` → `invocation`
			- `shared_terrain` → `terrain`

Notes:
- Every ingested unit preserves the full YAML node in `unit.raw_data` and non-core fields in `unit.attributes`.
- `unit_alias` rows are rebuilt on each run based on `unit.aliases`.

## Minimal Loader Flow
1. Parse YAML (ruamel.yaml already in requirements).
2. Upsert `game_system` rows for `w40k`, `aos`, `heresy`, `old_world` (if used).
3. Units manifests:
	- Detect schema branch: nested under `codex_units.<system_branch>` (preferred) or flat with top-level `factions`/`units`.
	- Upsert `faction` hierarchy from `factions` (including nested `subfactions/chapters/orders/septs/dynasties/hives/temples/legions`).
	- AoS: traverse `grand_alliances → factions → unit_types` and ingest entries; include faction-level and top-level special sections as `unit` rows with appropriate `category`.
	- Upsert `unit` rows (store `attributes` + `raw_data`) and rebuild `unit_alias` rows.
4. If the file is a parts manifest:
	- `wargear_w40k.yaml`: iterate `wargear:` mapping → upsert `part` with `part_type = 'wargear'`, `category`, `slot`, `aliases`, `available_to`, and snapshots
	- `bodies_w40k.yaml`: iterate `bodies:` mapping → upsert `part` with `part_type = 'body'`, `category` from `class`, `slots`, `aliases`; ensure faction rows exist for `faction:` keys
	- Rebuild `part_alias` rows
5. Later, add rules or manual UI actions to populate `unit_part_link`; the normalizer can also populate `variant_part_link` when a scanned variant is a parts pack.

Upsert keys:
- `game_system.key`
- `(faction.system_id, faction.key)`
- `(unit.system_id, unit.key)`

## Linking Variants to Units
- Automatic: your existing matcher can emit `(variant_id, unit_key, system_key, confidence)` when it finds a strong match. Resolve `system_id` and `unit_id` to insert `variant_unit_link`.
- Manual: UI can let you search Units by `name`/`alias` and add a link.
- Multiple links: allowed; set one `is_primary = true` if needed.

## Linking Variants to Parts
- Automatic: the matcher can recognize tokens like `shoulder`, `pauldron`, `bolt_rifle`, etc., then insert `(variant_id, part_key)` into `variant_part_link` with `match_method = 'token'` or similar.
- Manual: UI flow to search `Part` by `name`/`alias` and add a link for ambiguous packs.
 - Connector-aware inference (future): intersect `plug` on wargear with compatible `socket` on a body by `standard_key`/`type`/`size_mm` to surface likely fits; store explicit assertions in `unit_part_link` or a future `compatibility` table.

## Linking Units to Parts
- Seed compatibility tables via curated rules (e.g., Space Marine Intercessors → `bolt_rifle`, `power_pack`, `pauldron_left_*`, purity seals).
- Or compute compatibility on the fly by intersecting `unit.faction_id` (and subfaction/chapter) with `part.available_to` and matching `slot`/`category` semantics.

## Example Queries

All Grey Knights units and their linked model counts:
```
SELECT u.name, COUNT(vul.variant_id) AS model_count
FROM unit u
JOIN faction f ON u.faction_id = f.id
JOIN game_system s ON u.system_id = s.id
LEFT JOIN variant_unit_link vul ON vul.unit_id = u.id
WHERE s.key = 'w40k' AND f.key = 'grey_knights'
GROUP BY u.id
ORDER BY u.name;
```

All Variants that match any Sylvaneth unit:
```
SELECT v.*
FROM variant v
JOIN variant_unit_link vul ON vul.variant_id = v.id
JOIN unit u ON u.id = vul.unit_id
JOIN faction f ON u.faction_id = f.id
JOIN game_system s ON u.system_id = s.id
WHERE s.key = 'aos' AND f.key = 'sylvaneth';
```

All “spell-like” things for a faction (Endless Spells, Manifestations, Invocations):
```
SELECT u.*
FROM unit u
JOIN faction f ON u.faction_id = f.id
JOIN game_system s ON u.system_id = s.id
WHERE s.key = 'aos'
	AND f.key = 'sylvaneth'
	AND u.category IN ('endless_spell','manifestation','invocation');
```

All terrain for a faction:
```
SELECT u.*
FROM unit u
JOIN faction f ON u.faction_id = f.id
JOIN game_system s ON u.system_id = s.id
WHERE s.key = 'aos' AND f.key = 'nighthaunt' AND u.category = 'terrain';
```

All “spell-like” things across AoS (any faction + shared):
```
SELECT u.*
FROM unit u
JOIN game_system s ON u.system_id = s.id
WHERE s.key = 'aos' AND u.category IN ('endless_spell','manifestation','invocation');

Parts for a specific unit (explicit links):
```
SELECT p.*
FROM part p
JOIN unit_part_link upl ON upl.part_id = p.id
JOIN unit u ON u.id = upl.unit_id
JOIN game_system s ON u.system_id = s.id
WHERE s.key = 'w40k' AND u.key = 'intercessors';
```

All Space Marine wargear parts (by faction or available_to):
```
SELECT p.*
FROM part p
JOIN game_system s ON p.system_id = s.id
LEFT JOIN faction f ON p.faction_id = f.id
WHERE s.key = 'w40k' AND (
	(f.key = 'space_marines') OR JSON_EXTRACT(p.available_to, '$') LIKE '%space_marines%'
);
```

Variants that are parts packs (e.g., shoulder pads), with the canonical part:
```
SELECT v.rel_path, v.filename, p.name AS part_name
FROM variant v
JOIN variant_part_link vpl ON vpl.variant_id = v.id
JOIN part p ON p.id = vpl.part_id
JOIN game_system s ON p.system_id = s.id
WHERE s.key = 'w40k';
```
```

## Why not store the YAML blobs as-is in the DB?
- We want normalized, queryable entities for fast filters, joins, and referential integrity.
- We also store `raw_data` (the full YAML node) plus `attributes` (non-core fields) so 100% of the YAML is preserved without exploding the schema into per-system tables. You can always rehydrate or migrate later.
- We keep provenance (`source_file`, `source_anchor`) to trace back to YAML. The YAML files remain the SSOT; the DB is an index for querying.

## Migration Strategy
- Alembic revision: create new tables without touching existing Variant/File tables.
- Add a simple loader script `scripts/load_codex_from_yaml.py` that supports `--system w40k --file vocab/codex_units_w40k.yaml --dry-run/--commit`.
- Update the matcher to optionally emit `variant_unit_link` rows.

## UI Notes
- Sidebar: choose `GameSystem` (40K / AoS / Heresy).
- Then `Faction` tree (supports sub-factions/chapters).
- Unit list with counts and filters (role, edition legality, base profile).
- When viewing a unit: show two panes
	- Full models: linked Variants (via `variant_unit_link`)
	- Parts/Mods: compatible parts (via `unit_part_link`, or inferred by `available_to` + slot/category)
	Provide quick open to file path and tag actions to link/delink parts or models.

## Edge Cases
- Cross-faction units: keep `faction_id = NULL` and gate with `available_to` JSON (e.g., chapters) as in YAML; your UI can resolve eligibility based on the user’s selected subfaction.
- Subfactions/chapters/temples/septs: represented structurally under `faction` (as children) when you define them, and also mirrored in `unit.available_to` or `unit.attributes.subfaction` for unit-level gating. Either allows filtering (“Units available to Sept X”) without duplicating units.
- Renames/ID changes in YAML: keep `unit.key` stable; if a rename occurs, create a new Unit row and optionally a redirect link for historical mapping.
- Duplicates from YAML: dedupe by `(system_id, key)`; merge aliases.
 - Parts vocab is intentionally 40K-first; Horus Heresy compatibility can be layered in later by setting `system_id = 'heresy'` or cross-listing where appropriate.

## Success Criteria
- You can filter "all Grey Knights" or "all Sylvaneth" and see linked models.
- Loader runs idempotently; re-running on updated YAML updates/creates Units without duplicates.
- Existing tests remain green; add later tests for basic loader/link queries.
 - For a unit, the UI returns both full models and relevant parts; parts vocab for wargear/bodies ingests cleanly and can be linked to both units and variants.

## Loader CLI Usage

Basic examples (PowerShell on Windows):

```powershell
$env:STLMGR_DB_URL = 'sqlite:///./data/stl_manager_v1.db'

# Load 40K units
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\codex_units_w40k.yaml --commit

# Load Age of Sigmar units (schema under codex_units.age_of_sigmar)
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\codex_units_aos.yaml --system aos --commit

# Load Horus Heresy units (schema under codex_units.warhammer_30k)
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\codex_units_horus_heresy.yaml --system heresy --commit

# Load 40K parts (wargear, bodies)
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\wargear_w40k.yaml --commit
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\bodies_w40k.yaml --commit
```

Flags:
- `--system {w40k|aos|heresy|old_world}`: optional override when file name inference is ambiguous.
- `--commit`: apply changes (omit for a dry-run; the loader will rollback after validation).
- `--db-url`: explicit SQLAlchemy URL; defaults to `STLMGR_DB_URL` or `sqlite:///./data/stl_manager.db`.

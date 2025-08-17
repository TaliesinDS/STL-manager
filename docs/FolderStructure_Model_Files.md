# Tabletop & Display Folder Structure (Warhammer + Non-Warhammer) (Draft)

Date: 2025-08-17
Status: Draft (merged Warhammer + generic structures) – refine as ingestion scripts mature.
Scope: Canonical on-disk taxonomy for tabletop-oriented minis (Warhammer + other systems + generic) and pure display pieces; aims for deterministic parsing & normalization.

---
## 1. High-Level Goals
- Make paths semantically meaningful without needing to open files.
- Keep optional layers (e.g., grand alliance) skippable while still parseable.
- Separate provenance/source variant (scan, direct proxy, etc.) from unit identity.
- Provide a uniform README.json metadata contract.
- Allow future migration to DB-backed indexing with minimal path churn.

---
## 2. Unified Top-Level Directories
```
/tabletop
  /warhammer
  /other_games
  /generic
  /shared_assets
  /_ingest_queue
/display
/reference_only
```
Optional future: `/archive_deprecated`, `/kitbash_workspace`.

### 2.1 Why this split?
- `warhammer` isolates GW ecosystems (different taxonomy, factions).
- `other_games` houses named external rulesets (Infinity, Malifaux, Frostgrave, etc.).
- `generic` keeps system-agnostic sculpts categorized by genre rather than forcing a fictional system.
- `shared_assets` centralizes reusable bases/bits to avoid duplication.
- `_ingest_queue` staging area the validator can scan & propose canonical moves for.

---
## 3. Warhammer Substructure
```
/tabletop/warhammer/
  aos/<grand_alliance>/<faction>/<subfaction?>/<unit>/<source_variant>/
  40k/<faction>/<subfaction?>/<unit>/<source_variant>/
  horus_heresy/<legion>/<unit>/<source_variant>/
  old_world/<faction>/<unit>/<source_variant>/
  necromunda/<gang>/<unit_or_role>/<source_variant>/
  blood_bowl/<team>/<position?>/<source_variant>/
  kill_team/<faction>/<kill_team_name?>/<unit>/<source_variant>/
```
Definitions:
- **grand_alliance** (AoS only): order, chaos, death, destruction (lowercase).
- **faction**: e.g., nighthaunt, space_marines, tyranids.
- **subfaction** (optional): e.g., emerald_host, black_templars.
- **legion** (Horus Heresy): e.g., imperial_fists.
- **unit**: canonical unit name slug (dreadblade_harrows).
- **source_variant**: SEE Section 7 (scan / direct_proxy / close_proxy / kitbash / original).

Example mapping of existing path:
```
G:\3d models organised\32mm\_GW\Age of Sigmar\Death\Nighthaunt\_sorted\Dreadblade Harrows
→ /tabletop/warhammer/aos/death/nighthaunt/dreadblade_harrows/direct_proxy/
```
If subfaction absent:
```
/tabletop/warhammer/40k/tyranids/termagants/original/
```

---
## 4. Other Games Substructure
```
/tabletop/other_games/<system>/<faction_or_line?>/<unit_or_model>/<source_variant>/
```
- **system**: infinity, malifaux, frostgrave, stargrave, bushido, etc.
- **faction_or_line**: nomads, guild, generic, etc. (omit if not meaningful).
- **unit_or_model**: model slug.

Examples:
```
/tabletop/other_games/infinity/nomads/zero_hacker/direct_proxy/
/tabletop/other_games/malifaux/guild/death_marshal/close_proxy/
```

---
## 5. Generic Tabletop Substructure
```
/tabletop/generic/<genre>/<category>/<model_package>/<source_variant>/
```
Field vocabulary:
- **genre**: fantasy, scifi, historical, modern, post_apocalyptic, steampunk.
- **category**: infantry, hero, monster, vehicle, cavalry, terrain, objective, accessory.
- **model_package**: designer + model slug (see naming).

Examples:
```
/tabletop/generic/fantasy/hero/artisan_guild__elven_ranger/direct_proxy/
/tabletop/generic/scifi/terrain/designer_y__forest_ruins_set_a/original/
```

---
## 6. Display Pieces
```
/display/<form>/<genre>/<designer?>/<piece_name>/
```
- **form**: bust, full_figure, diorama, statue, prop, relief.
- **genre**: same set as tabletop genres (extend as needed).
- **designer**: only if grouping multiple pieces makes navigation easier.
- **piece_name**: slug.

Examples:
```
/display/bust/historical/designer_z/napoleonic_grenadier_v1/
/display/diorama/fantasy/forest_ambush_v1/
```
(Optionally still use source_variant subfolders if multiple forms like raw vs painted scans.)

---
## 7. Source Variant Layer
Permitted subfolder names under a unit/model:
```
scan/          # 3D scanned official kit (personal archival)
direct_proxy/  # Intended 1:1 representation of official unit
close_proxy/   # Functionally usable, stylistic differences
kitbash/       # Combined parts from multiple sources
original/      # Completely original sculpt (non-proxy)
alt_pose/      # Optional for alternate official-style poses
```
Only create folders that exist; keep unit root uncluttered.

---
## 8. Internal Layout Within Source Variant
```
<source_variant>/
  raw_parts/        (vendor or base STLs)
  pre_supported/    (if distinct from raw)
  hollowed/         (resin-saving versions)
  merged/           (combined or keyed)
  slicer_files/     (.lychee, .3mf, .ctb)
  docs/             (renders, license, changelog)
  README.json       (metadata)
```
Subfolders optional; omit unused ones.

---
## 9. Naming Conventions (Files)
```
<primary_slug>__<descriptor?>__v<Major>[ _revX][ _pose-<Code>][ _scale-<mm_or_ratio>].stl
```
Where **primary_slug** for Warhammer is `<unit>`; for generic or display it can be `<designer>__<model_name>` if you prefer designer context.
Rules:
- Double underscores separate high-level semantic tokens.
- Increment `v<Major>` on geometry changes (not support tweaks).
- Append `_revA/B` for support or minor mesh adjustments.
- Poses: `_pose-A`, `_pose-bow`.
- Scale: `_scale-32mm` or `_scale-1_10`.

Examples:
```
dreadblade_harrows__mounted_leader__v1.stl
artisan_guild__elven_ranger__v1_scale-32mm.stl
napoleonic_grenadier_bust__v1_revA.stl
```

---
## 10. README.json Metadata (Unit / Piece Root)
### 10.1 Warhammer Example
```json
{
  "system": "warhammer_aos",
  "grand_alliance": "death",
  "faction": "nighthaunt",
  "subfaction": "emerald_host",
  "unit": "dreadblade_harrows",
  "source_type": "direct_proxy",
  "designer": "scan",
  "license": "personal use",
  "tags": ["cavalry","spectral","hero"],
  "version": 1
}
```
### 10.2 Generic / Other Games Example
```json
{
  "system": "infinity",
  "faction": "nomads",
  "unit": "zero_hacker",
  "source_type": "close_proxy",
  "designer": "Indie Sculptor",
  "genre": "scifi",
  "category": "infantry",
  "tags": ["hacker","stealth"],
  "license": "personal use",
  "version": 2
}
```
### 10.3 Display Example
```json
{
  "form": "bust",
  "genre": "historical",
  "piece_name": "napoleonic_grenadier",
  "designer": "Designer Z",
  "source_type": "original",
  "scale_mm": 75,
  "tags": ["napoleonic","infantry"],
  "version": 1
}
```
Validation considerations:
- Require minimal keys per context (system+unit OR form+piece_name).
- Maintain JSON Schema with conditional requirements.
- Compute a stable content hash for change detection.

---
## 11. Deterministic Parsing Rules
- Split path after `/tabletop/warhammer` vs `/tabletop/other_games` vs `/tabletop/generic` to enter distinct extractors.
- Allow optional segments (subfaction) by pattern length; fill absent fields with `null` in normalized output.
- Source variant recognized by membership in allowed set (Section 7).
- File tokenization: split on `__`, parse trailing `_pose-`, `_scale-`, `_revX` patterns.

---
## 12. Future Extensions
| Need | Extension | Notes |
|------|-----------|-------|
| Multi-scale variants | `scale-XXmm` suffix or `scales/<size>/` subdir | Prefer suffix for simplicity |
| Kitbashes metadata | Add `kitbash_sources` array in README.json | List component designers/units |
| Licensing tracking | `license_file` pointing to `docs/license.txt` | Copy vendor license text |
| Paint schemes | Add `paint_refs/` under source_variant | Non-essential to normalization |
| Multi-material prints | `materials/` subdir | Rare for STL; defer |

---
## 13. Quick Start Checklist
1. Create top-level directories (Section 2).
2. For each existing Warhammer path, map & move into canonical pattern (record mapping log).
3. Create source variant subfolders and classify existing files.
4. Add README.json per unit/model with minimal required fields.
5. Standardize file names to naming convention (Section 9).
6. (Later) Run validator script to flag deviations.

---
## 14. Open Questions
- Should we always include scale (default 32mm) for uniformity? (Current: optional.)
- Enforce lowercase snake_case everywhere? (Recommendation: yes.)
- Represent kitbashes: prefix with `kitbash__` or just source_type = kitbash + README sources? (Leaning latter.)
- Need separate layer for base size? Possibly encode in README only to avoid path churn.

---
*End of Merged Draft*  

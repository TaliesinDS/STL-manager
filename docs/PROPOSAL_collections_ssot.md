# Proposal: SSOT and Workflow for Designer Collections (Populating Variant.collection_*)

This document proposes how we will populate and maintain the Variant collection fields — `collection_id`, `collection_original_label`, `collection_cycle`, `collection_sequence_number`, and `collection_theme` — using a small, explicit SSOT (single source of truth) YAML per designer and a deterministic matcher.

## Goals
- Normalize designer monthly/thematic releases into a stable, queryable structure.
- Populate Variant.collection_* fields reliably with dry-run safety and auditability.
- Keep source data human-editable (YAML in-repo) and provenance-linked to public product pages.

## Target columns (contract)
- `variant.collection_id` (string, stable slug): canonical key for the release (e.g., `dm_stash__2021_09_guardians_of_the_fey`).
- `variant.collection_original_label` (string): raw token that triggered the match (path snippet or alias used).
- `variant.collection_cycle` (string, usually `YYYY-MM`): normalized cycle extracted from SSOT (or tokens when confident).
- `variant.collection_sequence_number` (int, optional): parsed order number within that release (e.g., `01`, `1`).
- `variant.collection_theme` (string): controlled-ish theme key (e.g., `fey`, `desert_raiders`, `grimdark_sci_fi`).

A minimal `collection` table row will mirror the canonical facts (publisher, cycle, theme) and provide a place for provenance fields in later phases.

## SSOT format (YAML)
Location: `vocab/collections/<designer_key>.yaml`

Schema (proposed v1):
```yaml
# vocab/collections/dm_stash.yaml
version: 1
publisher: myminifactory   # primary platform for these entries (optional)

designer_key: dm_stash
collections:
  - id: dm_stash__2021_09_guardians_of_the_fey   # stable slug used as variant.collection_id
    name: "Guardians of the Fey"
    cycle: "2021-09"          # normalized year-month
    theme: fey                 # controlled-ish key; keep small and practical
    publisher: myminifactory   # optional override per collection
    release_date: "2021-09-01" # ISO (approx is fine if only month known)
    source_urls:               # provenance
      - https://www.myminifactory.com/users/DM-Stash/collection/guardians-of-the-fey
    aliases:                   # strings we expect to see in folders/archives
      - Guardians of the Fey
      - DM Stash September 2021 Release
      - September 2021
    match:
      # Case-insensitive regexes; must be conservative; evaluated near the variant root
      path_patterns:
        - "(?i)guardians[-_ ]of[-_ ]the[-_ ]fey"
      # Candidate patterns to extract sequence numbers from filenames/folders
      sequence_number_regex:
        - "^(\\d{1,2})[._ -]"       # 01_FairyKnight.stl
        - "[ _-](\\d{1,2})[ _-]"    # Fairy 02 Archer
```

Notes:
- `id` is the stable slug. Keep it deterministic: `<designer_key>__<YYYY_MM>_<normalized_title>`.
- `aliases` should remain specific to avoid false positives.
- `match.path_patterns` should prefer the explicit title over generic words (e.g., `fey` alone is too weak).
- `sequence_number_regex` is a list; we’ll take the first capturing group that matches.

## Matching strategy (deterministic first, then conservative heuristics)
1. Precondition: Variant must have `designer` normalized to a `designer_key` (via existing designers token map).
2. Deterministic match (preferred):
   - If any `match.path_patterns` for a collection under this `designer_key` matches the Variant `rel_path` (within top N segments), select that collection.
   - Set fields:
     - `collection_id` = collection `id` from YAML
     - `collection_original_label` = the exact substring (or alias) that triggered the match
     - `collection_cycle` = YAML `cycle`
     - `collection_theme` = YAML `theme`
     - `collection_sequence_number` = first number captured by any `sequence_number_regex` against `filename` or folder name (optional)
3. Conservative heuristic (fallback, optional):
   - If no pattern match, but `aliases` include an exact phrase present in the path (case-insensitive) AND designer matches, accept with lower confidence.
   - We can record a normalization warning when falling back to aliases without a regex pattern.
4. No match: leave fields null. We’ll emit a review candidate in the dry-run report.

Scope control:
- Only match within the designer’s namespace (do not match across designers).
- Search within the last 3–4 path segments by default to avoid ambient matches from deep nesting.
- Ignore files/folders recognized as junk (e.g., `presupported`, `previews`, `textures`, `lychee/chi*` projects) unless `sequence_number_regex` extraction needs the filename.

## Loader + matcher workflow
We’ll follow the same pattern as units/parts loaders: dry-run by default, explicit `--apply` to commit.

Tools to implement (names aligned with existing conventions):
- `scripts/20_loaders/load_collections.py`
  - Input: one or more `vocab/collections/*.yaml`
  - Behavior: upsert rows into `collection` table (by `id` slug), store core columns (`original_label` can mirror `name` for now), `publisher`, `cycle`, `sequence_number` (null at collection-level unless the designer publishes an overall sequence), `theme`, and stash the full YAML node in a `raw_data` JSON column if/when we add it (Phase 2). For Phase 1 we can limit to existing columns.
- `scripts/match_collections.py`
  - Input: DB URL and optional scope flags (by designer, by root)
  - Behavior: scan Variants with `designer` set; apply the matching strategy; write updates to `variant.collection_*` fields. Support `--dry-run` and `--apply` and JSON report export like the existing matchers.

Example dry-run commands (PowerShell-safe; scripts to be implemented):
```powershell
# Load DM Stash collections (dry-run)
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_collections.py `
  --file .\vocab\collections\dm_stash.yaml `
  --db-url sqlite:///./data/stl_manager_v1.db

# Match variants to collections (dry-run)
.\.venv\Scripts\python.exe .\scripts\match_collections.py `
  --db-url sqlite:///./data/stl_manager_v1.db `
  --designer dm_stash `
  --out ("reports/match_collections_dm_stash_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

## Minimal DB changes (optional Phase 2)
The current `collection` model is intentionally light. If/when needed, we can extend it:
- Add `key` (slug, unique), `designer` (string), `aliases` (JSON), `source_urls` (JSON), `release_date` (Date), and `raw_data` (JSON).
- Optionally, add a `collection_alias` table for fast alias search (mirrors `unit_alias`).

This can be staged without breaking the Variant fields contract. Phase 1 works with current columns by upserting with `original_label` = `name` and tracking richer metadata in SSOT YAML only.

## Data governance
- Source of truth lives in `vocab/collections/` per designer file.
- Keep aliases and regex patterns conservative; prefer specificity over recall.
- Every collection entry must include at least one public `source_urls` link (e.g., MyMiniFactory, Patreon post) for provenance.
- Use slugging rules for `id`:
  - Lowercase, ASCII, snake_case.
  - `<designer_key>__<YYYY_MM>_<normalized_title>` with non-word chars replaced by `_` and sequences collapsed.

## Example: DM Stash “Guardians of the Fey” (September 2021)
The official page: https://www.myminifactory.com/users/DM-Stash/collection/guardians-of-the-fey (12 objects; “DM Stash September 2021 Release”).

Proposed YAML entry is already included above under `dm_stash.yaml`. With that present, any Variant under DM Stash whose path contains a phrase matching `guardians[-_ ]of[-_ ]the[-_ ]fey` near the leaf will be assigned:
- `collection_id = dm_stash__2021_09_guardians_of_the_fey`
- `collection_original_label =` the matched label/substring
- `collection_cycle = 2021-09`
- `collection_sequence_number =` first number parsed from file/folder (if present)
- `collection_theme = fey`

## Edge cases and guardrails
- Re-releases/remasters: add a separate entry with a different `id` (e.g., `...__2024_03_guardians_of_the_fey_remastered`) and distinct `path_patterns`.
- Bundles that aggregate past releases: do not auto-match unless an explicit past collection title appears; otherwise leave null.
- Generic names (e.g., “guardians” alone): avoid using as an alias; require full phrase or designer-scoped context.
- Multiple designers in a shared folder: rely on `designer` normalization first; never cross-match.
- Welcome packs / evergreen content: add a special `cycle` (e.g., ` evergreen`) or leave cycle null and rely on `id` and `aliases`.

## Success criteria
- Dry-run report shows high-precision matches with negligible false positives.
- Variants from the same release share the same `collection_id`.
- Filters by `collection_id` and `collection_cycle` return consistent sets.
- Minimal manual curation after initial YAML population per designer.

## Rollout plan
1. Approve this SSOT schema (no code changes required yet).
2. Add `vocab/collections/dm_stash.yaml` with the entry above and 1–2 more recent DM Stash releases for coverage.
3. Implement `load_collections.py` and `match_collections.py` with dry-run first.
4. Run dry-run on your `sample_store` scope; review JSON report; iterate on aliases/patterns.
5. Apply; then add other designers (Printable Scenery, Cast n Play, etc.).

---

Short-term alternative (no loader yet):
- Parse `collection_cycle` and `collection_original_label` directly from folder names and leave `collection_id`/`collection_theme` null unless a very precise token exists. This yields partial utility but lacks stability across reorganizations and won’t support filtering by a canonical release.

Recommended path is the SSOT YAML + matcher above for stability, auditability, and ease of future UI filters.

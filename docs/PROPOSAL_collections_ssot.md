# Proposal: SSOT and Workflow for Designer Collections (Populating Variant.collection_*)

This document proposes how we will populate and maintain the Variant collection fields — `collection_id`, `collection_original_label`, `collection_cycle`, `collection_sequence_number`, and `collection_theme` — using a small, explicit SSOT (single source of truth) YAML per designer and a deterministic matcher. This workflow now incorporates our MyMiniFactory (MMF) collection auto-seeding and cleanup tools.

Status update (2025-09-03)
- MMF cleanup and updater scripts are available; designer-scoped YAML manifests under `vocab/collections/` can be matched to populate `variant.collection_*` fields. Draft proposer exists for missing collections.

## Goals
- Normalize designer monthly/thematic releases into a stable, queryable structure.
- Populate Variant.collection_* fields automatically after designer recognition (e.g., when var 340 is recognized as a Heroes Infinite model, its collection should be identified and the collection columns filled in).
- Preserve dry-run safety and auditability.
- Keep source data human-editable (YAML in-repo) and provenance-linked to public pages (MMF, Patreon, etc.).

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
- `id` is the stable slug. Keep it deterministic: `<designer_key>__<YYYY_MM>_<normalized_title>`. If cycle is unknown, allow `<designer_key>__<normalized_title>` (cycle can be added later without changing semantics).
- `aliases` should remain specific to avoid false positives.
- `match.path_patterns` should prefer the explicit title over generic words (e.g., `fey` alone is too weak).
- `sequence_number_regex` is a list; we’ll take the first capturing group that matches.

Auto-seeding from MMF (Phase 1)
- Use `scripts/10_integrations/update_collections_from_mmf.py` to append the latest N collections for a designer into its YAML file. Entries include `name`, `theme` (slugified from the title), `cycle` when parseable from the title, and `source_urls` pointing to the user’s collections.
- The script uses `vocab/mmf_usernames.json` to map `designer_key -> mmf_username` and only accepts URLs rooted at that username, preventing global/non-designer leaks. A companion cleaner `scripts/maintenance/cleanup_mmf_collections.py` removes any non-matching entries.

## Matching strategy (designer-scoped; deterministic first, then conservative heuristics)
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

MMF-derived pragmatic fallback (optional, Phase 1 safe):
- For designers with MMF-seeded entries (no explicit `match.path_patterns` yet), allow a conservative alias-only match using the MMF `name` as an alias when that name is sufficiently distinctive and appears near the variant leaf.
- This is designer-scoped (never cross-designer) and should still prefer explicit `match.path_patterns` when present.

Scope control:
- Only match within the designer’s namespace (do not match across designers).
- Search within the last 3–4 path segments by default to avoid ambient matches from deep nesting.
- Ignore files/folders recognized as junk (e.g., `presupported`, `previews`, `textures`, `lychee/chi*` projects) unless `sequence_number_regex` extraction needs the filename.

## Loader + matcher workflow (updated, Phase 1)
We’ll continue to use YAML as SSOT with MMF-assisted population; matching is a deterministic pass like our other matchers.

Population (YAML; no DB table needed in Phase 1):
- Clean any non-designer entries first:
```powershell
.\.venv\Scripts\python.exe .\scripts\maintenance\cleanup_mmf_collections.py
```
- Append up to N latest MMF collections per designer into YAML:
```powershell
$env:MMF_API_KEY = "<your_api_key>";
.\.venv\Scripts\python.exe .\scripts\10_integrations\update_collections_from_mmf.py --max 5 --apply
```

Matching (implemented):
- `scripts/30_normalize_match/match_collections.py` reads per-designer YAML from `vocab/collections/` and, for Variants with `designer` set, applies the matching strategy above to populate `variant.collection_*`.
- Supports `--dry-run` (default) and `--apply`, writing a JSON report with `summary` and per-item results.
- You can scope by one or more designers via repeated `--designer <key>` flags, or pass all designers by iterating over `vocab/collections/*.yaml`.

Optional: on-demand MMF enrichment during matching
- When enabled via `--mmf-refill-on-miss`, the matcher will, upon a strong collection phrase with no YAML hit:
  1) Check `vocab/mmf_usernames.json` for the designer’s `mmf_username`.
  2) Invoke the MMF updater programmatically for that designer (bounded N; default 5–10) to append any newly discovered collections into `vocab/collections/<designer>.yaml` (dry-run unless `--apply`).
  3) Reload the designer’s YAML and retry the collection match.

Guardrails
- Default remains 100% local: no network calls unless `--mmf-refill-on-miss` is provided and either `MMF_API_KEY` or OAuth creds are set.
- Only collections under the mapped `mmf_username` are considered; global/non-designer lists are ignored.
- In `--dry-run`, the matcher includes a `would_append_collections` section in the JSON report and does not write YAML.
- Backoff on rate limits; errors are non-fatal and logged in the report.

Example dry-run (Windows PowerShell):
```powershell
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_collections.py `
  --db-url sqlite:///./data/stl_manager_v1.db `
  --designer heroes_infinite `
  --mmf-refill-on-miss `
  --out ("reports/match_collections_heroes_infinite_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

Apply across all designers that have YAML manifests:

```powershell
$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";
$designers = (Get-ChildItem .\vocab\collections\*.yaml | ForEach-Object { $_.BaseName });
$args = @(); foreach ($d in $designers) { $args += @('--designer', $d) };
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_collections.py --db-url sqlite:///./data/stl_manager_v1.db @args --apply --out ("reports/match_collections_all_apply_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

Validate YAML (ruamel.yaml):

```powershell
.\.venv\Scripts\python.exe .\scripts\maintenance\validate_collections_yaml.py
```

Example consolidation (Printable Scenery):
- Instead of separate YAML entries like “Time Warp Europe - Medieval Church / House / Farm / Stone Barn”, define a single collection:

```yaml
- id: printable_scenery__time_warp_europe
  name: Time Warp Europe
  theme: time_warp_europe
  aliases:
  - Time Warp Europe
  - Time Warp Europe - Church Walls
  - Time Warp Europe - Medieval Church
  - Time Warp Europe - Medieval House
  - Time Warp Europe - The Farm
  - Time Warp Europe - The Stone Barn
  match:
    path_patterns:
    - "(?i)time[-_ ]warp[-_ ]europe"
```

This collapses sub-lines into a single collection id and improves consistency across variants.

### When the collection is not in YAML yet (smart proposer)
Instead of ignoring variants or asking the user to guess, add a proposer step that scans designer-scoped variants lacking `collection_id`, extracts collection-like phrases from path segments, and drafts YAML entries for review.

Tool (added): `scripts/60_reports_analysis/propose_missing_collections.py`
- Reads variants where `designer IS NOT NULL` and `collection_id IS NULL`.
- Extracts a likely collection phrase from the top/leaf segments (ignores generic words like `Supported`, `STLs`, etc.).
- Produces a JSON report and, with `--apply-draft`, writes draft YAML under `vocab/collections/_drafts/<designer>.pending.yaml` with:
  - `name` (titleized phrase), `theme` (slug), empty `cycle`, `aliases` including the phrase, and a safe `match.path_patterns` for the full title.
  - Standard sequence-number regex templates.
- Curator quickly adds a `source_urls` (e.g., MMF collection URL) and optional `cycle`, then moves approved entries into `vocab/collections/<designer>.yaml`.

Example commands (Windows PowerShell):
```powershell
# Propose for Heroes Infinite only; write drafts
.\.venv\Scripts\python.exe .\scripts\60_reports_analysis\propose_missing_collections.py `
  --db-url sqlite:///./data/stl_manager_v1.db `
  --designer heroes_infinite `
  --apply-draft `
  --out ("reports/propose_missing_collections_heroes_infinite_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")

# After review and adding source_urls, move curated entries from vocab/collections/_drafts to vocab/collections
```

Recommended quick flow for new/missing collections:
1) Run the proposer for the target designer(s) to generate draft entries from actual folder names.
2) Add `source_urls` and `cycle` for each draft from MMF pages; optionally run the MMF updater to fetch more recent sets.
3) Move curated entries into the canonical YAML, then run the collections matcher (dry-run, then apply).

This balances automation with a short human review, avoids false positives, and works even when MMF hasn’t surfaced the collection yet or uses slightly different titling.

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
  - Prefer `<designer_key>__<YYYY_MM>_<normalized_title>` when cycle is known, else `<designer_key>__<normalized_title>`.

MMF username mapping (centralized)
- `vocab/mmf_usernames.json` provides `designer_key -> mmf_username` used by the MMF updater and cleaner.
- Usernames must match MMF slugs exactly (case, underscores, spaces). Examples: `Artisan_Guild`, `Bestiarum Miniatures`, `HeroesInfiniteByRagingHeroes`, `TitanForgeMiniatures`, `Txarli`.

## Examples
### DM Stash “Guardians of the Fey” (September 2021)
The official page: https://www.myminifactory.com/users/DM-Stash/collection/guardians-of-the-fey (12 objects; “DM Stash September 2021 Release”).

Proposed YAML entry is already included above under `dm_stash.yaml`. With that present, any Variant under DM Stash whose path contains a phrase matching `guardians[-_ ]of[-_ ]the[-_ ]fey` near the leaf will be assigned:
- `collection_id = dm_stash__2021_09_guardians_of_the_fey`
- `collection_original_label =` the matched label/substring
- `collection_cycle = 2021-09`
- `collection_sequence_number =` first number parsed from file/folder (if present)
- `collection_theme = fey`

### Heroes Infinite: expected behavior when a variant is recognized
Given var 340 is recognized as `designer = heroes_infinite`, the collections matcher should:
- Look up `vocab/collections/heroes_infinite.yaml` (MMF-seeded + curated).
- Try deterministic `match.path_patterns` first; otherwise allow an alias match using the specific collection title.
- On match, fill:
  - `collection_id = heroes_infinite__<YYYY_MM>_<normalized_title>` (or `heroes_infinite__<normalized_title>` if cycle missing)
  - `collection_original_label =` the matched phrase from the path or alias
  - `collection_cycle = <YYYY-MM>` (if present in YAML)
  - `collection_sequence_number =` first sequence parsed by regex if applicable
  - `collection_theme = <theme>` (slugified, e.g., `arcadian_elves_ii`)

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

## Rollout plan (updated)
1. Approve this SSOT schema (no DB changes required for Phase 1).
2. Populate per-designer YAML via MMF updater (and manual curation where needed); ensure `vocab/mmf_usernames.json` has correct slugs.
3. Implement `match_collections.py` (or `--collections` mode) with dry-run first.
4. Run dry-run for specific designers (e.g., `heroes_infinite`); review JSON report; refine `match.path_patterns` and aliases in YAML to improve precision.
5. Apply; then expand to other designers.

---

Short-term alternative (no loader yet):
- Parse `collection_cycle` and `collection_original_label` directly from folder names and leave `collection_id`/`collection_theme` null unless a very precise token exists. This yields partial utility but lacks stability across reorganizations and won’t support filtering by a canonical release.

Recommended path is the SSOT YAML + matcher above for stability, auditability, and ease of future UI filters.

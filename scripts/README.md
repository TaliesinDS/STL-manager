# Scripts README

This document describes the helper scripts in `scripts/`, their purpose, inputs/outputs, and safe usage patterns. Scripts are organized by stage folders described in `docs/SCRIPTS_ORGANIZATION.md`. Most scripts default to dry-run behavior and require `--apply` (and sometimes `--force`) to write changes to the database.

## Key environment

- `STLMGR_DB_URL` — point scripts at a specific SQLite DB (recommended when writing):

```powershell
$env:STLMGR_DB_URL = 'sqlite:///C:/full/path/to/data/stl_manager_v1.db'
```

Activate your venv before running scripts (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

## CLI quick-reference

- Defaults are dry-run; add `--apply` to write. Prefer `--db-url` to select the database.
- Root files are shims; the Canonical column shows the staged source.

| Script (entrypoint) | Canonical | Purpose | Writes? | Key flags/options |
|---|---|---|---|---|
| `scripts/quick_scan.py` | `scripts/10_inventory/quick_scan.py` | Tokenize filenames/paths; plan vocab | No | `--root`, `--ignore-file`, `--out` |
| `scripts/create_sample_inventory.py` | `scripts/10_inventory/create_sample_inventory.py` | Build inventory JSON from folders | No | `--root`, `--out` |
| `scripts/load_sample.py` | `scripts/20_loaders/load_sample.py` | Ingest inventory JSON into DB | Yes | `--db-url`, `--apply`, `--file` |
| `scripts/compute_hashes.py` | `scripts/10_inventory/compute_hashes.py` | Compute SHA-256 for File rows | Yes (with apply) | `--db-url`, `--apply`, `--limit` |
| `scripts/load_codex_from_yaml.py` | `scripts/20_loaders/load_codex_from_yaml.py` | Load YAML codex (40K/HH/AoS) | Yes | `--file`, `--db-url`, `--apply` |
| `scripts/load_designers.py` | `scripts/20_loaders/load_designers.py` | Load designers tokenmap into vocab | Yes | `--db-url`, `--apply`, `--file` |
| `scripts/load_franchises.py` | `scripts/20_loaders/load_franchises.py` | Load franchises manifests into vocab | Yes | `--db-url`, `--apply` |
| `scripts/sync_designers_from_tokenmap.py` | `scripts/20_loaders/sync_designers_from_tokenmap.py` | Report stale designer vocab and orphaned Variant.designer; optionally clear/delete | Yes (with apply) | `--db-url`, `--apply`, `--delete-vocab`, `<tokenmap.md>` |
| `scripts/sync_characters_to_vocab.py` | `scripts/20_loaders/sync_characters_to_vocab.py` | Aggregate characters from `vocab/franchises/*.json` into vocab | Yes (with apply) | `--db-url`, `--apply`, `--franchise` |
| `scripts/normalize_inventory.py` | `scripts/30_normalize_match/normalize_inventory.py` | Normalize variants using tokenmaps and vocab | Yes (with apply) | `--db-url`, `--apply`, `--batch`, `--only-missing` |
| `scripts/match_franchise_characters.py` | `scripts/30_normalize_match/match_franchise_characters.py` | Franchise/character matcher | Yes (with apply) | `--db-url`, `--apply`, `--batch`, `--out` |
| `scripts/match_variants_to_units.py` | `scripts/30_normalize_match/match_variants_to_units.py` | Unit matcher (40K/HH/AoS) | No/Yes (report/apply) | `--db-url`, `--apply`, `--systems`, `--include-kit-children`, `--out` |
| `scripts/backfill_kits.py` | `scripts/40_kits/backfill_kits.py` | Mark/link kits and group children | Yes (with apply) | `--db-url`, `--apply`, `--limit` |
| `scripts/delete_variant.py` | `scripts/50_cleanup_repair/delete_variant.py` | Targeted variant delete | Yes | `--db-url`, `--id`, `--apply` |
| `scripts/verify_*` | `scripts/60_reports_analysis/*` | Small verification/report helpers | No | `--db-url`, script-specific |

## Common safety flags

- `--apply` — commit proposed changes to the DB (default is dry-run).  
- `--force` — overwrite existing values (use with care).  
- `--only-missing` — process only rows missing token_version (used by normalizer).  
- `--delete-vocab` — used by sync scripts to optionally delete stale `VocabEntry` rows.

## Primary scripts and contracts

- `scripts/quick_scan.py` — tokenizes filenames/paths and contains `tokenize()`, `classify_token()` and tokenmap loaders. Read-only. Used by other scripts. If `--ignore-file` is omitted it searches `ignored_tokens.txt` in this order: `scripts/30_normalize_match/` (canonical), then `vocab/`, then script directory (legacy).

- `scripts/create_sample_inventory.py` — compatibility shim forwarding to `scripts/10_inventory/create_sample_inventory.py`.
  - Canonical: `scripts/10_inventory/create_sample_inventory.py` (walks sample folders and emits an inventory JSON used by the loader). Read-only.

- `scripts/20_loaders/load_sample.py` — reads inventory JSON and inserts/updates `Variant` and `File` rows. Writes to DB. Root entrypoint `scripts/load_sample.py` is a shim.

- `scripts/20_loaders/load_designers.py` — parses `vocab/designers_tokenmap.md` and upserts `VocabEntry(domain='designer')` rows (aliases/meta). Writes to DB. Root entrypoint is a shim.

- `scripts/30_normalize_match/normalize_inventory.py` — normalization engine: reads `Variant` + `File` rows, tokenizes, infers fields (designer, franchise, support_state, height_mm, flags, etc.) using the tokenmap and DB `VocabEntry` alias map. Dry-run by default; use `--apply` to commit and `--force` to overwrite. Supports `--batch` and `--only-missing`. Root entrypoint is a shim.

- `scripts/sync_designers_from_tokenmap.py` — compatibility shim to canonical `scripts/20_loaders/sync_designers_from_tokenmap.py`; compares `vocab/designers_tokenmap.md` to DB `VocabEntry` rows, reports stale vocab, detects orphaned `Variant.designer` values, and optionally clears designer fields and deletes stale vocab entries with `--apply` and `--delete-vocab`. Supports `--db-url`.

- `scripts/compute_hashes.py` — compatibility shim forwarding to `scripts/10_inventory/compute_hashes.py`.
  - Canonical: `scripts/10_inventory/compute_hashes.py` — compute SHA-256 for `File` rows (dry-run by default; may write when run with apply flags).

- Diagnostics & quick-fix utilities:
  - `scripts/debug_variant_fields.py` — counts normalized fields and prints sample variants.
  - `scripts/show_variant.py` — prints full Variant row(s) as JSON.
  - `scripts/inspect_inference.py` — run inference for a single Variant id and print proposed inferred values.
    (test harness moved under `tests/`; use `tests/test_write_variant.py`.)
  - `scripts/fix_skarix_designer.py` — focused fixer to remove mistaken `designer='skarix'` VocabEntry and clear Variant.designer values; supports `--apply`.

Additional matching, migration, and verification scripts
- `scripts/30_normalize_match/match_franchise_characters.py` — Automatic matcher that scans `Variant` rows and attempts to infer `franchise` and `character` hints by loading `vocab/franchises/*.json`, `vocab/characters_tokenmap.md`, and `vocab/tokenmap.md`. Produces a dry-run report listing conservative proposals and supports `--apply` to commit. Respects tabletop gating and will not populate `faction_general` from character-first-names for non-tabletop items.
- `scripts/50_cleanup_repair/migrate_codex_to_character.py` — Finds variants where `codex_unit_name` is non-empty and `character_name` is empty, and proposes copying `codex_unit_name` → `character_name` (dry-run by default). Use `--apply` to perform the copy. Conservative semantics: only writes when `character_name` is empty unless `--force` is provided.
- `scripts/60_reports_analysis/export_codex_candidates.py` — Export utility that writes a JSON report of all `Variant` rows with a non-empty `codex_unit_name` for auditing and review. Read-only.
- `scripts/60_reports_analysis/verify_migration_output.py` — Small verification helper that reads the DB and writes a JSON verification file listing migrated rows (variant id, rel_path, `codex_unit_name`, `character_name`, `character_aliases`). Use after migrations to produce an auditable report.
- `scripts/30_normalize_match/apply_proposals_from_report.py` — Reads a matcher or normalizer dry-run report (JSON proposals) and applies the proposals conservatively to the DB. Defaults to dry-run; requires `--apply` to commit. Maps legacy `codex_unit_name` proposals into `character_name` when appropriate.
- `scripts/30_normalize_match/apply_vocab_matches.py` — Similar helper that applies proposals generated from vocabulary-based matching (updating `character_name`, `character_aliases`, and safe `franchise` hints). Dry-run by default.
- `scripts/50_cleanup_repair/set_variant_franchise.py` — A small focused utility for manually setting a single `Variant`'s `franchise` (useful for targeted fixes like "var 119 belongs to My Hero Academia"). Requires `--apply` to write.
- `scripts/20_loaders/create_missing_franchises.py` — Convenience script that creates `VocabEntry(domain='franchise')` rows for franchises found in `vocab/franchises/*.json` when you want franchise token aliases to be present in the DB for normalizer lookup.
- `scripts/50_cleanup_repair/repair_sigmar_variants.py` — Targeted fixer used during debugging to repair variants that were incorrectly matched to Cities of Sigmar; an example of a focused repair script pattern (dry-run default; `--apply` to commit).
- `scripts/30_normalize_match/match_variants_to_units.py` — Unit matcher (preferred over deprecated `assign_codex_units_aos.py`).
- `scripts/20_loaders/sync_characters_to_vocab.py` — aggregates characters from `vocab/franchises/*.json` and upserts `VocabEntry(domain='character')`. Dry-run by default; `--apply` to write. Supports `--db-url` and `--franchise` filter.

## Normalization helpers

- `scripts/apply_sample_folder_tokens.py` — compatibility shim forwarding to `scripts/30_normalize_match/apply_sample_folder_tokens.py`.
  - Canonical: `scripts/30_normalize_match/apply_sample_folder_tokens.py` — merges tokens captured from folder paths into Variant/File residual_tokens. Dry-run by default; `--apply` writes. Example:

```powershell
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\apply_sample_folder_tokens.py --inventory .\tests\fixtures\sample_inventory.json --apply
```

  - Canonical ignore list: `scripts/30_normalize_match/ignored_tokens.txt` (also used by `quick_scan.py` via fallback search).

## Recommended pipeline

1. Generate or update inventory (if needed):

```powershell
.venv\Scripts\python.exe scripts\10_inventory\create_sample_inventory.py --root <source-folder> --out tests/fixtures/sample_inventory.json
```

2. Ingest inventory into DB:

```powershell
.venv\Scripts\python.exe scripts\20_loaders\load_sample.py --file tests/fixtures/sample_inventory.json --db-url sqlite:///./data/stl_manager_v1.db --apply
```

3. Load tokenmaps (designers, franchises, etc.) into DB:

```powershell
.venv\Scripts\python.exe scripts\20_loaders\load_designers.py --file vocab\designers_tokenmap.md --db-url sqlite:///./data/stl_manager_v1.db --apply
```

4. Dry-run normalization and inspect proposals:

```powershell
.venv\Scripts\python.exe scripts\30_normalize_match\normalize_inventory.py --db-url sqlite:///./data/stl_manager_v1.db
```

5. Apply normalization when ready (explicitly set DB URL):

```powershell
.venv\Scripts\python.exe scripts\30_normalize_match\normalize_inventory.py --db-url sqlite:///./data/stl_manager_v1.db --apply
```

6. Re-run `debug_variant_fields.py` / `show_variant.py` / `inspect_inference.py` to validate results.

7. Run the sync script after editing tokenmaps to detect/remove drift:

```powershell
.venv\Scripts\python.exe scripts\20_loaders\sync_designers_from_tokenmap.py vocab\designers_tokenmap.md --db-url sqlite:///./data/stl_manager_v1.db
```

Use `--apply --delete-vocab` to commit clearing and deletion when you are confident.

## Troubleshooting tips

- DB viewer stale cache: close and re-open the DB file or re-run the inspection scripts (`show_variant.py`) to confirm writes.  
- Wrong DB target: always ensure `STLMGR_DB_URL` points to the DB file your GUI is inspecting.  
- SQLAlchemy warning about `Query.get()`: harmless; consider updating scripts to `Session.get()` to silence it.

Windows archive extractor logs
- The PowerShell helper `windows_tools/Extract-Archives.ps1` now defaults its `-LogCsv` output to the repo `reports/` folder (e.g., `reports/Extract-Archives_log_<timestamp>.csv`). Override with `-LogCsv <path>` to customize.

## CI / automation ideas

- Run `scripts/sync_designers_from_tokenmap.py` in dry-run in CI on PRs that modify any tokenmap to flag DB drift.  
- Optionally add a pre-commit hook that runs `debug_variant_fields.py` or a quick `inspect_inference.py` spot-check for changed files.

## Contributing

### Compatibility shims

During migration, many root-level scripts are thin shims that dynamically import and forward to their canonical counterparts under the staged folders (e.g., `scripts/50_cleanup_repair/delete_variant.py`). This keeps legacy entrypoints working. Prefer invoking the canonical paths in new automation, and update any personal notes to point to the staged locations.

When adding new scripts, follow these guidelines:
- Default to dry-run behavior; require an explicit `--apply` to write to DB.  
- Respect `STLMGR_DB_URL` for DB selection.  
- Keep tokenization and classification in `scripts/quick_scan.py` to avoid divergent logic.

---
If you want, I can add a small GitHub Action that runs the sync script in dry-run on PRs touching `vocab/` files. Tell me if you'd like that next.

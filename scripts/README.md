# Scripts README

This document describes the helper scripts in `scripts/`, their purpose, inputs/outputs, and safe usage patterns. The scripts are organized into stages: scan/tokenize, ingest/load, normalize/compare, hashing/inspection, and diagnostics/fixers. Most scripts default to dry-run behavior and require `--apply` (and sometimes `--force`) to write changes to the database.

## Key environment

- `STLMGR_DB_URL` — point scripts at a specific SQLite DB (recommended when writing):

```powershell
$env:STLMGR_DB_URL = 'sqlite:///C:/full/path/to/data/stl_manager_v1.db'
```

Activate your venv before running scripts (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

## Common safety flags

- `--apply` — commit proposed changes to the DB (default is dry-run).  
- `--force` — overwrite existing values (use with care).  
- `--only-missing` — process only rows missing token_version (used by normalizer).  
- `--delete-vocab` — used by sync scripts to optionally delete stale `VocabEntry` rows.

## Primary scripts and contracts

- `scripts/quick_scan.py` — tokenizes filenames/paths and contains `tokenize()`, `classify_token()` and tokenmap loaders. Read-only. Used by other scripts.

- `scripts/create_sample_inventory.py` — (inventory generator) walks sample folders and emits an inventory JSON. Output used by the loader. Read-only.

- `scripts/load_sample.py` — reads inventory JSON and inserts/updates `Variant` and `File` rows. Writes to DB.

- `scripts/load_designers.py` — parses `vocab/designers_tokenmap.md` and upserts `VocabEntry(domain='designer')` rows (aliases/meta). Writes to DB.

- `scripts/normalize_inventory.py` — normalization engine: reads `Variant` + `File` rows, tokenizes, infers fields (designer, franchise, support_state, height_mm, flags, etc.) using the tokenmap and DB `VocabEntry` alias map. Dry-run by default; use `--apply` to commit and `--force` to overwrite. Supports `--batch` and `--only-missing`.

- `scripts/sync_designers_from_tokenmap.py` — compares `vocab/designers_tokenmap.md` to DB `VocabEntry` rows, reports stale vocab, detects orphaned `Variant.designer` values (designer string not present in tokenmap aliases), and optionally clears designer fields and deletes stale vocab entries with `--apply` and `--delete-vocab`.

- `scripts/compute_hashes.py` — compute SHA-256 for `File` rows (dry-run by default; may write when run with apply flags).

- Diagnostics & quick-fix utilities:
  - `scripts/debug_variant_fields.py` — counts normalized fields and prints sample variants.
  - `scripts/show_variant.py` — prints full Variant row(s) as JSON.
  - `scripts/inspect_inference.py` — run inference for a single Variant id and print proposed inferred values.
  - `scripts/test_write_variant.py` — small test to prove DB writes persist.
  - `scripts/fix_skarix_designer.py` — focused fixer to remove mistaken `designer='skarix'` VocabEntry and clear Variant.designer values; supports `--apply`.

## Recommended pipeline

1. Generate or update inventory (if needed):

```powershell
.venv\Scripts\python.exe scripts\create_sample_inventory.py <source-folder> > tests/fixtures/sample_inventory.json
```

2. Ingest inventory into DB:

```powershell
.venv\Scripts\python.exe scripts\load_sample.py tests/fixtures/sample_inventory.json
```

3. Load tokenmaps (designers, franchises, etc.) into DB:

```powershell
.venv\Scripts\python.exe scripts\load_designers.py vocab\designers_tokenmap.md
```

4. Dry-run normalization and inspect proposals:

```powershell
.venv\Scripts\python.exe scripts\normalize_inventory.py
```

5. Apply normalization when ready (explicitly set DB URL):

```powershell
$env:STLMGR_DB_URL = 'sqlite:///C:/full/path/to/data/stl_manager_v1.db'
.venv\Scripts\python.exe scripts\normalize_inventory.py --apply
```

6. Re-run `debug_variant_fields.py` / `show_variant.py` / `inspect_inference.py` to validate results.

7. Run the sync script after editing tokenmaps to detect/remove drift:

```powershell
.venv\Scripts\python.exe scripts\sync_designers_from_tokenmap.py vocab\designers_tokenmap.md
```

Use `--apply --delete-vocab` to commit clearing and deletion when you are confident.

## Troubleshooting tips

- DB viewer stale cache: close and re-open the DB file or re-run the inspection scripts (`show_variant.py`) to confirm writes.  
- Wrong DB target: always ensure `STLMGR_DB_URL` points to the DB file your GUI is inspecting.  
- SQLAlchemy warning about `Query.get()`: harmless; consider updating scripts to `Session.get()` to silence it.

## CI / automation ideas

- Run `scripts/sync_designers_from_tokenmap.py` in dry-run in CI on PRs that modify any tokenmap to flag DB drift.  
- Optionally add a pre-commit hook that runs `debug_variant_fields.py` or a quick `inspect_inference.py` spot-check for changed files.

## Contributing

When adding new scripts, follow these guidelines:
- Default to dry-run behavior; require an explicit `--apply` to write to DB.  
- Respect `STLMGR_DB_URL` for DB selection.  
- Keep tokenization and classification in `scripts/quick_scan.py` to avoid divergent logic.

---
If you want, I can add a small GitHub Action that runs the sync script in dry-run on PRs touching `vocab/` files. Tell me if you'd like that next.

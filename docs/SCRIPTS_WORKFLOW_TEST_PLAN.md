# Scripts Workflow Test Plan (STL Manager)

This document proposes a comprehensive test suite to validate the end‑to‑end workflow after migrating `scripts/` into subfolders with backward‑compatible shims. The goal is to ensure users can perform the entire pipeline (bootstrap → inventory → loaders → normalize/match → kits → cleanup/repair → reports) using the new canonical paths and the legacy root shims, with consistent CLI flags and Windows PowerShell compatibility.

Status update (2025-09-03)
- Workflow tests are implemented and runnable on Windows PowerShell using the venv interpreter; they cover bootstrap, loaders (units/parts), normalization, matchers, kits backfill, cleanup (safe subset), and verification reports. Legacy shims are exercised for `--help` and dry‑runs.

## Objectives and success criteria

- All workflow stages run without errors on Windows PowerShell using the venv Python and `--db-url` flags (no env var reliance).
- Root shim entrypoints still work and delegate to their new canonical scripts, preserving CLI and exit codes.
- Defaults are safe: dry‑run unless `--apply`; timestamped report files under `reports/`.
- Loaders ingest vocab into a temporary DB; normalize/match produce schema‑valid report JSON.
- Idempotency: re‑running stages results in no additional changes (no duplicates, no drift).
- Existing unit tests remain green; workflow tests never touch `data/stl_manager_v1.db`.

## Test scope (critical path)

1) Bootstrap DB
- Create a fresh temporary SQLite DB and upgrade to latest Alembic head.

2) Inventory
- Generate a small sample inventory and ingest into the temp DB.
- Optional: compute file hashes for the sample set (smoke only).

3) Loaders
- Load designers, franchises, YAML codex manifests (40K, AoS, Heresy), and 40K parts vocab (wargear, bodies).

4) Normalize/Match
- Normalize inventory (dry‑run → then `--apply`).
- Run franchise/character matcher (dry‑run), save timestamped report, then apply proposals.
- Run unit matcher (e.g., 40K) with `--include-kit-children` (dry‑run), then apply proposals.
- Optional: parts matcher dry‑run to ensure it runs and emits a sane report.

5) Kits
- Backfill kits (dry‑run, then `--apply`) to link parent/children and set kit child types.
- Optional: link a virtual parent (dry‑run only).

6) Cleanup/Repair
- Safe hygiene scripts (dry‑run): prune invalid variants, repair orphans. Avoid destructive actions in CI.

7) Reports/Verification
- Representative reports (counts/coverage/verification) with timestamped outputs and schema checks.

8) Shims
- For each legacy root shim, run `--help` and one representative dry‑run; verify delegation and exit code 0.

## Environment and conventions

- OS/shell: Windows, PowerShell (`pwsh.exe`).
- Python: explicit venv path: `c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe`.
- DB: never touch `data/stl_manager_v1.db`. Use a temp DB under `.pytest-tmp/`, e.g., `sqlite:///./.pytest-tmp/stl_manager_e2e.db` passed via `--db-url`.
- Reports: verify files created under `reports/` with timestamped names; prefer `reports/test_artifacts/` for CI.
- CLI: prefer `--db-url` on all scripts; avoid `$env:STLMGR_DB_URL` in tests.

## Proposed test structure (pytest)

- Folder: `tests/workflow/`
- `conftest.py`
  - Fixture `tmp_db_url` to create an empty SQLite file in `.pytest-tmp/` and return the SQLAlchemy URL string.
  - Fixture `venv_python` returning the absolute venv Python path.
  - Helper `run_cli(args: list[str], cwd=repo_root) -> CompletedProcess` using `subprocess.run` (each arg its own list element; no quoting issues).
- Use `@pytest.mark.workflow` and optionally `pytest-order` for deterministic sequencing.
- Target runtime ≤ 3–5 minutes locally; guard slower tests with `@pytest.mark.slow`.

## Test cases and example invocations

Replace `DBURL` with the fixture‑provided value (e.g., `sqlite:///./.pytest-tmp/stl_manager_e2e.db`). In pytest, invoke via `subprocess` rather than shell strings.

1) Bootstrap
- Purpose: ensure a clean DB can be created/migrated to head.
- Command:
  - Canonical: `".\\.venv\\Scripts\\python.exe" .\\scripts\\00_bootstrap\\bootstrap_db.py --db-url DBURL`
- Assertions: DB file created; `alembic_version` row exists; core tables present.

2) Inventory: create and load sample
- Create inventory JSON:
  - `".\\.venv\\Scripts\\python.exe" .\\scripts\\10_inventory\\create_sample_inventory.py --out .\\.pytest-tmp\\sample_inventory.json`
- Ingest into DB:
  - `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_sample.py --file .\\.pytest-tmp\\sample_inventory.json --db-url DBURL --apply`
- Optional hashing (smoke):
  - `".\\.venv\\Scripts\\python.exe" .\\scripts\\10_inventory\\compute_hashes.py --limit 10 --db-url DBURL`
- Assertions: Variants/Files rows inserted (>0); re‑ingest is a no‑op; hashing populates expected columns on subset.

3) Loaders: vocab and codex
- Designers: `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_designers.py --db-url DBURL --apply`
- Franchises: `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_franchises.py --db-url DBURL --apply`
- Codex manifests:
  - 40K: `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_codex_from_yaml.py --file .\\vocab\\codex_units_w40k.yaml --db-url DBURL --apply`
  - AoS: `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_codex_from_yaml.py --file .\\vocab\\codex_units_aos.yaml --db-url DBURL --apply`
  - Heresy: `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_codex_from_yaml.py --file .\\vocab\\codex_units_horus_heresy.yaml --db-url DBURL --apply`
- Parts vocab (40K):
  - `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_codex_from_yaml.py --file .\\vocab\\wargear_w40k.yaml --db-url DBURL --apply`
  - `".\\.venv\\Scripts\\python.exe" .\\scripts\\20_loaders\\load_codex_from_yaml.py --file .\\vocab\\bodies_w40k.yaml --db-url DBURL --apply`
- Assertions: Reference tables populated; no duplicate key errors; counts roughly match expectations.

4) Normalize (dry‑run then apply)
- Dry‑run: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\normalize_inventory.py --db-url DBURL --out reports/normalize_inventory_YYYYMMDD_HHMMSS.json`
- Apply: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\normalize_inventory.py --db-url DBURL --apply`
- Assertions: Dry‑run writes a timestamped JSON with expected schema; apply updates rows and is idempotent.

5) Franchise/Character match → apply
- Dry‑run: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\match_franchise_characters.py --db-url DBURL --out reports/match_franchise_YYYYMMDD_HHMMSS.json --batch 100`
- Apply: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\apply_proposals_from_report.py --db-url DBURL --file reports/match_franchise_*.json`
- Assertions: Report schema valid; apply updates `franchise_id`/`character_id`; rerun is no‑op.

6) Unit match (with children) → apply
- Dry‑run: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\match_variants_to_units.py --db-url DBURL --include-kit-children --limit 0 --out reports/match_units_with_children_YYYYMMDD_HHMMSS.json`
- Apply: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\apply_proposals_from_report.py --db-url DBURL --file reports/match_units_with_children_*.json`
- Assertions: Report exists and references known variants; apply sets `unit_id`; re‑apply is idempotent.

7) Parts matcher (optional)
- Dry‑run: `".\\.venv\\Scripts\\python.exe" .\\scripts\\30_normalize_match\\match_parts_to_variants.py --db-url DBURL --out reports/match_parts_YYYYMMDD_HHMMSS.json`
- Assertions: Report created; entries link kit children to parts; schema sanity check.

8) Kits backfill → apply
- Dry‑run: `".\\.venv\\Scripts\\python.exe" .\\scripts\\40_kits\\backfill_kits.py --db-url DBURL --out reports/backfill_kits_dryrun_YYYYMMDD_HHMMSS.json`
- Apply: `".\\.venv\\Scripts\\python.exe" .\\scripts\\40_kits\\backfill_kits.py --db-url DBURL --apply`
- Assertions: Parents/children linked; child types persisted; spot‑check known parents.

9) Cleanup/Repair (safe subset)
- Dry‑run only: `".\\.venv\\Scripts\\python.exe" .\\scripts\\50_cleanup_repair\\prune_invalid_variants.py --db-url DBURL`
- Dry‑run only: `".\\.venv\\Scripts\\python.exe" .\\scripts\\50_cleanup_repair\\repair_orphan_variants.py --db-url DBURL`
- Assertions: Complete without errors; logs show proposals but no DB mutations.

10) Reports/Verification
- `".\\.venv\\Scripts\\python.exe" .\\scripts\\60_reports_analysis\\report_codex_counts.py --db-url DBURL --out reports/report_codex_counts_YYYYMMDD_HHMMSS.json`
- `".\\.venv\\Scripts\\python.exe" .\\scripts\\60_reports_analysis\\verify_applied_matches.py --db-url DBURL --out reports/verify_matches_YYYYMMDD_HHMMSS.json`
- Assertions: Files exist; names are timestamped; JSON schema validated.

11) Shim verification
- Shims to sample (adjust to actual set):
  - `scripts/normalize_inventory.py`, `scripts/match_franchise_characters.py`, `scripts/match_variants_to_units.py`, `scripts/backfill_kits.py`, `scripts/load_codex_from_yaml.py`, `scripts/load_designers.py`, `scripts/load_franchises.py`, `scripts/compute_hashes.py`, `scripts/create_sample_inventory.py`, `scripts/apply_proposals_from_report.py`.
- For each, run `--help` and a no‑op/dry‑run with `--db-url DBURL`.
- Assertions: Exit code 0; help text prints; effects mirror canonical path; optional deprecation notice printed.

## JSON schema sanity checks

Implement lightweight validators in tests to sanity‑check report files:
- Required top‑level fields (e.g., `generated_at`, `script`, `db_url`, `items`).
- Each item has expected keys per script (e.g., `variant_id`, `proposal`, `confidence`, etc.).
- Filename pattern matches `*_YYYYMMDD_HHMMSS.json`, under `reports/`.

## Idempotency and safety

- Re‑run apply steps and assert no additional rows/updates occur.
- Assert dry‑run never modifies the DB (row counts unchanged before/after).
- Ensure destructive cleanup scripts run only in dry‑run mode in CI.

## Windows/PowerShell notes

- Always use explicit venv Python: `".\\.venv\\Scripts\\python.exe"`.
- Prefer `--db-url` explicitly; avoid `$env:STLMGR_DB_URL=…;` patterns.
- In pytest, pass arguments as a list to `subprocess.run` to avoid quoting mishaps.

## How to run locally

- All tests:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q
```

- Only workflow tests:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q -k workflow
```

- Verbose single test with live output:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q -k workflow -vv -s
```

## Implementation plan (incremental)

1) Add `tests/workflow/` with `conftest.py` and a first smoke test covering bootstrap + designers/franchises load + normalize dry‑run.
2) Add matchers (franchise, units) dry‑run tests with JSON checks; then add apply + idempotency checks.
3) Add kits backfill dry‑run + apply with small known sample assertions.
4) Add shim `--help` and dry‑run checks across the legacy entrypoints.
5) Gate slow/optional tests (`match_parts_to_variants.py`) behind `@pytest.mark.slow` or an env flag.

## Mapping to requirements

- End‑to‑end workflow validated: Yes (stages 1–10).
- Shim behavior validated: Yes (stage 11).
- Safe defaults and timestamped reports: Yes (checks in stages 4–7, 10).
- Windows PowerShell compatibility: Yes (explicit commands and subprocess execution model).
- Non‑interference with canonical DB: Yes (temp DB fixture).

---
This plan aims for high confidence with quick feedback. Start with a minimal happy path, then expand coverage to matchers, kits, and representative reports while keeping runs fast and safe.

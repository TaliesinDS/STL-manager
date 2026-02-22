# CLI Reference

All scripts honor the `STLMGR_DB_URL` environment variable. Example:

```powershell
$env:STLMGR_DB_URL='sqlite:///data/stl_manager_v1.db'
```

Most commands support `--db-url` as an explicit override.

---

## Quick Start (Developer)

```powershell
Set-Location 'C:\path\to\STL-manager'
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Initialize DB (safe to re-run)
python scripts/00_bootstrap/bootstrap_db.py --db-url sqlite:///./data/stl_manager_v1.db --use-metadata

# Optional: create a tiny inventory JSON and load it
python scripts/10_inventory/create_sample_inventory.py --out data/sample_quick_scan.json
python scripts/20_loaders/load_sample.py --file data/sample_quick_scan.json --db-url sqlite:///./data/stl_manager_v1.db
```

### Alembic (schema migrations)

```powershell
pip install -r requirements.txt
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

---

## Quick Exploratory Token Scan

Canonical script: `scripts/10_inventory/quick_scan.py`

```powershell
python scripts/10_inventory/quick_scan.py --root D:\Models --limit 60000 --extensions .stl .obj .chitubox .lys --json-out quick_scan_report.json
```

With dynamic vocab from tokenmap:

```powershell
python scripts/10_inventory/quick_scan.py --root D:\Models --tokenmap vocab\tokenmap.md --json-out quick_scan_report.json
```

What it does (Phase 0 safe):
- Recurses files (no archive extraction) honoring extension filter.
- Splits stems and directory names on `_ - space`.
- Optionally loads designers / lineage / faction aliases / stopwords from `vocab/tokenmap.md`.
- Counts token frequencies, classifies against embedded vocab, highlights unknown tokens.
- Highlights scale ratio / mm tokens and numeric-containing tokens.
- Optional `--include-archives` adds archive filenames to token stream.

What it does NOT do: no writes / renames / DB mutations; no geometry parsing.

---

## Vocab Loaders

### Load Designers

```powershell
.\.venv\Scripts\python.exe scripts\20_loaders\load_designers.py --db-url sqlite:///data/stl_manager_v1.db --apply
```

### Load Franchises

Dry-run (default):

```powershell
$env:STLMGR_DB_URL='sqlite:///data/stl_manager_v1.db'
& .venv\Scripts\python.exe scripts\20_loaders\load_franchises.py vocab\franchises
```

Commit with dedup:

```powershell
& .venv\Scripts\python.exe scripts\20_loaders\load_franchises.py vocab\franchises --dedupe --commit
```

### Load Codex Units & Parts

```powershell
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_codex_from_yaml.py --file .\vocab\codex_units_w40k.yaml --db-url sqlite:///./data/stl_manager_v1.db --commit
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_codex_from_yaml.py --file .\vocab\codex_units_aos.yaml --db-url sqlite:///./data/stl_manager_v1.db --commit
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_codex_from_yaml.py --file .\vocab\codex_units_horus_heresy.yaml --db-url sqlite:///./data/stl_manager_v1.db --commit
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_codex_from_yaml.py --file .\vocab\wargear_w40k.yaml --db-url sqlite:///./data/stl_manager_v1.db --commit
.\.venv\Scripts\python.exe .\scripts\20_loaders\load_codex_from_yaml.py --file .\vocab\bodies_w40k.yaml --db-url sqlite:///./data/stl_manager_v1.db --commit
```

Quick verification:

```powershell
.\.venv\Scripts\python.exe .\scripts\60_reports_analysis\report_codex_counts.py --db-url sqlite:///./data/stl_manager_v1.db --yaml
```

---

## Normalization & Matching

### Normalize Inventory

```powershell
$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db"

# Dry-run
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\normalize_inventory.py `
    --batch 500 --print-summary `
    --include-fields character_name,character_aliases,franchise,franchise_hints `
    --out ("reports/normalize_characters_full_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")

# Apply
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\normalize_inventory.py `
    --batch 500 --apply --print-summary `
    --include-fields character_name,character_aliases,franchise,franchise_hints `
    --out ("reports/normalize_characters_apply_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

### Match Variants to Units

```powershell
# Dry-run
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_variants_to_units.py `
    --db-url sqlite:///./data/stl_manager_v1.db --limit 200 `
    --systems w40k aos heresy --min-score 12 --delta 3

# Apply
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_variants_to_units.py `
    --db-url sqlite:///./data/stl_manager_v1.db --apply `
    --systems w40k aos heresy --min-score 12 --delta 3

# Apply with overwrite
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_variants_to_units.py `
    --db-url sqlite:///./data/stl_manager_v1.db --apply --overwrite `
    --systems w40k aos heresy
```

### Match Franchises & Characters

```powershell
$env:STLMGR_DB_URL = 'sqlite:///data/stl_manager_v1.db'

# Dry-run
& .venv\Scripts\python.exe scripts\30_normalize_match\match_franchise_characters.py `
    --db-url sqlite:///data/stl_manager_v1.db --batch 500 `
    --out .\reports\match_franchise_dryrun.json

# With OC inference (strict + fantasy)
& .venv\Scripts\python.exe scripts\30_normalize_match\match_franchise_characters.py `
    --db-url sqlite:///data/stl_manager_v1.db --batch 500 `
    --infer-oc --infer-oc-fantasy `
    --out .\reports\match_franchise_dryrun_with_oc.json

# Apply
& .venv\Scripts\python.exe scripts\30_normalize_match\match_franchise_characters.py `
    --db-url sqlite:///data/stl_manager_v1.db --batch 500 --apply
```

### Collections Matcher

```powershell
$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db"

# Single designer (dry-run)
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_collections.py `
    --db-url sqlite:///./data/stl_manager_v1.db --designer dm_stash `
    --out ("reports/match_collections_dm_stash_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")

# Apply for a single designer
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_collections.py `
    --db-url sqlite:///./data/stl_manager_v1.db --designer dm_stash --apply `
    --out ("reports/match_collections_dm_stash_apply_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")

# All designers with YAML manifests
$designers = (Get-ChildItem .\vocab\collections\*.yaml | ForEach-Object { $_.BaseName })
$args = @(); foreach ($d in $designers) { $args += @('--designer', $d) }
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\match_collections.py `
    --db-url sqlite:///./data/stl_manager_v1.db @args --apply `
    --out ("reports/match_collections_all_apply_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

---

## Inspection & Reports

- **Verify tokens**: `scripts/60_reports_analysis/verify_tokens_written.py [--db-url URL] [--like "%Ryuko%"]`
- **Verify migration output**: `scripts/60_reports_analysis/verify_migration_output.py [--db-url URL] [--ids 1,2,3]`
- **Franchise alias sync**: `scripts/20_loaders/sync_franchise_tokens_to_vocab.py [--db-url URL] [--apply]`
- **YAML validation**: `scripts/maintenance/validate_collections_yaml.py`

---

## Integrity Tests

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_codex_basing_integrity.py
```

Workflow tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -k workflow
```

---

## MyMiniFactory Integration

Key files:
- `vocab/mmf_usernames.json` — canonical map `designer_key -> MMF username`.
- `scripts/10_integrations/update_collections_from_mmf.py` — fetches latest N collections per designer.
- `scripts/maintenance/cleanup_mmf_collections.py` — removes non-designer entries from YAMLs.

Credentials — set one of:
- OAuth: `MMF_CLIENT_ID` + `MMF_CLIENT_SECRET`
- API key: `MMF_API_KEY`

```powershell
# Clean existing YAMLs
.\.venv\Scripts\python.exe .\scripts\maintenance\cleanup_mmf_collections.py

# Update all designers (append up to 5 newest per designer)
$env:MMF_API_KEY = "<your_api_key>"
.\.venv\Scripts\python.exe .\scripts\10_integrations\update_collections_from_mmf.py --max 5 --apply

# Update a single designer
.\.venv\Scripts\python.exe .\scripts\10_integrations\update_collections_from_mmf.py --designer bestiarum_miniatures --max 5 --apply
```

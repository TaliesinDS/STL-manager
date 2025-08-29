# Project Progress (Mini Beast)

A lightweight, living log of milestones, active work, and recent changes. Keep updates short and practical.

Last updated: 2025-08-29

## Status Overview
- Phase: 0 → 1 transition (inventory → deterministic normalization)
- DB: `data/stl_manager_v1.db`
- Focus: Warhammer codex/parts vocab ingestion; linking Variants ↔ Units and Parts; integrity tests green

## Completed Achievements (beyond tabletop units)
- Vocab externalization and repo structure: moved planning/specs to `docs/` and high‑churn vocab to `vocab/` for clean diffs; tools prefer `vocab/` paths
- Designers vocabulary: externalized to `vocab/designers_tokenmap.md`; loader `scripts/load_designers.py`
- Franchise manifests for display models: `vocab/franchises/*.json` (+ loader `scripts/load_franchises.py`)
- Conservative franchise/character matcher: `scripts/match_franchise_characters.py` supports dry‑run (`--out`) and apply (`--apply`), ambiguity guards, and reports
- Quick Scan tooling: `scripts/quick_scan.py` with directory tokenization, ignore list, archive filename support (`--include-archives`), JSON report, and `run_quick_scan.bat`
- Extraction utility: `scripts/Extract-Archives.ps1` for controlled archive processing (kept out of Phase 0 by default)
- Bootstrap/dev: `scripts/bootstrap_dev.ps1`, Alembic scaffold, and per‑script `STLMGR_DB_URL` handling
- Test harness: basing integrity tests wired via VS Code tasks and venv Python

## Milestones & Epics
- [x] Schema: Variant/File base, GameSystem/Faction/Unit (+aliases)
- [x] Loader: Units YAML (40K/AoS/Heresy) with raw_data preservation
- [x] Tests: Basing integrity for 40K YAML (pytest task wired)
- [x] Parts model: `Part`, `PartAlias`, `VariantPartLink`, `UnitPartLink`
- [x] Loader: Parts ingestion for `wargear_w40k.yaml` and `bodies_w40k.yaml` (dry-run verified)
- [x] Designers vocab externalized + loader (`vocab/designers_tokenmap.md`, `scripts/load_designers.py`)
- [x] Franchise manifests + loader + matcher (dry‑run/apply pipeline)
- [x] Repo restructure (docs/ and vocab/ separation)
- [x] Quick Scan improvements (dirs, archives, JSON)
- [ ] Unit ↔ Part linking policy (seed curated compatibility rules)
- [ ] API/UI: unit detail returns two result types (full models + parts/mods)
- [ ] Tests: parts ingestion/linking coverage; Alembic migrations for new tables
- [ ] HH/AoS expansion: continue manifests with conservative legality and base profiles
- [ ] Packaging: bootstrap script polish; optional PyInstaller EXE

## Current Sprint / Focus
- Implement initial `UnitPartLink` seeds for Space Marines (Intercessors/Terminator/Gravis; chapter shoulder pads; purity seals; packs)
- Add API endpoints/queries to fetch parts alongside variants for a unit
- Add unit tests for parts ingestion and linkage

## Dev Log (reverse chronological)
- 2025-08-29
  - Docs: Updated `docs/SCHEMA_codex_and_linking.md` to include Parts schema, loader behavior, queries, and UI notes
  - Loader: Wargear ingestion dry-run completed successfully on `stl_manager_v1.db`
  - ORM: Added `Part`, `PartAlias`, `VariantPartLink`, `UnitPartLink` relationships; fixed table creation against active session engine
- 2025-08-28
  - Tests: Basing integrity task stabilized; AoS YAML sweeps passing
  - Loader: Duplicate key handling in ruamel for units YAML stabilized

### Historical highlights (2025-08-15 — 2025-08-16)
- Restructured repo (created `docs/` and `vocab/`); tools prefer `vocab/` over legacy paths
- Externalized designers to `vocab/designers_tokenmap.md`; added loader and sync scripts
- Introduced franchise manifests (`vocab/franchises/*.json`), loader, and conservative matcher with dry‑run → apply workflow
- Upgraded `quick_scan.py`: directory tokens, ignore list, archive filename scanning, JSON output, batch wrapper
- Defined normalization flow, metadata fields, and initial token map versions in planning docs; logged decisions in `DECISIONS.md`

## How to Update This File
- Keep entries terse; one bullet per change.
- Update milestones as items complete; keep “Current Sprint” to 3–5 items.
- Append to Dev Log with date and 1–3 bullets.

## Quick Commands (PowerShell)
Run integrity tests:
```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_codex_basing_integrity.py
```

Run parts loader (dry-run default):
```powershell
& .\.venv\Scripts\python.exe .\scripts\load_codex_from_yaml.py --file .\vocab\wargear_w40k.yaml --db-url sqlite:///./data/stl_manager_v1.db
```

## Useful Links
- Schema & Linking: `docs/SCHEMA_codex_and_linking.md`
- Desired Features: `docs/DesiredFeatures.md`
- Planning: `docs/PLANNING.md`
- Decisions: `DECISIONS.md`
- Vocab directory: `vocab/` (designers, franchises, codex units)
- Scanning & matching: `scripts/quick_scan.py`, `scripts/load_franchises.py`, `scripts/load_designers.py`, `scripts/match_franchise_characters.py`

## Conventions
- Use ISO dates (YYYY-MM-DD) in the Dev Log.
- Prefer present tense, imperative style ("Add", "Fix", "Update").
- Keep this file focused on progress; deep rationale goes to `DECISIONS.md`.
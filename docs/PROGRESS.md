# Project Progress (STL Manager)

A lightweight, living log of milestones, active work, and recent changes. Keep updates short and practical.

Last updated: 2026-02-22

## Status Overview
- Phase: 1 (deterministic normalization, matching, and linking are operational)
- DB: `data/stl_manager_v1.db` (SQLite, single-file, write-once / read-heavy)
- API: Developer-preview FastAPI (`GET /variants`, `GET /variants/{id}`)
- Tests: 106 passing (unit + workflow), `ruff check` clean, `pytest-cov` enabled
- Focus: Expanding vocab coverage, improving matching accuracy, preparing for UI

## What's Built

### Core Infrastructure
- `pyproject.toml` with full dependency management (runtime + dev extras)
- All `sys.path` hacks removed — clean editable install (`pip install -e ".[dev]"`)
- Alembic migrations scaffold with auto-schema reconciliation in `db/session.py`
- `ruff` linting (zero errors) with CI integration
- `pytest-cov` coverage reporting enabled by default
- Thread-safe `reconfigure()` for DB URL switching

### Inventory & Scanning
- `scripts/10_inventory/quick_scan.py` — read-only token frequency scan with directory tokenization, ignore lists, archive filename support, JSON reports
- `run_quick_scan.bat` — double-click convenience wrapper

### Vocab & Loaders (`scripts/20_loaders/`)
- **Designers**: `load_designers.py` — loads `vocab/designers_tokenmap.md` into DB
- **Franchises**: `load_franchises.py` — loads `vocab/franchises/*.json` with dedup support
- **Codex Units**: `load_codex_from_yaml.py` — loads 40K, AoS, Horus Heresy YAML (with raw_data preservation, aliases, base profiles)
- **Parts**: Same loader handles `wargear_w40k.yaml` and `bodies_w40k.yaml`
- **Collections**: `load_collections.py` — loads `vocab/collections/*.yaml` per-designer manifests
- **Lineages**: `load_lineages.py` — loads lineage vocabulary
- Sync scripts: `sync_franchise_tokens_to_vocab.py`, `sync_designers_from_tokenmap.py`, `sync_characters_to_vocab.py`

### Normalization & Matching (`scripts/30_normalize_match/`)
- **Normalizer**: `normalize_inventory.py` — deterministic metadata extraction (designer, faction, lineage, scale, franchise, character, etc.) with dry-run → apply
- **Unit matcher**: `match_variants_to_units.py` — context-aware scoring with mount/spell injection, kit-child support, timestamped JSON reports
- **Franchise matcher**: `match_franchise_characters.py` — conservative matching with OC inference (`--infer-oc`, `--infer-oc-fantasy`), strong/weak signal handling
- **Collections matcher**: `match_collections.py` — per-designer collection assignment from YAML manifests
- **Lineage matcher**: `match_lineages.py`
- **Parts matcher**: `match_parts_to_variants.py`
- **Backfill**: `backfill_english_tokens.py` — multilingual token translation (Spanish/CJK → English) with locale preservation, UI display label generation
- **Shared logic**: `scripts/lib/alias_rules.py` (shared alias gating), `scripts/lib/ui_display.py` (extracted UI display builder), `scripts/lib/constants.py` (shared constants), `scripts/lib/mmf_client.py` (MMF API with retry/backoff)

### Kit Management (`scripts/40_kits/`)
- Kit parent/child hierarchies via `parent_id`, `is_kit_container`, `kit_child_types`
- `backfill_kits.py` — creates virtual parents, links children, aggregates child types

### Cleanup & Repair (`scripts/50_cleanup_repair/`)
- 18 targeted repair scripts (prune invalid variants, repair orphans, remove `__MACOSX` duplicates, backfill scale/intended_use, fix cross-system matches, etc.)

### Reporting & Analysis (`scripts/60_reports_analysis/`)
- 25 inspection/report scripts (codex counts, franchise coverage, field stats, residual tokens, proposal filtering, variant debugging, etc.)

### Integrations (`scripts/10_integrations/`)
- `update_collections_from_mmf.py` — fetches MMF collections per designer with retry/backoff
- `vocab/mmf_usernames.json` — canonical designer → MMF username mapping

### API (`api/main.py`)
- FastAPI developer preview: `GET /health`, `GET /variants` (search/filter/paginate), `GET /variants/{id}` (detail with files)
- Full API spec in `docs/API_SPEC.md` with `[PLANNED]`/`[IMPLEMENTED]` labels

### DB Schema (`db/models.py`)
- Wide single-table `Variant` model (~60 columns, annotated by phase P0/P1/P2) — write-once, read-heavy design
- Supporting tables: `File`, `Archive`, `VocabEntry`, `Character`, `GameSystem`, `Faction`, `Unit`, `UnitAlias`, `Part`, `PartAlias`
- Association tables: `variant_unit_link`, `variant_part_link`, `unit_part_link`

### Test Suite (106 tests)
- **Unit tests**: match scoring (21), UI display (18), scale parsing, multilingual backfill, lineage depth bias, codex basing integrity, variant write
- **Workflow tests**: franchise match → apply, kits backfill, loaders + matchers, multilingual backfill, smoke workflow

### Documentation
- `docs/ARCHITECTURE.md` — system architecture, repo layout, flowchart
- `docs/CLI_REFERENCE.md` — full CLI commands with PowerShell examples
- `docs/API_SPEC.md` — REST API spec (draft, with PLANNED/IMPLEMENTED labels)
- `docs/SCHEMA_codex_and_linking.md` — schema and linking details
- `docs/FIX_PLAN.md` — codebase review fix plan (all 7 phases complete)
- `CHANGELOG.md` — release history
- `DECISIONS.md` — versioned rationale log

## Milestones & Epics
- [x] Schema: Variant/File base, GameSystem/Faction/Unit (+aliases)
- [x] Loader: Units YAML (40K/AoS/Heresy) with raw_data preservation
- [x] Tests: Basing integrity for 40K/AoS YAML
- [x] Parts model: `Part`, `PartAlias`, `VariantPartLink`, `UnitPartLink`
- [x] Loader: Parts ingestion for wargear + bodies YAML
- [x] Designers vocab externalized + loader
- [x] Franchise manifests + loader + matcher (dry-run/apply)
- [x] Collections SSOT + matcher (per-designer YAML)
- [x] Repo restructure (docs/ and vocab/ separation)
- [x] Quick Scan improvements (dirs, archives, JSON)
- [x] Kit containers: backfill + matcher/report collapse
- [x] Multilingual backfill (english_tokens + UI display labels)
- [x] Shared alias rules and constants extraction
- [x] Codebase review: all 7 phases completed (pyproject.toml, sys.path cleanup, ruff, tests, docs split, etc.)
- [x] MMF integration: collections fetch with retry/backoff
- [ ] Unit ↔ Part linking policy (seed curated compatibility rules)
- [ ] API expansion: unit/parts/franchise endpoints
- [ ] Web UI (React, static bundle)
- [ ] HH/AoS expansion: continue manifests with conservative legality and base profiles
- [ ] Packaging: PyInstaller EXE or portable zip

## Current Sprint / Focus
- Expand API endpoints (units, parts, search)
- Seed initial `UnitPartLink` compatibility rules for Space Marines
- Improve matching accuracy (refine scoring, reduce false positives)
- Begin UI scaffolding

## Dev Log (reverse chronological)
- 2026-02-22
  - Codebase review: completed all 7 fix phases (pyproject.toml, sys.path removal, constants extraction, kit dedup, backfill decomposition, ruff, gitignore, tests, utcnow fix, legacy cleanup, README split, pytest-cov, thread-safety, MMF retry)
  - 106 tests passing, ruff clean, coverage enabled
  - README trimmed to concise overview; extracted CHANGELOG.md, docs/ARCHITECTURE.md, docs/CLI_REFERENCE.md
  - API endpoints marked [PLANNED]/[IMPLEMENTED] in API_SPEC.md
- 2025-09-03
  - Documentation refreshed; loaders stable; matching/linking operational
  - Basing integrity and multilingual backfill verified
- 2025-09-02
  - Collections SSOT and matcher implemented (per-designer YAML)
  - MMF collections hardened (username map, non-designer pruning)
- 2025-08-31
  - Shared alias rules extracted to `scripts/lib/alias_rules.py`
  - Normalizer bigram aliasing and ambiguity gating unified
- 2025-08-30
  - Kit container modeling: parent/child schema, backfill, report collapse
- 2025-08-29
  - Parts model (Part, PartAlias, links) and wargear/bodies YAML ingestion
- 2025-08-28
  - Basing integrity tests stabilized; AoS YAML sweeps passing
- 2025-08-15 — 2025-08-16
  - Initial repo setup, vocab design, quick scan, franchise manifests, normalization planning

## Quick Commands (PowerShell)
See [CLI_REFERENCE.md](CLI_REFERENCE.md) for the full list.

```powershell
# Run all tests
.\.venv\Scripts\python.exe -m pytest

# Run linter
.\.venv\Scripts\python.exe -m ruff check .

# Start API server
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8077
```

## Useful Links
- [ARCHITECTURE.md](ARCHITECTURE.md) — system architecture and flowchart
- [CLI_REFERENCE.md](CLI_REFERENCE.md) — full CLI reference
- [SCHEMA_codex_and_linking.md](SCHEMA_codex_and_linking.md) — schema details
- [API_SPEC.md](API_SPEC.md) — API specification
- [FIX_PLAN.md](FIX_PLAN.md) — codebase review plan (complete)
- [DECISIONS.md](../DECISIONS.md) — rationale log

## Conventions
- Use ISO dates (YYYY-MM-DD) in the Dev Log.
- Prefer present tense, imperative style ("Add", "Fix", "Update").
- Keep this file focused on progress; deep rationale goes to `DECISIONS.md`.

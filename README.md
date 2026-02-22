# STL Manager

A local-first 3D model intelligence engine that inventories huge, messy model libraries and turns filename/folder chaos into structured, queryable data. It normalizes tokens, persists rich variant metadata, models kit hierarchies, and auto-links variants to tabletop game systems, factions, units, and characters — all with reviewable dry-run → apply workflows.

**Status**: Phase 1 active — deterministic normalization, matching, and linking are operational. Tabletop Units + Parts (40K/AoS/Heresy) YAML ingestion and DB linking available. Developer-preview API serving variant queries.

## Documentation

| Document | Description |
|----------|-------------|
| [PROGRESS.md](docs/PROGRESS.md) | Living project status, milestones, dev log |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, repository layout, flowchart |
| [CLI_REFERENCE.md](docs/CLI_REFERENCE.md) | Full CLI commands with PowerShell examples |
| [CHANGELOG.md](CHANGELOG.md) | Release history and notable changes |
| [API_SPEC.md](docs/API_SPEC.md) | REST API specification (draft) |
| [SCHEMA_codex_and_linking.md](docs/SCHEMA_codex_and_linking.md) | Schema and linking details |
| [WORKFLOW_TESTS.md](docs/WORKFLOW_TESTS.md) | Workflow tests (plain-English guide) |
| [SCRIPTS_ORGANIZATION.md](docs/SCRIPTS_ORGANIZATION.md) | Script organization by phase |
| [TECH_STACK_PROPOSAL.md](docs/TECH_STACK_PROPOSAL.md) | Full architecture rationale |
| [RESOURCES.md](docs/RESOURCES.md) | Resources and links |
| [DECISIONS.md](DECISIONS.md) | Versioned rationale & token_map_version log |

## Project Constraints

- 100% local, offline-friendly (no required external services / cloud).
- Free & open-source dependencies only.
- Windows 10 one-click startup target (no WSL / Docker required for baseline).
- Deterministic normalization before any probabilistic / ML features.

## Quick Start (Developer)

```powershell
Set-Location 'C:\path\to\STL-manager'
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Initialize DB
python scripts/00_bootstrap/bootstrap_db.py --db-url sqlite:///./data/stl_manager_v1.db --use-metadata

# Run tests
python -m pytest -q
```

For complete CLI commands including vocab loading, normalization, and matching, see [CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

## Phase Overview

| Phase | Focus | Status |
|-------|-------|--------|
| Phase 0 | Passive inventory, vocab design, quick scan | Complete |
| Phase 1 | Deterministic normalization, SQLite persistence, matching, API | **Active** |
| Phase 2 | Unit ↔ Part linking, API expansion, web UI | Next |
| Phase 3+ | Geometry hashing, dedupe, PyInstaller packaging | Future |

### Current Capabilities

- **Inventory**: Read-only token scan across file/folder names with JSON reports.
- **Vocab**: Modular YAML/JSON under `vocab/` — designers, franchises, codex units (40K/AoS/Heresy), parts (wargear/bodies), collections, lineages.
- **Normalization**: Deterministic metadata extraction (designer, faction, lineage, scale, franchise, character, etc.) with dry-run → apply.
- **Matching**: Context-aware unit/franchise/character/collection/lineage/parts matchers with timestamped JSON reports.
- **Kits**: Kit parent/child hierarchies with type classification and report collapse.
- **Multilingual**: Spanish/CJK token backfill to `english_tokens` with UI display label generation.
- **Cleanup**: 18 targeted repair scripts (orphans, duplicates, cross-system fixes, scale backfill, etc.).
- **API**: Developer-preview FastAPI — variant listing with search/filter and detail endpoints.
- **Tests**: 106 tests (unit + workflow), ruff linting, pytest-cov coverage.

## Terminology

| Term | Meaning |
|------|---------|
| Variant | A DB record representing a model folder; may contain files (STL/OBJ/etc.) |
| Kit | A variant that acts as a parent container for part packs |
| Codex / Vocab | Structured YAML/JSON under `vocab/` with units, factions, parts, and aliases |
| Dry-run | Execute logic, produce reports, but don't change the DB |
| Apply | Execute logic and persist changes to the DB |

## Safety Principles

- Deterministic passes only until precision validated (>95% target for designer + faction).
- No destructive file operations in early phases.
- External high-churn vocab kept isolated for low-noise diffs.
- No hidden network calls / telemetry.

## Contributing

1. Propose vocab additions via residual token frequency (quick_scan report).
2. Add new aliases to appropriate vocab file under `vocab/`.
3. Update `DECISIONS.md` (date, rationale, version bump if core map changed).
4. Re-run quick_scan to ensure new aliases collapse residual frequency.

## License

TBD (will be added before any public release). All current dependencies are open-source (MIT / Apache / BSD).

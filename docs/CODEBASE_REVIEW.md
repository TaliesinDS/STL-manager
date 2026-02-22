# Codebase Review — STL-Manager

**Date**: 2026-02-21  
**Scope**: Full repository review  
**Note**: The UI (`docs/ui/`) is a dirty mockup and is excluded from this review; it will be rebuilt with proper structure.

---

## 1. Project Overview

STL-Manager is a local-first 3D model intelligence engine that inventories large, messy STL/OBJ libraries and turns filename/folder chaos into structured, queryable data. The project is currently transitioning from Phase 0 (passive inventory) toward Phase 1 (deterministic normalization).

| Metric | Value |
|--------|-------|
| Python files | ~146 |
| Lines of Python | ~19,500 |
| Scripts (under `scripts/`) | ~118 |
| Franchise manifests | 215 JSON files |
| Collection manifests | 20 YAML files |
| Test files | 12 (6 unit + 6 workflow) |
| Alembic migrations | 9 |
| DB backup files in `data/` | 23 |
| Dependencies (runtime) | 7 packages |

---

## 2. Architecture & Design

### Strengths

- **Clear phased approach**: The project follows a deliberate Phase 0 → 1 → 2+ roadmap with gating on each stage. Destructive operations are deferred, and all matchers operate in dry-run mode by default. This is excellent engineering discipline.
- **Comprehensive domain model**: The `Variant` model captures a remarkably thorough set of metadata fields for a 3D model library — from NSFW tagging to tabletop basing profiles, kit hierarchies, multilingual support, and loadout codes.
- **Vocab-driven architecture**: Externalizing vocabulary (franchises, codex units, lineages, collections, designers) into `vocab/` keeps the codebase data-driven and extensible without code changes.
- **Dry-run/apply pattern**: Every mutation script follows a consistent dry-run-then-apply workflow that produces JSON reports for review. This is a strong safety pattern.
- **Self-documenting decisions**: `DECISIONS.md` logs every vocabulary or structural change with dates, rationale, and version bumps — valuable for a solo project.

### Concerns

- **No package configuration**: There is no `pyproject.toml`, `setup.py`, or `setup.cfg`. Every script that needs to import `db.*` or `scripts.lib.*` resorts to `sys.path.insert(0, ...)` hacks. This makes the codebase fragile, untestable in isolation, and impossible to install as a proper package. This is the single highest-priority structural fix.
- **Monolithic scripts**: The two largest scripts — `match_variants_to_units.py` (~900 lines) and `backfill_english_tokens.py` (~900 lines) — mix scoring logic, DB operations, CLI handling, and heuristic rules in a single file. These should be decomposed into a library layer (pure functions) and a thin CLI/DB layer.
- **No clear boundary between library and CLI**: Scripts under `scripts/` serve as both importable modules and CLI entrypoints. There is no `src/` or library package structure; shared logic lives only in `scripts/lib/` (2 files).

---

## 3. Data Layer (`db/`)

### Models (`db/models.py`)

- **124 columns on `Variant`** — this is an exceptionally wide table. While SQLite handles this fine, it makes the model difficult to reason about and impossible to present cleanly in an API without explicit projection. Consider grouping related columns into separate tables (e.g., `variant_nsfw`, `variant_tabletop`, `variant_compatibility`) or at minimum documenting which fields belong to which phase.
- Uses `Column(JSON, default=list)` and `Column(JSON, default=dict)` — the mutable default objects (`list`, `dict`) are shared across instances. SQLAlchemy handles this internally with copy-on-access for `default`, but this is a documented footgun. Prefer `default=lambda: []` or `default_factory` to be safe.
- **`datetime.utcnow`** is deprecated as of Python 3.12. Should use `datetime.now(timezone.utc)` or `func.now()` for server-side defaults.
- Good use of `cascade="all, delete-orphan"` on relationships and proper `ondelete` clauses on foreign keys.
- The `Lineage` model is well-designed with family/sublineage hierarchy and locale-aware aliases.

### Session (`db/session.py`)

- **Auto-schema-reconciliation on every session open**: `get_session()` performs table creation and column introspection on the first session per URL. This is clever for a prototype but:
  - Conflates session management with DDL operations.
  - The column-reconciliation code issues raw `ALTER TABLE` DDL — this bypasses Alembic entirely and could create migration drift.
  - The `_SCHEMA_VERIFIED` guard correctly prevents repeated reflection but relies on process-global state.
- The `reconfigure()` function mutates module-global `engine` and `SessionLocal` — this is not thread-safe. Multiple threads calling `reconfigure()` concurrently could produce undefined behavior.
- **Positive**: `NullPool` usage for SQLite avoids file locking issues, and `PRAGMA foreign_keys=ON` enforcement is correct.

### API (`api/main.py`)

- Minimal but functional FastAPI app with proper Pydantic models.
- **CORS `allow_origins=["*"]`** — acceptable for local-only use, but should be tightened before any network exposure.
- Uses `ilike` for search — SQLite's `LIKE` is case-insensitive by default only for ASCII characters; non-ASCII franchise/character names won't match case-insensitively.
- The `_to_summary` serializer accesses `v.updated_at.isoformat()` without null-checking the inner datetime — could raise `AttributeError` if `updated_at` is None. The `getattr` wrapping helps but the pattern is fragile.
- No pagination guard: `limit=500` allows large result sets. Consider a lower maximum or streaming.
- Only 3 endpoints (`/health`, `/variants`, `/variants/{id}`). The README and `API_SPEC.md` document many more planned endpoints.

---

## 4. Scripts

### Organization

The `scripts/` directory is well-organized into numbered phases:

| Phase | Directory | Purpose | Files |
|-------|-----------|---------|-------|
| 00 | `00_bootstrap/` | DB setup | 1 |
| 10 | `10_inventory/` | Filesystem scanning | 5 |
| 10 | `10_integrations/` | MMF API | 3 |
| 20 | `20_loaders/` | Data loading | 11 |
| 30 | `30_normalize_match/` | Core matching | 12 |
| 40 | `40_kits/` | Kit hierarchy | 3 |
| 50 | `50_cleanup_repair/` | Maintenance | 17 |
| 60 | `60_reports_analysis/` | Reports | 24 |
| 90 | `90_util/` | Developer tools | 4 |

**However**, the root of `scripts/` also contains 15+ loose files that appear to be compatibility shims forwarding to the numbered directories. A `scripts/maintenance/remove_root_shims.py` exists to clean these up — it should be run and the shims removed.

### Code Quality Highlights

**Positive patterns**:
- Consistently uses `argparse` with `--help` support across all CLI scripts.
- Dry-run/apply separation is uniform.
- JSON report output with timestamps for auditability.

**Issues found**:

1. **Major duplication in `match_variants_to_units.py`**: The "kit child enrichment" block (~80 lines) is copy-pasted twice — once for the `parent_id` path and once for the `kit_parent_rel` path. This should be extracted into a shared function.

2. **Major duplication in `backfill_english_tokens.py`**: The `build_ui_display()` function defines 8+ near-identical inner helper functions (`_norm`, `_norm_pre2`, `_norm_pre3`, `_norm_b`, `_norm_u`, `_norm_f`, `_normx`, `_normc`, `_norm_disp`). Additionally, `_translate_tokens_keep_dupes()` is a near-complete copy of `translate_tokens()` differing by one line.

3. **Hardcoded mappings duplicated across files**: The AoS leaf-faction-to-Grand-Alliance map and default scale dictionaries appear in both `match_variants_to_units.py` and `backfill_english_tokens.py`. These should be in a shared config or `scripts/lib/` constant.

4. **`sys.path` manipulation in every script**: Nearly every script in `scripts/` contains:
   ```python
   sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
   ```
   This is the symptom of not having a `pyproject.toml`.

5. **`quick_scan.py` uses Python 3.10+ syntax** (`str | None`, `list[str]`) without `from __future__ import annotations`. This will crash on Python 3.9, which is still within its support window.

6. **Generated reports committed in `scripts/reports/`**: 63 JSON report files are checked into the repo. The `.gitignore` covers `/reports/**/*.json` but not `scripts/reports/`. These should either be gitignored or moved out of version control.

### Security

- No SQL injection risks — all DB access uses SQLAlchemy ORM.
- `mmf_client.py` properly URL-encodes usernames before constructing URLs.
- No secrets are committed; `CONFIG.example.yaml` is clean.
- The YAML loader uses `allow_duplicate_keys = True` which silently absorbs data errors — not a security issue but a correctness concern.

---

## 5. Testing

### Coverage

| Test File | Type | Tests | Notes |
|-----------|------|-------|-------|
| `test_codex_basing_integrity.py` | Unit | ~10 | YAML structure validation |
| `test_lineage_depth_bias.py` | Unit | ~5 | Lineage classification |
| `test_scale_parsing.py` | Unit | ~8 | Scale token regex |
| `test_write_variant.py` | Manual | 1 | Requires live DB + env var; effectively dead |
| `test_multilingual_backfill.py` | — | 0 | Deprecated placeholder (empty file) |
| `workflow/test_smoke_workflow.py` | Integration | ~12 | Full pipeline |
| `workflow/test_franchise_match_apply.py` | Integration | ~5 | Franchise matching |
| `workflow/test_kits_backfill.py` | Integration | ~5 | Kit hierarchy |
| `workflow/test_loaders_and_matchers.py` | Integration | ~5 | Loader + matcher chain |
| `workflow/test_multilingual_backfill_workflow.py` | Integration | ~5 | Multilingual tokens |

### Strengths

- Workflow tests are comprehensive end-to-end integration tests using ephemeral DBs and real subprocesses.
- Idempotency verification is built into multiple tests (run twice, assert same result).
- Test fixtures use session-scoped temp databases.

### Critical Gaps

1. **No unit tests for the most complex scoring logic**: `match_variants_to_units.py` (mount detection, spell injection, chapter hints, faction path walking, score delta gating) has zero dedicated unit tests. This is the highest-risk untested code.
2. **No unit tests for `build_ui_display()` / `_choose_thing_name()`**: ~450 lines of deeply nested heuristics that generate user-facing labels, tested only through the integration path.
3. **No unit tests for `mmf_client.py`**: The HTML scraper and API client are completely untested.
4. **No unit tests for `classify_tokens()`** beyond lineage and scale — the main normalization function.
5. **No negative / edge-case tests**: No tests for franchise character matching edge cases, alias collision resolution, or ambiguous token handling.
6. **CI only runs 1 test file** (`test_codex_basing_integrity.py`). None of the workflow tests or other unit tests run in CI.
7. **No code coverage measurement** is configured anywhere.
8. **No linting/type-checking in CI** — no `ruff`, `mypy`, or `flake8` configured.

---

## 6. Alembic & Migrations

### State

9 migration files exist with inconsistent naming: `0001_canonical_initial.py` vs `20250830_*`, `20250902_*`, `20250903_*`. Multiple migrations from the same day (Sept 3, 2025) suggest rapid iteration.

### Issues

1. **Schema drift risk**: `db/session.py`'s auto-reconciliation issues `ALTER TABLE` DDL outside of Alembic, creating potential drift between Alembic history and actual schema.
2. **23 backup files in `data/`**: Manual backup accumulation (`.bak`, `.bak2`, ..., `.bak10`, timestamped `.bak.YYYYMMDD`) indicates reliance on manual snapshot management rather than a clean migration-only flow.
3. **Bootstrap script has a stamp-and-upgrade fallback**: `bootstrap_db.py` catches `IntegrityError` on `alembic upgrade head` and falls back to stamping the version table. This masks migration errors.
4. These backup and `.bak` files should be gitignored (they currently are via `/data/` rule, but this also hides the production DB from the repo).

---

## 7. Vocabulary & Data

### Franchise Manifests (215 files)

- Well-structured JSON with `canonical` name, `aliases`, `tokens` (strong_signals, weak_signals, stop_conflicts), and `characters`.
- Some files show inconsistent formatting (misaligned braces, trailing commas) suggesting manual editing without a JSON linter.
- Coverage is impressively broad: anime, comics, games, movies, TV.

### Codex Unit YAMLs

- Three game systems (40K, AoS, Horus Heresy) with factions, units, aliases, editions, base profiles.
- Parts (wargear + bodies) have dedicated YAML files.
- `lineages.yaml` (~700 lines) is an excellent SSOT with multilingual aliases and exclusion lists.

### tokenmap.md

- Version 11 with externalized designers and codex units.
- The Markdown-as-pseudo-YAML format is fragile — some section boundaries are ambiguous, making automated parsing unreliable. Consider migrating to proper YAML.

---

## 8. CI/CD & Tooling

### Current State

- **CI**: Single GitHub Actions workflow (`ci.yml`) on `windows-latest` with Python 3.11. Only runs `test_codex_basing_integrity.py`. Triggered only on changes to `vocab/`, the test file, requirements files, or the workflow itself.
- **No linting**: No `ruff`, `flake8`, `pylint`, `black`, or `isort` configured.
- **No type checking**: No `mypy` or `pyright` configuration.
- **No code formatting standard enforced**.
- **No pre-commit hooks**.

### Recommendations

- Expand CI to include workflow tests (they already work on Windows).
- Add `ruff` (or `flake8`) for linting and style enforcement.
- Add `mypy` with `--strict` gradually (start with `db/` and `scripts/lib/`).
- Configure `pytest-cov` for coverage measurement.

---

## 9. Documentation

### Strengths

- Exceptionally thorough documentation for a personal project: 25 markdown files in `docs/`, a detailed README, versioned decisions log, and dedicated workflow test guides.
- The README serves as both a user guide and developer reference with copy-paste PowerShell commands.
- Mermaid flowchart for the population/normalization pipeline.

### Weaknesses

- **README is ~500 lines and growing**: It serves as changelog, tutorial, CLI reference, architecture overview, and roadmap all in one. Consider splitting into separate files (CHANGELOG, CONTRIBUTING, ARCHITECTURE).
- **Some docs reference planned features as if implemented**: The API spec documents endpoints that don't exist yet in `api/main.py` (e.g., `/units/{id}/bundle`, proxy endpoints, loadout coverage). This should be clearly labeled as planned/unimplemented.
- **`PROGRESS.md` and `PLANNING.md`** were not read in this review but likely contain overlapping content with the README.

---

## 10. Configuration

- `CONFIG.example.yaml` contains only `db.url` and `redis.url`. Redis is not used anywhere in the codebase.
- No config loading code exists — scripts use `argparse` flags and `STLMGR_DB_URL` env var exclusively.
- The example config is aspirational rather than functional.

---

## 11. `.gitignore`

- **7 duplicate entries**: `__pycache__/`, `*.pyc`, `.env`, `.env.*`, `.vscode/`, `.idea/`, `.venv/`, `build/`, `dist/` all appear twice (original block + a copy block at the bottom).
- Missing entries:
  - `.pytest-tmp/` (created by workflow tests)
  - `scripts/reports/` (63 generated JSON files currently committed)
  - `*.pytest_cache/` at non-root levels

---

## 12. Priority Recommendations

### Critical (should fix before further feature work)

| # | Issue | Impact |
|---|-------|--------|
| 1 | **Add `pyproject.toml`** with proper package config | Eliminates all `sys.path` hacks, enables proper imports, makes testing reliable |
| 2 | **Expand CI to run all tests** | Prevents regressions — currently only 1 of 12 test files runs in CI |
| 3 | **Extract shared constants** (scale maps, faction maps) into `scripts/lib/constants.py` | Fixes duplication across 3+ files, prevents silent divergence |

### High (should address soon)

| # | Issue | Impact |
|---|-------|--------|
| 4 | **Add unit tests for scoring logic** in `match_variants_to_units.py` | The most complex and impactful code path has zero isolated tests |
| 5 | **Decompose `backfill_english_tokens.py`** — extract `build_ui_display()` into a testable module | ~450 lines of untested UI label heuristics |
| 6 | **Remove `sys.path` manipulation** from all scripts (after #1) | Fragile, IDE-hostile, hard to debug |
| 7 | **De-duplicate kit child enrichment** in `match_variants_to_units.py` | 80 lines copy-pasted twice |
| 8 | **Clean up `.gitignore`** duplicates; add `scripts/reports/` | 63 generated artifacts are in version control |
| 9 | **Add `ruff` config and CI linting** | Catches style issues, unused imports, security patterns |

### Medium (quality of life)

| # | Issue | Impact |
|---|-------|--------|
| 10 | Remove compatibility shims from `scripts/` root (run `remove_root_shims.py`) | Reduces confusion about canonical script locations |
| 11 | Replace `datetime.utcnow` with `datetime.now(timezone.utc)` in models | `utcnow` is deprecated in Python 3.12 |
| 12 | Add `from __future__ import annotations` to `quick_scan.py` | Fixes Python 3.9 compatibility |
| 13 | Remove or gitignore the 23 `.bak` files in `data/` | Repo clutter |
| 14 | Migrate `tokenmap.md` from Markdown-pseudo-YAML to proper YAML | Eliminates fragile parsing |
| 15 | Clean up `scripts/legacy/` — archive or delete migration-era artifacts | 6 files that are likely dead code |
| 16 | Remove `redis.url` from `CONFIG.example.yaml` until Redis is actually used | Misleading configuration |
| 17 | Split the README into focused documents (CHANGELOG, ARCHITECTURE, CLI_REFERENCE) | Current README is ~500 lines and growing |

### Low (nice to have)

| # | Issue | Impact |
|---|-------|--------|
| 18 | Add `pytest-cov` for coverage measurement | Quantify test gaps |
| 19 | Consider splitting `Variant` model (124 columns) into related tables | Better normalization, clearer domain boundaries |
| 20 | Add retry/backoff to `mmf_client.py` | Robustness for API integration |
| 21 | Thread-safety for `session.reconfigure()` | Prevents race conditions if API serves concurrent requests |
| 22 | Document which `Variant` fields belong to which project phase | Makes the wide model more approachable |

---

## 13. What's Working Well

This section is worth emphasizing — the codebase has strong foundations:

- **Safety-first philosophy**: Dry-run defaults, JSON proposals, timestamped reports, no destructive ops without `--apply`. This is better discipline than many production systems.
- **Domain richness**: The vocabulary system (franchises, lineages, codex units, designers, collections) is impressively comprehensive for a personal project. 215 franchise manifests with character aliases, 3 game systems with full unit rosters, lineage taxonomy with multilingual aliases.
- **Pragmatic testing**: The workflow tests cover the real end-to-end pipeline including idempotency checks. The test infrastructure (ephemeral DBs, subprocess runners) is well-designed.
- **Incremental evolution**: The DECISIONS log shows careful, versioned expansion. Token map versions, migration history, and the phased approach demonstrate thoughtful iteration.
- **Windows-first**: Unusual but deliberate — the project targets Windows 10 one-click startup. CI runs on `windows-latest`. All scripts use compatible paths and subprocess calls.

---

*Review conducted on 2026-02-21. UI (`docs/ui/`) excluded — noted as mockup pending rebuild.*

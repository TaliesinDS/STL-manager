# Codebase Review — Fix Plan

**Created**: 2026-02-22
**Updated**: 2026-02-22
**Source**: [CODEBASE_REVIEW.md](CODEBASE_REVIEW.md)

---

## Phase 1 — Critical: Package Structure & CI (Issues 1, 2, 6)

Phase 1 must come first because it unlocks clean imports, which enables the refactoring in Phase 2 and the unit tests in Phase 4.

### 1.1 Add `pyproject.toml` (Issue #1) — DONE

> Completed 2026-02-22.

- Created `pyproject.toml` with `setuptools` backend, all runtime + dev deps,
  `[tool.pytest.ini_options]` migrated from `pytest.ini`, package discovery for
  `db`, `scripts`, `api`.
- Added 15 `__init__.py` files (`scripts/`, all phase subdirectories, `scripts/lib/`,
  `scripts/dev/`, `scripts/diagnostics/`, `scripts/maintenance/`, `api/`).
- Installed with `pip install -e ".[dev]"` — ruff and pytest-cov now available.
- Python requirement set to `>=3.9` (matches active venv 3.9.5).
- All 19 tests pass (1 expected skip).

### 1.2 Remove all `sys.path` hacks (Issue #6) — DONE

> Completed 2026-02-22.

- Removed `sys.path.insert(0, ...)` from **42 files** across `alembic/`,
  `tests/`, `scripts/` and all subdirectories.
- Kept `ROOT`/`PROJECT_ROOT` variables where still needed for locating
  `vocab/`, `reports/`, or data directories on disk.
- Fixed 4 incorrect `.parent.parent` → `.parents[2]` path calculations
  (`apply_proposals_from_report`, `apply_vocab_matches`, `find_vocab_matches`,
  `match_parts_to_variants`).
- Removed unused `import sys` in files where it was only used for the path hack.
- All 19 tests pass (1 expected skip), zero `sys.path.insert` calls remain.

### 1.3 Expand CI (Issue #2) — DONE

> Completed 2026-02-22.

- Broadened `paths:` trigger to include `scripts/**`, `db/**`, `api/**`, `tests/**`, `vocab/**`, `pyproject.toml`.
- Changed install step to `pip install -e ".[dev]"` (uses `pyproject.toml`).
- Added lint step: `ruff check .`.
- Added `pytest-cov` coverage reporting (`--cov=db --cov=scripts --cov=api`).
- Deleted `pytest.ini` (config already in `pyproject.toml`).
- All 19 tests pass (1 expected skip).

---

## Phase 2 — High: Deduplication & Refactoring (Issues 3, 5, 7)

### 2.1 Extract shared constants (Issue #3) — DONE

> Completed 2026-02-22.

- Created `scripts/lib/constants.py` with `NOISE_FILENAMES`, `KIT_CHILD_TOKENS`,
  `KIT_PARENT_HINTS`, `DEFAULT_SCALE_MAP`, `AOS_FACTION_TOKENS`.
- Updated 5 consumer files to import from the shared module instead of
  defining constants locally.
- All 19 tests pass.

### 2.2 De-duplicate kit child enrichment (Issue #7) — DONE

> Completed 2026-02-22.

- Extracted `_enrich_kit_child(v, parent_v, session, args)` in
  `match_variants_to_units.py` (~130 lines of shared logic).
- Replaced two ~140-line copy-pasted blocks (parent_id path and
  kit_parent_rel path) with calls to the new helper.
- Reconciled minor drift between the two blocks (pre-computing `v_norm`,
  using `new_fp[-1]` consistently, adopting the safer `faction_general`
  guard, and including the `codex_faction` ensure block).
- Net reduction: ~250 lines removed.
- All 19 tests pass.

### 2.3 Decompose `backfill_english_tokens.py` (Issue #5) — DONE

> Completed 2026-02-22.

- Extracted `build_ui_display()`, `_choose_thing_name()`, and 15 helper
  functions/constants into `scripts/lib/ui_display.py` (~720 lines).
- Collapsed 8+ near-identical `_norm*` lambdas into a single `_norm_label()`
  function shared by all comparison sites.
- Merged `_translate_tokens_keep_dupes()` into `translate_tokens()` via a new
  `dedup=False` keyword argument — removed ~60 lines of duplicated translation
  logic.
- Used `importlib.util.spec_from_file_location` for the lazy cross-reference
  between `ui_display.py` and `backfill_english_tokens.py` (numeric-prefixed
  package directories can't use dotted imports).
- `backfill_english_tokens.py` reduced from 1 491 to 527 lines (−965 lines).
- All 19 tests pass.

---

## Phase 3 — High: Tooling & Hygiene (Issues 8, 9)

### 3.1 Clean up `.gitignore` (Issue #8) — DONE

> Completed 2026-02-22.

- Removed 7 duplicate entries (`__pycache__/`, `*.pyc`, `.env`, `.env.*`, `.vscode/`, `.idea/`, `.venv/`, `build/`, `dist/`).
- Added `scripts/reports/`, `.pytest-tmp/`, `**/.pytest_cache/`, `data/*.bak*`, `*.egg-info/`.
- TODO: Run `git rm -r --cached scripts/reports/` to untrack report artifacts.

### 3.2 Add `ruff` config and CI linting (Issue #9) — DONE

> Completed 2026-02-22.

- Added `[tool.ruff]` config to `pyproject.toml` (target-version `py39`, line-length 120).
- Selected rules: E, F, W, I, UP, S with pragmatic ignores for high-volume pre-existing issues.
- Excluded `scripts/60_reports_analysis` and `scripts/legacy` (syntax compat issues).
- Ran `ruff check . --fix` — auto-fixed 379 trivial issues (unused imports, whitespace, etc.).
- Manually fixed remaining 27 issues (unused vars, None comparisons, tab indentation, ambiguous names).
- `ruff check .` now passes cleanly (zero errors).
- Lint step added to CI workflow (done as part of 1.3).

---

## Phase 4 — High: Testing (Issue #4)

### 4.1 Unit tests for scoring logic — DONE

> Completed 2026-02-22.

- Created `tests/test_match_scoring.py` (21 tests).
- Covers `norm_text`, `system_hint`, `find_chapter_hint`, `_has_marine_context`,
  `detect_mount_context`, `apply_mount_bias`, `detect_spell_context`,
  `detect_aos_faction_hint`, `score_match`, `_path_segments`,
  and `find_best_matches` (including mount injection & spell injection).
- Uses `importlib.util.spec_from_file_location` to load the module from its
  numeric-prefix directory.
- All 21 tests pass.

### 4.2 Unit tests for UI display logic — DONE

> Completed 2026-02-22.

- Created `tests/test_ui_display.py` (18 tests).
- Covers `_split_words`, `_clean_words`, `_title_case`, `_norm_label`,
  `_is_bucket_phrase`, `_is_packaging_segment`, `_best_named_segment_from_path`,
  `_choose_thing_name`, and `build_ui_display`.
- Uses a stub `translate_tokens` (identity function) seeded into `sys.modules`
  to avoid loading the real backfill module and its DB dependencies.
- All 18 tests pass.

29. Both test files are auto-discovered by pytest via `testpaths = ["tests"]`
    in `pyproject.toml` — no CI changes needed.

---

## Phase 5 — Medium: Code Quality Fixes (Issues 10–16)

### 5.1 Remove root shims (Issue #10) — DONE

> Completed 2026-02-22.

- Deleted 17 standalone shim scripts from `scripts/` root (e.g., `show_variant.py`,
  `assign_codex_units_aos.py`, `debug_matching_state.py`, all `inspect_*`, `report_*`,
  `dump_*`, `variant_field_stats.py`, etc.).
- Kept `normalize_inventory.py` and `quick_scan.py` as import facades — they are
  imported by 17+ files across the codebase (tests, normalizers, loaders).
- Deleted `scripts/maintenance/remove_root_shims.py` (no longer needed).
- No imports or references broke — the deleted shims were standalone entry points only.
- All 106 tests pass.

### 5.2 Fix `datetime.utcnow` deprecation (Issue #11) — DONE

> Completed 2026-02-22.

- Replaced all 21 `datetime.utcnow` usages in `db/models.py` with
  `lambda: datetime.now(datetime.UTC)` (18 `default=`, 3 `onupdate=`).
- Fixed 1 additional occurrence in `scripts/30_normalize_match/match_variants_to_units.py`.
- Ruff auto-fixed `timezone.utc` → `datetime.UTC` alias (UP017, valid for
  target-version `py311`).
- Removed unused `timezone` imports.
- All 106 tests pass, `ruff check .` clean.

### 5.3 Fix Python 3.9 compat in `quick_scan.py` (Issue #12) — DONE (pre-existing)

> Already resolved — `from __future__ import annotations` was present at line 38.
> Target Python version has also been updated to `>=3.11` in `pyproject.toml`,
> making the union syntax natively valid.

### 5.4 Gitignore `.bak` files (Issue #13) — DONE (pre-existing)

> Already resolved — `data/*.bak*` was already present in `.gitignore`.

### 5.5 Remove `redis.url` from config (Issue #16) — DONE

> Completed 2026-02-22.

- Removed the `redis:` section from `CONFIG.example.yaml`.
- No code references redis config; only documentation mentions it as an
  optional future upgrade path.

### 5.6 Clean up `scripts/legacy/` (Issue #15) — DONE

> Completed 2026-02-22.

- Confirmed all 6 files are dead code (migration-era artifacts, no imports
  or references outside docs).
- Deleted `scripts/legacy/` directory entirely.
- All 106 tests pass.

---

## Phase 6 — Medium: Documentation & Architecture (Issue #17)

### 6.1 Split README — DONE

> Completed 2026-02-22.

- Extracted changelog ("What's new" sections) into `CHANGELOG.md` at repo root.
- Extracted architecture overview, repository layout, flowchart, and runtime
  deps into `docs/ARCHITECTURE.md`.
- Extracted all CLI commands, PowerShell examples, loader/matcher/scan
  workflows, and MMF integration into `docs/CLI_REFERENCE.md`.
- Rewrote `README.md` as a concise overview (~90 lines) with a documentation
  table linking to all sub-documents.
- Marked all unimplemented API endpoints in `docs/API_SPEC.md` with `[PLANNED]`
  labels. The two implemented endpoints (`GET /variants`, `GET /variants/{id}`)
  are marked `[IMPLEMENTED]`.
- All 106 tests pass.

---

## Phase 7 — Low: Nice-to-Have (Issues 18–22)

### 7.1 Add `pytest-cov` (Issue #18) — DONE

> Completed 2026-02-22.

- `pytest-cov` already in dev dependencies.
- Added `[tool.coverage.run]` and `[tool.coverage.report]` to `pyproject.toml`.
- Added `--cov=db --cov=scripts --cov=api --cov-report=term-missing` to
  `[tool.pytest.ini_options] addopts`.
- Removed stale `scripts/legacy` from ruff exclude list.
- All 106 tests pass with coverage reporting.

### 7.2 Document Variant field phases (Issue #22) — DONE

> Completed 2026-02-22.

- Added inline phase section comments (`── P0:`, `── P1:`, `── P2:`) to
  `db/models.py` grouping all ~60 Variant columns by implementation phase.
- P0: identity, inventory, timestamps, residuals.
- P1: normalized metadata, tabletop/franchise, lineage, classification,
  tagging, multilingual, kit relationships.
- P2: addon/compatibility fields.
- All 106 tests pass.

### 7.3 Thread-safety for `reconfigure()` (Issue #21) — DONE

> Completed 2026-02-22.

- Added `_reconfigure_lock = threading.Lock()` in `db/session.py`.
- Wrapped the entire `reconfigure()` body in `with _reconfigure_lock:`.
- All 106 tests pass.

### 7.4 `mmf_client.py` retry/backoff (Issue #20) — DONE

> Completed 2026-02-22.

- Added exponential backoff retry (3 retries, 1s/2s/4s delays) to
  `_http_request()` in `scripts/lib/mmf_client.py`.
- Client errors (4xx except 429) fail immediately without retry.
- Server errors (5xx), rate limits (429), and network errors trigger retry.
- Logs warnings via `logging` module on each retry attempt.
- All 106 tests pass, `ruff check .` clean.

### 7.5 Consider splitting `Variant` model (Issue #19) — DONE (documented)

> Completed 2026-02-22.

- Documented trade-offs and deferral rationale in `DECISIONS.md` (2026-02-22 entry).
- Decision: defer to Phase 2+. Current single-table design is acceptable for
  SQLite at current scale. Phase annotations (P0/P1/P2) in `db/models.py`
  guide a future split if needed.

---

## Dependency Graph

```
Phase 1 (pyproject.toml, sys.path, CI)
  │
  ├──► Phase 2 (extract constants, deduplicate, decompose)
  │      │
  │      └──► Phase 4 (unit tests for extracted functions)
  │
  ├──► Phase 3 (gitignore, ruff)
  │
  └──► Phase 5 (utcnow, compat, shims, legacy cleanup)
         │
         └──► Phase 6 (docs restructure)
                │
                └──► Phase 7 (nice-to-have)
```

## Execution Priority

| Order | Phase | Effort | Description | Status |
|-------|-------|--------|-------------|--------|
| 1st | Phase 1 | High | `pyproject.toml`, remove sys.path hacks, expand CI | **DONE** |
| 2nd | Phase 3.1 | Low | `.gitignore` cleanup | **DONE** |
| 3rd | Phase 2 | High | Extract constants, deduplicate, decompose monoliths | **DONE** |
| 4th | Phase 3.2 | Low | `ruff` config | **DONE** |
| 5th | Phase 4 | Medium | Unit tests for scoring + UI display | **DONE** |
| 6th | Phase 5 | Low | `utcnow`, compat, config, shims, legacy | **DONE** |
| 7th | Phase 6 | Low | README split, API spec labels | **DONE** |
| 8th | Phase 7 | Low | Coverage, thread safety, retry, model split | **DONE** |

# Codebase Review — Fix Plan

**Created**: 2026-02-22
**Source**: [CODEBASE_REVIEW.md](CODEBASE_REVIEW.md)

---

## Phase 1 — Critical: Package Structure & CI (Issues 1, 2, 6)

Phase 1 must come first because it unlocks clean imports, which enables the refactoring in Phase 2 and the unit tests in Phase 4.

### 1.1 Add `pyproject.toml` (Issue #1)

1. Create `pyproject.toml` at repo root with:
   - `[build-system]` using `hatchling` or `setuptools`
   - `[project]` with name `stl-manager`, version, Python `>=3.10`
   - `[project.dependencies]` — migrate entries from `requirements.txt`
   - `[project.optional-dependencies]` — `dev = ["pytest>=8.4", "ruff", "pytest-cov"]`
   - `[tool.pytest.ini_options]` — migrate config from `pytest.ini`
   - `[tool.ruff]` — see Phase 3.2
   - Package discovery covering `db`, `scripts`, `api`
2. Add `__init__.py` to every package/sub-package that lacks one:
   - `scripts/`
   - Each phase subdirectory (`00_bootstrap/`, `10_inventory/`, `10_integrations/`, `20_loaders/`, `30_normalize_match/`, `40_kits/`, `50_cleanup_repair/`, `60_reports_analysis/`, `90_util/`)
   - `scripts/lib/`
   - `api/` (if missing)
3. Run `pip install -e .` in the venv to make the project importable as a package.

### 1.2 Remove all `sys.path` hacks (Issue #6)

4. Grep for `sys.path.insert` across `scripts/`, `alembic/`, `tests/`, `api/`.
5. Remove each `sys.path.insert(0, ...)` block **and** its associated `PROJECT_ROOT`/`ROOT` path calculation when used solely for import resolution.
6. Update any relative imports that relied on the sys.path hack to use absolute package imports (e.g., `from db.session import get_session`).
7. Run full test suite to verify nothing broke.

### 1.3 Expand CI (Issue #2)

8. Edit `.github/workflows/ci.yml`:
   - Broaden `paths:` trigger to include `scripts/**`, `db/**`, `api/**`, `tests/**`.
   - Change install step to `pip install -e ".[dev]"` (uses `pyproject.toml`).
   - Run **all** tests: `python -m pytest tests/ -q`.
   - Add a lint step: `ruff check .`.
   - Optionally add `pytest-cov` coverage reporting.
9. Delete `pytest.ini` after migrating its config to `pyproject.toml`.

---

## Phase 2 — High: Deduplication & Refactoring (Issues 3, 5, 7)

### 2.1 Extract shared constants (Issue #3)

10. Create `scripts/lib/constants.py` containing:
    - `AOS_FACTION_TO_GRAND_ALLIANCE: dict[str, str]` — the map currently in `match_variants_to_units.py` (~line 368).
    - `DEFAULT_SCALE_MAP: dict` — any duplicated scale mappings.
    - `AOS_FACTION_TOKENS: list[str]` — the faction hint tokens.
    - `KIT_CHILD_TOKENS: set[str]` — the set used for kit detection.
    - `NOISE_FILENAMES: set[str]` — OS noise files set.
11. Update all files that define these locally to import from `scripts.lib.constants`.
12. Run tests to verify.

### 2.2 De-duplicate kit child enrichment (Issue #7)

13. In `scripts/30_normalize_match/match_variants_to_units.py`, identify the two copy-pasted ~80-line blocks (once for the `parent_id` path, once for the `kit_parent_rel` path).
14. Extract into a shared function, e.g.:
    ```python
    def _enrich_kit_child(variant, parent_variant, session) -> dict:
        ...
    ```
15. Replace both call sites with calls to the extracted function.

### 2.3 Decompose `backfill_english_tokens.py` (Issue #5)

16. Read `scripts/30_normalize_match/backfill_english_tokens.py` fully to map function boundaries.
17. Extract `build_ui_display()` and `_choose_thing_name()` into a new module `scripts/lib/ui_display.py`.
18. Collapse the 8+ near-identical `_norm*` helper functions into 1–2 parameterized functions.
19. Replace `_translate_tokens_keep_dupes()` with the existing `translate_tokens()` plus a flag parameter (e.g., `keep_dupes=True`).
20. Update `backfill_english_tokens.py` to import from the new module.
21. Run tests.

---

## Phase 3 — High: Tooling & Hygiene (Issues 8, 9)

### 3.1 Clean up `.gitignore` (Issue #8)

22. Edit `.gitignore`:
    - Remove the 7 duplicate entries (second copy of `__pycache__/`, `*.pyc`, `.env`, `.env.*`, `.vscode/`, `.idea/`, `.venv/`, `build/`, `dist/`).
    - Add `scripts/reports/` to gitignore generated report artifacts.
    - Add `.pytest-tmp/`.
    - Add `**/.pytest_cache/`.
23. Remove tracked report files: `git rm -r --cached scripts/reports/`.

### 3.2 Add `ruff` config and CI linting (Issue #9)

24. Add `[tool.ruff]` section to `pyproject.toml`:
    ```toml
    [tool.ruff]
    target-version = "py310"

    [tool.ruff.lint]
    select = ["E", "F", "W", "I", "UP", "S"]

    [tool.ruff.lint.per-file-ignores]
    "scripts/legacy/*" = ["ALL"]
    ```
25. Run `ruff check . --fix` to auto-fix trivial issues.
26. Add `ruff check .` step to CI workflow (done as part of 1.3).

---

## Phase 4 — High: Testing (Issue #4)

### 4.1 Unit tests for scoring logic

27. Create `tests/test_match_scoring.py`:
    - Test `system_hint()` with various inputs.
    - Test mount detection logic.
    - Test spell injection matching.
    - Test chapter hints / faction path walking.
    - Test score delta gating.
    - Test the full `score_candidate()` function with synthetic data.

### 4.2 Unit tests for UI display logic

28. Create `tests/test_ui_display.py` (depends on Phase 2.3 extraction):
    - Test `build_ui_display()` with known variant metadata.
    - Test `_choose_thing_name()` edge cases.
    - Test tokenization variants, comma handling, prefix stripping.

29. Ensure these new tests are picked up by the CI test run.

---

## Phase 5 — Medium: Code Quality Fixes (Issues 10–16)

### 5.1 Remove root shims (Issue #10)

30. Review `scripts/maintenance/remove_root_shims.py` to understand what it does.
31. Identify the ~15 shim files in `scripts/` root (e.g., `normalize_inventory.py`, `quick_scan.py`, `show_variant.py`, etc.).
32. Run `remove_root_shims.py` or manually delete the shims.
33. Update any imports or references that used the shim paths.

### 5.2 Fix `datetime.utcnow` deprecation (Issue #11)

34. In `db/models.py`, replace all `datetime.utcnow` with `datetime.now(timezone.utc)`:
    ```python
    # Before
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # After
    from datetime import timezone
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    ```
35. Grep for any other `utcnow` usage across the codebase and fix.

### 5.3 Fix Python 3.9 compat in `quick_scan.py` (Issue #12)

36. Check `scripts/10_inventory/quick_scan.py` for `str | None`, `list[str]` union syntax.
37. Add `from __future__ import annotations` at the top (or convert to `Optional[str]`, `List[str]`).

### 5.4 Gitignore `.bak` files (Issue #13)

38. Add `data/*.bak*` to `.gitignore`.
39. Run `git rm --cached data/*.bak*` to remove from tracking (**confirm with user first** — 23 backup files).

### 5.5 Remove `redis.url` from config (Issue #16)

40. Edit `CONFIG.example.yaml` — remove the `redis:` section entirely.

### 5.6 Clean up `scripts/legacy/` (Issue #15)

41. Review each file in `scripts/legacy/` — 6 files:
    - `apply_proposals_to_v1.py`
    - `create_and_stamp.py`
    - `gen_migration_from_metadata.py`
    - `inspect_sqlite.py`
    - `migrate_add_columns.py`
    - `set_alembic_version.py`
42. Confirm all are dead code (migration-era artifacts).
43. Delete or move to an archive branch.

---

## Phase 6 — Medium: Documentation & Architecture (Issue #17)

### 6.1 Split README

44. Extract changelog section from `README.md` into `CHANGELOG.md`.
45. Extract architecture overview into `docs/ARCHITECTURE.md`.
46. Extract CLI reference into `docs/CLI_REFERENCE.md`.
47. Keep `README.md` as a concise project overview with links to the sub-documents.
48. Mark unimplemented API endpoints in `docs/API_SPEC.md` with `[PLANNED]` labels.

---

## Phase 7 — Low: Nice-to-Have (Issues 18–22)

### 7.1 Add `pytest-cov` (Issue #18)

49. Add `pytest-cov` to dev dependencies.
50. Add `[tool.coverage]` config to `pyproject.toml`.
51. Add `--cov=db --cov=scripts --cov-report=term-missing` to pytest defaults.

### 7.2 Document Variant field phases (Issue #22)

52. Add inline comments in `db/models.py` grouping fields by phase (P0, P1, P2).
53. Or create a `docs/MODEL_FIELDS.md` reference document.

### 7.3 Thread-safety for `reconfigure()` (Issue #21)

54. Add a `threading.Lock` around the global mutation in `db/session.py`'s `reconfigure()`:
    ```python
    _reconfigure_lock = threading.Lock()

    def reconfigure(db_url: str) -> None:
        with _reconfigure_lock:
            global DB_URL, engine, SessionLocal
            ...
    ```

### 7.4 `mmf_client.py` retry/backoff (Issue #20)

55. Add basic retry logic with exponential backoff to `scripts/lib/mmf_client.py` for HTTP requests.

### 7.5 Consider splitting `Variant` model (Issue #19)

56. This is a large architectural change — defer to a dedicated design phase. Document the intent and trade-offs as a future consideration in `DECISIONS.md`.

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

| Order | Phase | Effort | Description |
|-------|-------|--------|-------------|
| 1st | Phase 1 | High | `pyproject.toml`, remove sys.path hacks, expand CI |
| 2nd | Phase 3.1 | Low | `.gitignore` cleanup |
| 3rd | Phase 2 | High | Extract constants, deduplicate, decompose monoliths |
| 4th | Phase 3.2 | Low | `ruff` config |
| 5th | Phase 4 | Medium | Unit tests for scoring + UI display |
| 6th | Phase 5 | Low | `utcnow`, compat, config, shims, legacy |
| 7th | Phase 6 | Low | README split, API spec labels |
| 8th | Phase 7 | Low | Coverage, thread safety, retry, model split |

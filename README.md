# STL Manager

Personal project to inventory and eventually manage a very large 3D model library (STL, OBJ, slicer project files, preview images, nested archives) using conservative, deterministic normalization phases.

Status: Phase 0 (passive inventory & vocabulary design) transitioning toward Phase 1 (deterministic low‑risk normalization).

Project Constraints (baseline):
- 100% local, offline-friendly (no required external services / cloud).
- Free & open-source dependencies only.
- Windows 10 one‑click startup target (no WSL / Docker required for baseline).
- Deterministic normalization before any probabilistic / ML features.

See `docs/TECH_STACK_PROPOSAL.md` (rev 1.1) for full architecture rationale.

## Repository Layout (2025-08-16 Restructure)

```
docs/         Planning & specifications (API_SPEC, MetadataFields, NormalizationFlow, PLANNING, DesiredFeatures, TECH_STACK_PROPOSAL)
vocab/        Modular vocab files (tokenmap, designers_tokenmap, codex_units_*.md, franchises/ manifests)
scripts/      Utility / exploratory scripts (quick_scan.py, one_click_start_template.bat, future normalization passes)
prompts/      Reusable prompt/style definition assets (e.g., bernadette_banner_style_prompt.txt)
DECISIONS.md  Versioned rationale & token_map_version change log
README.md     This file
```

All large / high‑churn vocab domains (designers, codex unit lists) are externalized under `vocab/` so diffs stay readable and expansion doesn’t obscure structural taxonomy changes. Core token map (`vocab/tokenmap.md`) contains only stable, high-signal mappings plus sentinels:

```
designers: external_reference
codex_units: external_reference
```

`quick_scan.py` automatically prefers `vocab/` paths (falls back to legacy root only with a warning – root duplicates have now been removed).

## Phase 0 Goals

Current Focus:
- Map existing extracted files (no archive extraction yet).
- Produce simple inventory (path, size, extension, depth, archive flag) – script spec in planning.
- Curate conservative vocab & precedence ordering before any automated writes.

Out of Scope (Now): archive extraction, geometry analytics (volume, height), dedupe / renames, probabilistic tagging, web UI, mesh thumbnails.

Next Micro Goal: Implement read-only inventory scan (CSV + JSONL) feeding future normalization passes.

Upcoming Near Sequence (High-Level):
1. Refactor scan + introduce ruleset digest & tests.
2. Implement normalization engine + SQLite persistence + API (variants, vocab, overrides, jobs sync).
3. Add in‑process job queue + SSE progress.
4. Bundle minimal React UI as static assets (list + filters + override editing).
5. Introduce audit logging & FTS search facets.
6. (Optional) PyInstaller single‑EXE packaging.
7. Geometry hashing (opt‑in) & dedupe suggestions.

## Quick Exploratory Token Scan (Planning Aid)

Added `scripts/quick_scan.py` to surface high-frequency filename tokens and highlight potential new metadata dimensions you might have overlooked (designers, factions, scale denominators, lineage families, variant cues).

PowerShell example:

```
python scripts/quick_scan.py --root D:\Models --limit 60000 --extensions .stl .obj .chitubox .lys --json-out quick_scan_report.json
```

With dynamic vocab from tokenmap (recommended after updates to `vocab/tokenmap.md`):

```
python scripts/quick_scan.py --root D:\Models --tokenmap vocab\tokenmap.md --json-out quick_scan_report.json
```

Double‑click option:
- Copy `quick_scan.py` and `run_quick_scan.bat` into any folder (or subfolder) you want to scan.
- Double click `run_quick_scan.bat` -> it treats that folder as root and writes `quick_scan_report.json` there.
- Omit `--root` / `--json-out` manually: script defaults root to its own directory and output file to `quick_scan_report.json`.

What it does (Phase 0 safe):
- Recurses files (no archive extraction) honoring extension filter.
- Splits stems (and now directory names) on `_ - space` unless `--skip-dirs` provided.
- Optionally loads designers / lineage / faction aliases / stopwords from `vocab/tokenmap.md` via `--tokenmap` (falls back to embedded defaults if parsing fails). Designers list auto-loads from `vocab/designers_tokenmap.md` if present (or legacy root with warning).
- Supports ignore list & domain summary via `--ignore-file` (newline tokens, `#` comments) and `--emit-known-summary` to print counts of classified domains and suppress noisy frequent known/ambiguous tokens from the unknown list.
	- If `--ignore-file` is omitted the script auto-loads `ignored_tokens.txt` from the scripts directory when present.
- Optional `--include-archives` adds archive filenames (.zip .rar .7z .cbz .cbr) to token stream (still no extraction) and reports `scanned_archives` in JSON.
- Counts token frequencies and classifies against a minimal embedded vocab subset (sync with `tokenmap.md`).
- Prints top unknown tokens (candidates for expansion into designer aliases, factions, lineage, style, etc.).
- Highlights scale ratio / mm tokens and numeric-containing tokens (pose, version, base size hints).
- Suggests review actions.

What it does NOT do:
- No writes / renames / DB mutations.
- No geometry parsing.
— JSON optional (use --json-out). Without it: stdout only. Redirect if desired:

```
python scripts/quick_scan.py --root D:\Models > quick_scan_report.txt
```

## Planned Scripts / Roadmap

Near Term:
- inventory_scan.py (Phase 0) – produce CSV/JSONL inventory.
- vocab_loader.py – aggregate & validate all `vocab/*.md` (collision + ambiguity checks).
- normalization_passes/ (Phase 1) – deterministic field extraction (designer, faction/system, lineage_family, variant axes, NSFW coarse, intended_use, pc_candidate_flag, scale).

Phase 2 Seeds (Gated):
- Unit extraction using codex_units_* lists (`enable_unit_extraction` flag + contextual activation).
- Tabletop-specific planned fields (equipment_type, base_size_mm, unit_role) once tabletop intent reliably detected.

Phase 3+ Ideas:
- Geometry hashing & dedupe, mesh measurements, override-aware re-normalization jobs.
- Web UI for browsing, override layering, residual token mining.
- (Optional) Postgres / Redis upgrade if local scale or concurrency needs exceed SQLite + thread pool.

## Quick Start (Baseline One‑Click – Planned)
Until the packaged batch script is finalized the following outlines intended behavior:

1. Clone / download repo (or portable release zip when available).
2. Double‑click `scripts/one_click_start_template.bat` (will be copied / renamed to `start_stl_manager.bat` in releases).
	- Creates `.venv` if absent.
	- Installs pinned dependencies from `requirements.txt` (generated from `poetry.lock` / pyproject).
	- Launches FastAPI server on `http://127.0.0.1:8077/` and opens default browser.
3. Use future UI (when added) or CLI commands (to be added under `stlmgr` Typer entrypoint) for scan & normalization.

Nothing is installed globally; deleting the folder removes everything (idempotent local footprint).

## Minimal Runtime Dependencies
Baseline (Phase 1) runtime requires only the embedded Python environment (or forthcoming single EXE) and SQLite (bundled with Python). Optional extras (only when enabled):
- Geometry: `trimesh`, `meshio` (installed via extras or included in EXE variant).
- Postgres / Redis: NOT required; upgrade path only.

## Local Configuration (Planned)
Future `CONFIG.yaml` (or `.env`) will define:
```
api_port: 8077
api_key: YOUR_LOCAL_KEY
db_path: data/stl_manager.sqlite
log_level: info
geometry_enabled: false
```
If absent, safe defaults are used (single‑user mode, generated API key optional for initial prototype).

## DECISIONS & Versioning
Every vocabulary or structural change is logged in `DECISIONS.md` referencing `token_map_version`. External vocab additions that don’t modify core sentinel structure may omit a version bump (noted explicitly).

## Contributing / Extending (Internal Workflow)
1. Propose vocab additions via residual token frequency (quick_scan report).
2. Add new aliases to appropriate vocab file under `vocab/`.
3. Update `DECISIONS.md` (date, rationale, version bump if core map changed).
4. Re-run quick_scan to ensure new aliases collapse residual frequency.

## Safety Principles
- Deterministic passes only until precision validated (>95% target for designer + faction).
- No destructive file operations in early phases.
- External high-churn vocab kept isolated for low-noise diffs.
- No hidden network calls / telemetry.

## Architecture Snapshot (Concise)
| Layer | Baseline | Notes |
|-------|----------|-------|
| Inventory & Normalization | Pure Python functions | Deterministic, versioned ruleset digest |
| Persistence | SQLite (WAL, FTS5) | Single file portable, no service install |
| API | FastAPI (Uvicorn) | Single process, SSE for job progress |
| Jobs | Thread pool (in‑proc) | SQLite job table; upgrade optional |
| Search | SQLite FTS5 | Upgrade path Postgres / OpenSearch deferred |
| UI | Static React bundle | Served from same process; no Node at runtime |
| Packaging | Venv folder or PyInstaller EXE | One‑click batch launcher |
| Geometry (Optional) | trimesh / meshio | Only if user enables feature |

## License
TBD (will be added before any public release). All current dependencies proposed are open‑source (MIT / Apache / BSD). Final license selection (MIT or Apache‑2.0 likely) pending.

License: (decide later)

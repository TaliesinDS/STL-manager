# Repository Contents & Commit Guidelines

This document explains what to keep in this repository, what to exclude, and where to place common project artifacts so the project stays reproducible, portable, and reviewer-friendly.

## High-level principles
Status update (2025-09-03)
- Current repo follows this guidance: code under `db/`, `scripts/`, tests under `tests/`, docs in `docs/`, and vocab under `vocab/`.
- Runtime DB files are kept under `data/` and referenced via `--db-url`/`STLMGR_DB_URL`; they’re excluded from commits.
- Script organization matches the proposed folder structure with maintenance utilities under `scripts/maintenance/` and integrations under `scripts/10_integrations/`.

- Keep source, configuration templates, short sample fixtures, docs, vocab, and migrations in Git.
- Exclude large binary assets, runtime database files, user-specific environments, and generated dependency caches.
- Store release artifacts (fat zips, EXEs) outside main branches — use GitHub Releases or a separate `releases/` area managed outside source control.
- Prefer small, curated sample datasets for CI/dev; run full ingestion from an external HDD or networked storage.

## What lives in this repo (commit)
- Source code: `stl_manager/` or top-level folders `api/`, `core/`, `db/`, `jobs/`, `cli/`, `services/`, `schemas/`.
- Vocabulary & normalization maps: `vocab/` (e.g., `tokenmap.md`, `designers_tokenmap.md`).
- Documentation & planning: `docs/` (including this file) and `README.md`.
  - Progress log: `docs/PROGRESS.md` (milestones, current sprint, dev log; linked from README)
- Database schema & migrations: `db/models.py`, `db/migrations/`, `alembic/` (if present).
- Tests & fixtures: `tests/` (include only tiny fixtures useful for CI).
- Frontend source: `frontend/` (TypeScript/React/Vite sources).
- Static frontend runtime (optional): `ui_dist/` — include this if you want the packaged app to serve UI without requiring Node at runtime.
- Build & run scripts: `scripts/one_click_start_template.bat`, other `scripts/` helpers.
- Config templates (non-secret): `CONFIG.example.yaml`, `.env.example`, `pyproject.toml`, `poetry.lock` (or equivalent lockfiles).
- CI / GitHub workflows and small utility tools: `.github/workflows/`, `.github/chatmodes/` (chatmode definitions), etc.

## What to keep out of Git (ignore / externalize)
- Large binary assets and raw model files (e.g., `*.stl`, `*.obj`, full extracted archives) — keep those on the dedicated HDD or in external storage.
- Runtime database files: `data/*.db`, `.db` blobs, or any transient SQLite file created by a run.
- Virtual environments and dependency caches: `.venv/`, `env/`, `node_modules/`.
- Build outputs: `dist/`, `build/`.
- User/editor settings: `.vscode/` (unless you intentionally share workspace settings), `.idea/`.
- Sensitive secrets or keys (API keys, password files) — keep them out and use environment variables or secret managers.

## Recommended `.gitignore` snippet
Add or verify these entries in the repository `.gitignore`:

```
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
.env
.env.*

# Runtime DB
/data/
*.db

# Build
dist/
build/

# Node
frontend/node_modules/

# Large model / asset files (do not commit)
*.stl
*.obj
*.zip
*.rar

# Editor
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

Tune the snippet to your team's preferences; the important bit is to keep bulky and runtime artifacts out of the repository.

## Handling large datasets & releases
- Full dataset: leave on your dedicated HDD and point the app to it via `CONFIG.yaml` or environment variable (e.g., `STLMGR_DATA_ROOT`).
- Distribution bundles (portable `.venv` or `stl_manager.exe`): publish these via GitHub Releases or an external artifact store rather than committing them.
- If you need to track medium-sized files in Git, use Git LFS and define a retention policy.

## Where to put release-ready static UI
- If you want one-click installs that do not require Node, commit the built UI to `ui_dist/` and ensure your start script serves that folder.
- Alternatively, build UI at CI time and publish `ui_dist/` to Releases alongside the packaged Python app.

## Minimal repo layout (example)
```
/ (repo root)
  stl_manager/        # python package
  api/                # optional split
  core/
  db/
    models.py
    migrations/
  vocab/
    tokenmap.md
    designers_tokenmap.md
  frontend/
    src/
  ui_dist/            # built frontend (optional)
  scripts/
    one_click_start_template.bat
  docs/
    TECH_STACK_PROPOSAL.md
    PLANNING.md
    REPO_CONTENTS.md
  tests/
    fixtures/
  .gitignore
  pyproject.toml
  poetry.lock
```

## Quick developer workflow suggestions
- Use `CONFIG.example.yaml` in the repo; ask users to copy to `CONFIG.yaml` and customize local paths (DB path, data root, API key).
- Keep a small sample dataset in `tests/fixtures/` for fast development & CI tests; never store the full extracted library there.
- Add a `scripts/bootstrap_dev.ps1` (PowerShell) that: creates a venv, installs pinned deps, runs DB migrations, and seeds small fixtures.

## Next steps you may want me to take
- Add/update `.gitignore` in the repo with the recommended entries.
- Create a tiny `tests/fixtures/sample_inventory.json` (10–20 records) for early development.
- Add `docs/RELEASES.md` with a short release-publish checklist (where to upload EXEs/zips).

---

If you want, I can now add the `.gitignore` entries and a tiny sample fixture so the repo is ready for scraper + DB work.
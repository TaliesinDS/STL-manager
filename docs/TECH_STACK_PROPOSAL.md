# Tech Stack & Architecture Proposal (Draft v1.1)

Date: 2025-08-17 (rev 1.1)
Scope: End-to-end stack recommendations for STL Manager across phases (P0–P3+). Emphasis on maintainability, deterministic processing, incremental scaling, Windows-friendly local dev, and minimal premature complexity.

Status update (2025-09-03)
- Current codebase runs SQLite + SQLAlchemy 2.x with Alembic; loaders and matchers operate via CLI scripts; optional UI and API layers remain planned.

---
## Guiding Principles
- Deterministic core first: every classification reproducible from vocab + rules.
- Local-first, single-user friendly early; seamless path to multi-user/network later.
- 100% Free / Open Source stack (permissive or copyleft acceptable) – no license fees.
- Windows 10 compatibility (baseline) without requiring WSL, Docker, or global service installs.
- One-click (batch file) startup: user should unzip/clone and double-click to launch.
- No mandatory global dependency pinning on host (Python, Node, Redis, Postgres optional only). All runtime versions are embedded or vendored.
- Favor boring, well-supported tech with strong ecosystem & typing.
- Layer capabilities only when the phase that needs them begins (defer search cluster, ML, geometry parsing until justified).
- Observability from day one (structured logs + lightweight metrics) to avoid blind spots.
- All vocab + rule evolution versioned in Git (no hidden runtime drift).

### Constraint Mapping (User Clarification)
| Requirement | Response |
|-------------|----------|
| Free software only | All proposed components are FOSS (MIT/Apache/BSD or similar). |
| Local hosting only | Default distribution runs entirely on local filesystem / localhost. |
| Windows 10 support | Chosen libs (FastAPI, SQLite, React build artifacts) are Windows-compatible; no mandatory POSIX-only daemons. |
| One-click startup | Provide `scripts/one_click_start_template.bat` that: sets up isolated venv, installs pinned wheels, launches API + opens UI. |
| No external services (DB, Redis) | Replace Redis & Postgres in baseline with SQLite (with FTS5) and an in-process job queue. Optional upgrade path documented but *not* required. |
| Avoid version drift | Ship lockfiles (Poetry lock) + optional pre-built virtual environment or frozen executable (PyInstaller) for distribution snapshots. |

If/when multi-user or >500k variant scale is reached, Postgres + Redis remain *optional upgrade modules* activated by explicit config; they are **not** part of the minimal one-click bundle.

Note (2025-08-29 alignment): Since rev 1.1 we added tabletop Units + Parts vocab ingestion (40K) and links (Variant↔Unit, Variant↔Part, Unit↔Part). The stack choices below remain valid; a few sections call out these additions explicitly.

---
## High-Level Component Map
| Domain | Function | Phase Intro | Baseline (Local/Free, No External Service) | Upgrade Path (Optional) | Notes |
|--------|----------|-------------|----------------------------------------|---------------------------|-------|
| Inventory Scanner | Walk filesystem | P0 | Python 3.12 script | N/A | Existing `quick_scan.py` refactor |
| Normalization Engine | Deterministic mapping | P1 | Pure Python module | N/A | No brokers required |
| Vocabulary Store | Token maps & manifests | P0 | Git files (JSON/MD) | Cache table in DB | Validation script only |
| Persistence DB | Variants, audit, overrides | P1 | SQLite (FTS5 + JSON1) | PostgreSQL 16 | Single file DB portable |
| API Layer | REST + SSE | P1 | FastAPI + Uvicorn (embedded) | Same | Runs inside one process |
| Background Jobs | Async normalization | P1 | In-process worker threads + SQLite job table | Dramatiq + Redis | Thread pool sufficient early |
| Search / Facets | Token & text search | P1 | SQLite FTS5 virtual tables | Postgres GIN / OpenSearch | Avoid external search daemon |
| Web UI | Browser UI | P2 | Pre-built static React assets served by API | Separate dev server during dev | No Node needed at runtime |
| Asset Storage | STL files | P0 | Native filesystem | S3/MinIO | Read-only early |
| Geometry Analysis | Hashing & metrics | P3 | trimesh + meshio on-demand | Dedicated worker farm | Only when user opts in |
| Auth | Single-user API key | P1 | Static key in config | JWT multi-user | Optional until sharing |
| Audit Trail | Change history | P1 | SQLite table | Same | Append-only design |
| Metrics | Basic stats | P1 | Built-in endpoint (JSON) | Prometheus exporter | Simpler than full stack |
| Logging | Structured logs | P0 | structlog to file + console | Central log aggregation | Rotating file handler |
| Packaging | Distribution | P1 | Portable venv or PyInstaller EXE | Nuitka / Docker | User chooses flavor |
| Deployment | Local | P1 | Batch script startup | Docker Compose | Batch kept authoritative |
| CLI Tooling | Power ops | P1 | Typer CLI (stlmgr) | Same | Wraps same code paths |
| Testing | Quality gate | P0+ | Pytest | Same | Ship tests optional |
| Realtime Events | Job progress | P2 | SSE via FastAPI | WebSockets | SSE simpler (one-way) |
| Docs | User/dev docs | P1 | Markdown in repo | MkDocs site build | Build optional, not required at runtime |

---
## Detailed Rationale by Layer
### 1. Language & Core Runtime
**Python 3.12**: Already used; pattern matching, typing improvements, stable ecosystem for file IO and scientific libs later.
Alternative deferred: Rust or Go for performance-sensitive geometry hashing; only if profiling shows Python bottleneck.

### 2. Inventory & Normalization
- Keep pure functions: `tokens = tokenize(path_segments)`; `result = normalize(tokens, ruleset)` => facilitates property-based testing.
- Provide both CLI and import API to avoid code duplication.
- Use a `Ruleset` dataclass reading vocab manifests + token map with version id (hash for integrity).

### 3. Vocabulary & Manifests
- Continue storing in Git (Markdown/JSON/YAML). Add a lightweight loader that caches a computed `ruleset_digest` (SHA256) to short-circuit re-normalization when unchanged.
- Validation script: schema check (JSON Schema for JSON manifests) + duplicate alias detection.
- Tabletop vocab files (Phase 2 gated but present now for ingestion):
  - Units: `vocab/codex_units_w40k.yaml`, `codex_units_aos.yaml`, `codex_units_horus_heresy.yaml`
  - Parts (40K first): `vocab/wargear_w40k.yaml`, `vocab/bodies_w40k.yaml`
- YAML parsing: `ruamel.yaml` round‑trip loader with duplicate key tolerance; preserve full node snapshot in DB `raw_data` fields.

### 4. Database
Phase strategy:
- **P1 (local)**: SQLite (WAL mode) — zero friction, supports transactions & partial indexes.
- **P2+**: PostgreSQL 16 for: GIN/Trigram indexing, JSONB for audit metadata, concurrency, FTS.
Migration: Alembic migrations written from day one; tests run under both SQLite (fast) and Postgres (CI service container) to catch dialect drift.
Schema patterns:
- Core tables: `variant`, `archive`, `vocab_*` (cache of file-based vocab), `override`, `audit_log`, `job`.
- Tabletop entities: `game_system`, `faction`, `unit`, `unit_alias`, association `variant_unit_link`.
- Parts entities: `part`, `part_alias`, associations `variant_part_link`, `unit_part_link` (for compatibility/recommendations/requirements).
- Use surrogate integer/UUID primary keys (UUID v7 library once stable or Postgres `gen_random_uuid()`).
- Partial index example: GIN on `residual_tokens` for array containment search.

### 5. API Layer
**FastAPI** (sync/async hybrid) served by Uvicorn inside the same Python process the batch file launches.
SQLite accessed via SQLAlchemy (sync engine) to avoid event loop complexity early; can switch to async if needed. No external services required.
Optional SSE endpoint for job progress uses simple generator; no dependency on Redis.
Rate limiting unnecessary single-user; disabled by default.

Endpoints alignment (see `docs/API_SPEC.md`):
- Variants (+ overrides, bulk, jobs) as before; plus links: Variant↔Unit and Variant↔Part.
- Units: list/detail, `.../variants`, `.../parts`, and combined `.../bundle` for the dual-return UI.
- Parts: list/detail, `.../variants`.
- Discovery: `game-systems`, `factions`.

### 6. Background Jobs
Baseline: In-process thread pool (e.g., `concurrent.futures.ThreadPoolExecutor`) managing a simple SQLite-backed `job` table with state transitions.
Dispatch pattern: API inserts job row (status=pending) then submits function to the pool; worker updates progress fields.
Progress polling or SSE pushes JSON lines (no Redis, no message broker).
Upgrade path (optional): Add Dramatiq + Redis only if distributing work across multiple processes or machines.

### 7. Search & Filtering
Baseline: SQLite FTS5 virtual table `variant_fts` (content=variant) indexing designer, franchise, residual joined tokens string.
Facets: simple `SELECT field, COUNT(*) FROM variant WHERE ... GROUP BY field` with small dataset; if slow, create precomputed facet summary tables updated after normalization batches.
Fuzzy: Use FTS5 BM25 scoring + LIKE for lightweight fuzzy fallback; upgrade to Postgres trigram/OpenSearch only if dataset + latency warrant.

### 8. Web UI
Dev Tooling: React + TypeScript + Vite (only required during development).
Runtime Distribution: Pre-built static assets (HTML/CSS/JS) placed under `ui_dist/` and served by FastAPI's static files mount – end user does *not* need Node.js.
Styling/Components: Mantine (MIT). All dependencies bundled in build output.
State/Data: TanStack Query for caching + polling/SSE.
Auth: Initially single static API key stored in memory; UI exposes a settings modal to change it.

Unit detail UX (tabletop): two-pane view returning both full models and parts/mods.

### 9. File / Asset Handling
- Keep raw STL directory read-only for Phase 0/1 (no moving/renaming). Add an abstraction service later if remote store (S3 / MinIO) required.
- Introduce file integrity hashing (SHA256) in P3; store in `archive` and/or `variant_asset` table.

### 10. Geometry & Mesh Analysis (P3)
Opt-in module. If user never invokes geometry commands, heavy libs need not be installed (split extras: `pip install stl-manager[geometry]`).
On Windows 10, ensure pure-Python wheels selected; avoid forcing compilation for first release.
Execution via background thread pool; progress emitted by SSE.

### 11. Authentication & Authorization (P2)
- Simple users table: id, email, password_hash (argon2), role.
- JWT access tokens (short) + refresh tokens (long) stored httpOnly (when browser usage), or CLI use API key.
- Role-based dependency injection in FastAPI routes (admin vs viewer vs curator).

### 12. Audit & Overrides
- Append-only `audit_log` with columns: id, resource_type, resource_id, field, old_value, new_value, actor_id, ts.
- Provide revert by writing inverse log (never destructive delete).
- Override layering: store manual value & original auto value snapshot; normalization engine checks overrides before writing.

### 13. Observability
- Structured logging with `structlog`: fields (ts, level, msg, request_id, job_id, duration_ms).
- Metrics: `prometheus_client` counters (requests_total{path,method,status}), histograms (request_latency_ms, normalization_duration_ms), gauges (jobs_running).
- Health endpoint `/api/v1/system/health` with DB connectivity + ruleset digest.

### 14. Testing & Quality
Pytest layers: unit (pure functions), integration (SQLite + API), property tests (tokenization invariants), snapshot tests (normalization outputs for fixed fixture paths).
Coverage threshold >80% initially (raise after stabilization) to keep velocity; focus on normalization determinism.
Pre-commit: ruff (lint + format), mypy (strict for core), pytest -k fast subset.

### 15. Packaging & Distribution
Primary Distribution Forms:
1. Portable Folder (Recommended Early):
  - Contains `.venv/` (pre-created), source package, `requirements.txt` (or `poetry.lock`), `start_stl_manager.bat`.
  - User double-clicks batch; script activates local venv and starts API + opens browser.
2. Single Executable (Optional):
  - PyInstaller spec produces `stl_manager.exe` bundling Python interpreter & libs. Separate build variant with geometry extras.
3. Zip Archive: Compressed portable folder variant.
4. (Optional) Docker Image: For non-Windows users; *not* required by baseline.

Version Pinning:
 - `poetry.lock` (source of truth) -> generate `requirements.txt` for PyInstaller reproducibility.
 - Batch script verifies interpreter (bundled) via relative path, ignoring any system Python.

### 16. Deployment Strategy
Baseline: Local only. Provide `CONFIG.yaml` for tuning (DB path, API key, port). Batch script reads it.
Optional Advanced: Compose file includes Postgres/Redis only if user explicitly opts in.
No mandatory cloud resources.

### 17. Real-Time Updates
- SSE endpoint `/api/v1/events` streaming JSON lines (event: job_progress, suggestion_added, audit_tail).
- Client uses EventSource; fallback to polling if unsupported.
- Later upgrade to WebSockets only if bidirectional interactions (live collaborative editing) required.

### 18. Security & Hardening (Progressive)
- Input validation via Pydantic + server-side enums.
- Rate limiting (Redis) when multi-user.
- CORS locked to configured origins.
- Add SAST (Bandit) and dependency scanning (pip-audit) in CI.

### 19. Data Model Performance Considerations
- Index strategy (Postgres):
  - BTREE on (designer), (codex_faction), (game_system).
  - GIN on residual_tokens (array), user_tags (array), tsvector column search_document.
  - Partial index: `CREATE INDEX idx_variant_nsfw ON variant(content_flag) WHERE content_flag = 'nsfw';`
  - Composite for common filters: `(designer, asset_category)`.
- Periodic VACUUM / ANALYZE (cron or autovacuum fine initially).

### 20. Scaling Path Summary
| Stage | Records | Storage | Search | Jobs | Notes |
|-------|---------|---------|--------|------|-------|
| Early P1 | <100k | SQLite | FTS5 | Inline thread | One-click bundle only |
| Late P1 | 100k–300k | SQLite (optimize pragmas) | FTS5 + cached facets | Thread pool | May still avoid upgrade |
| P2 | 300k–1M | SQLite or Postgres (optional) | FTS5 or GIN | Thread pool / optional Dramatiq | Decision gate here |
| P3 | 1M–5M | Postgres (if chosen) | GIN/Trigram | Dramatiq workers | Geometry tasks begin |
| P4 | >5M | Postgres partitioned | OpenSearch (if needed) | Scaled workers | Only if user scales up |

---
## Initial Directory Structure (Expanded)
```
/ stl_manager/
  api/            # FastAPI routers
  core/           # Normalization engine (pure)
  vocab_loader/   # Parsers + validators
  db/
    models.py
    session.py
    migrations/
  jobs/           # Dramatiq task defs
  cli/
    __init__.py   # Typer app
  schemas/        # Pydantic models (shared)
  services/       # Higher-level orchestration (normalization runner)
  tests/
frontend/
  src/
    components/
    pages/
    api/
    hooks/
Dockerfile
compose.yaml
pyproject.toml
```

---
## Tool & Library Choices (Concise Justification)
**FastAPI**: Type safety + OpenAPI docs; minimal overhead.
**SQLAlchemy 2.x**: Unified DB code; dialect switch later.
**structlog**: Structured JSON logs for troubleshooting.
**Typer**: Simple unified CLI.
**Ruff / mypy**: Fast lint + typing.
**SQLite FTS5**: Built-in full-text search; no extra service.
**React + Mantine + TanStack Query**: Build once, ship static assets; all MIT licensed.
**PyInstaller**: Optional self-contained Windows executable packaging.

---
## Risk Mitigation Table
| Risk | Mitigation | Trigger for Revisit |
|------|------------|----------------------|
| SQLite concurrency limits | Early switch to Postgres once >1 writer or >100k rows | Write contention metrics > threshold |
| Token search slow in Postgres | Add indexes/materialized views; only then external search | FTS query P95 >150ms |
| Job backlog growth | Priority queues + worker autoscale | Queue latency >2m |
| Geometry lib performance | Profile, consider Rust microservice | Geometry job median > desired SLA |
| Vocab drift vs code | CI validator + ruleset digest check | Any normalization mismatch in tests |

---
## Phase-by-Phase Implementation Order (Actionable)
1. P0 Enhancements: Refactor `quick_scan.py`; add ruleset digest & unit tests; introduce CLI skeleton.
2. P1 Core: Normalization engine + SQLite schema + FastAPI endpoints (variants, vocab, overrides, jobs sync) + batch start script.
3. Add in-process job queue + SSE progress stream.
4. Build & bundle initial UI (static assets) – variant list + filters + override form.
5. Implement audit logging + revert; add FTS5 search + facets.
6. Optional packaging: PyInstaller portable EXE variant.
7. P2 gating: auth (API key config file), advanced bulk ops UI.
8. Geometry hashing (opt-in extras) + dedupe suggestions.
9. Evaluate need for Postgres/Redis (only if scale gate crossed); otherwise continue optimizing SQLite.

---
## Minimal Early Dependencies List (Python)
```
fastapi
uvicorn
sqlalchemy>=2.0
pydantic>=2.0
structlog
typer
ruff
mypy
pytest
python-dotenv
alembic            # still useful for migrations even on SQLite
ruamel.yaml        # YAML loader for units/parts vocab ingestion
trimesh ; extra == "geometry"
meshio  ; extra == "geometry"
```
Optional (only if upgrading): `psycopg[binary]`, `prometheus-client`, `dramatiq`, `redis`.

---
### Docker Readiness (Deferred Future Packaging)
The current local-first design is container-friendly; no chosen component blocks later Dockerization.
Key readiness points:
1. Single Process Simplicity: All baseline services (API, jobs, SQLite) run in one Python process, enabling a minimal single-container image initially.
2. SQLite in WAL Mode: Works inside a container with a bind-mounted volume (`/data/app.db`) to persist state; no host OS features required beyond standard file locking (supported on Linux). For multi-writer or scale triggers you can introduce Postgres as a second container later without refactoring the normalization core.
3. Static UI Assets: Pre-built React bundle is pure static files; COPY into image and serve via FastAPI static mount (no Node in runtime layer). Multi-stage build keeps final image slim.
4. Optional Components: Dramatiq/Redis/Postgres/OpenSearch remain additive; each can map to additional services in a future `compose.yaml` without altering core package APIs (decoupled via interfaces/service modules).
5. Configuration via Environment: Planned config loader should check env vars (e.g., `STLMGR_DB_URL`, `STLMGR_API_KEY`) before falling back to `CONFIG.yaml`, aligning with container best practices.
6. Deterministic Builds: Pin versions in `pyproject.toml` + lock; future Dockerfile uses those to ensure reproducible layers.
7. Logging & Metrics: Structured JSON logs already suitable for container stdout. Prometheus exporter (optional) just exposes an HTTP endpoint—no change needed.
8. Security: Single-user API key stays as env var secret (`STLMGR_API_KEY`) in container runtime; later multi-user adds JWT without image change.

Sample future (not yet needed) multi-stage outline:
```
FROM node:22-alpine AS ui-build
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml poetry.lock ./
# (Optionally install with pip if using requirements.txt)
RUN pip install --no-cache-dir --upgrade pip \
  && pip install .[geometry]  # or . without extras
COPY stl_manager/ ./stl_manager/
COPY scripts/start_container.sh ./
COPY --from=ui-build /ui/dist ./ui_dist
VOLUME ["/data"]
ENV STLMGR_DB_PATH=/data/app.db
EXPOSE 8000
CMD ["python", "-m", "stl_manager.api.run"]
```
Nothing in current architecture mandates Windows-only code paths; ensure future file handling uses `pathlib` for portability.

---
## Suggested Next Steps
1. Confirm acceptance of local-only baseline & packaging strategy.
2. Generate `pyproject.toml` with pinned versions + extras section.
3. Implement ruleset digest + normalization tests.
4. Add SQLite schema + Alembic baseline.
5. Create batch starter script referencing local venv.
6. Build minimal UI (list + search) and integrate static serving.

---
## Open Questions
- Do we anticipate multi-user editing before P2? (If yes, implement Postgres earlier.)
- Is Windows-only deployment acceptable for first release, or do we target cross-platform Docker from start?
- Should we pre-reserve naming for potential multi-tenancy (add tenant_id columns) now to avoid later migrations?

---
*End of Draft v1.1 – updated for local-only, free, one-click constraints.*

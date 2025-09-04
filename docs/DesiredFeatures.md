Desired Features (migrated from root 2025-08-16)

Phase 0 (Inventory Only)
Scan existing extracted directory tree (no archive extraction).
Record path, size, mtimes, extension, hash (defer hash until after pilot performance test).
Lightweight media classification: mesh vs image vs other.
Skip large binary ingestion into Git.
Emit CSV + JSON lines per file for flexibility.
Configurable ignore patterns (e.g., previews, unsupported formats) – minimal at first.

Phase 1 (Deterministic Normalization – Low Risk Fields)
Status update (2025-09-03)
- Phase 0 inventory and Phase 1 deterministic normalization are in place for key fields; residual token capture and warnings are active.
- Unit/parts vocabulary externalized under `vocab/` with loaders; linking tables enable unit and parts associations.
- Tests cover basing integrity and workflow sanity; Windows tasks exist to run common flows.

Canonical designer inference via alias map (with suffix stripping like (Presupported)).
Franchise (broad) assignment (e.g., warhammer_40k, generic_fantasy) using curated token sets.
Lineage family grouping (space_marines, orks, etc.) – limited curated set.
Asset category classification: miniature, base_topper, terrain_piece, vehicle, bits, token, scatter.
Scale normalization: detect 28mm heroic, 32mm, 6mm (epic), 15mm etc (initial subset) via tokens.
Residual token capture: store all unmatched alphanumeric tokens for later mining.
Strict precedence ordering to avoid noisy false positives.
Idempotent re-runs (same input -> same output). No probabilistic steps.
Generate audit of field assignments (source=designer_map|franchise_token|etc.).

Phase 2 (Extended Wargame Unit Layer – Feature Gated)
Optional enriched classification mapping variant to game_system + codex_faction + (planned) unit roles (hq, troops, heavy, elite, fast).
Externalized codex unit vocabulary (separate files) to minimize diffs.
Confidence scoring (simple counts) – later.
Unit extraction flag off by default to prevent misclassification early.
Ambiguity warning list (tokens mapping to multiple factions).

Phase 3 (Relationships & Derived Groupings)
Lineage tree: parent lineage_family -> specific chapter/subfaction (later perhaps).
Compatible units array (list of other variant ids sharing kit-bash potential) – manual curation.
Kit composition (if a file set contains multiple meshes forming a unit) – future.
Model set detection (STL + pre-supported + Lychee file grouping) via basename heuristics.

Phase 4 (User Overrides & UI)
Web UI for browse, facet filtering, edit overrides.
Override layering: manual override stored separately; auto engine re-runs never overwrite manual.
Audit timeline per variant & per vocab entry.
Bulk edit wizard (filter -> preview -> apply) with dry run.
Residual token explorer: frequency table, promote to alias with one click.

Feedback Loop: Mismatch Reporting & Safe Defaults
- In‑app report flow: Add a "Report mismatch" button on Variant details. Capture variant_id, current fields (system/faction/franchise/character), filenames/paths, token trace, and an optional user comment.
- Storage: `mismatch_reports` table with status (new/reviewed/fixed), timestamps, and resolution notes; link to the reporting user when available.
- Admin review page: Filter/sort queue, mark accepted/denied, batch-generate a triage JSON to feed into fixer scripts.
- Safe‑by‑default application: matchers run dry‑run by default; only fill empty fields unless `--overwrite` is set; gate writes behind `--min-confidence` (default 0.8).
- Explainability: show "why matched" (tokens used, rule names triggered, score breakdown, alias provenance) on Variant page and include in `--out` JSON reports.
- Progressive matching tiers: Tier 1 (exact within scoped system/faction) auto‑apply; Tier 2 (strong partial + multiple hints) proposal only by default; Tier 3 (experimental/fuzzy) proposals only.
- Edge‑case scaling: run scans in batches, emit coverage and "top misses" reports; provide ignore/negatives overlays users can manage in‑app so noisy folders don’t pollute detection.

Phase 5 (Archive Ingestion & Advanced Processing)
Controlled archive extraction queue (hash-first to skip dups).
Checksum based dedupe (identical meshes in different packs).
Geometry fingerprinting (hash on normalized mesh) – experimental.
STL metadata extraction (dimensions, volume) – out of scope until earlier phases stable.

Vocabulary Management Principles
All vocab value additions logged in DECISIONS.md with version bump or explicit note if no bump.
Designer alias map curated to avoid collisions; keep minimal early; expand via residual token review.
Factions remain inline for Phase 1 simplicity; only high-churn large lists (units, designers) externalized.
No removal of existing canonical tokens without migration plan.

Vocab Subscriptions (Blocklist‑style Updates)
- Subscribe to external vocab sources (like uBlock Origin lists): support `vocab/subscriptions.yaml` with one or more sources (name, URL, type: designers/units/franchises/parts, optional branch/tag/ref, checksum/signature, and apply scope).
- Update flow: "Check for updates" runs a dry‑run to fetch, validate schema, and compute a diff; show a preview grouped by category (designers, units, aliases, legends flags, base profiles) with accept/deny per group.
- Provenance and safety: store source, version/ref, and checksum on applied rows; changes are gated by conflicts policy (local overrides win), `--min-confidence` where applicable, and never overwrite manual edits unless explicitly allowed.
- Layering and precedence: builtin → subscribed lists (ordered) → local overrides. Local overrides always take precedence and survive updates.
- Rollback: keep timestamped snapshots and allow one‑click revert to the previous vocab state; write a JSON diff report under `reports/` for traceability.
- Scheduling: optional background check (e.g., weekly) plus a manual "Update vocab" button in UI.
- Offline‑first: cache remote sources under `data/vocab_cache/` and only re‑fetch when ref or checksum changes.

User‑managed Vocab (BYO) — deferred
- The same updater should support local sources (file/folder paths) so users can curate their own vocab and apply it with the same dry‑run/diff/rollback flow.
- Manage local sources via `vocab/subscriptions.yaml` entries pointing to paths; keep an “Overrides” folder that is ignored by Git by default.
- Precedence: local overrides (BYO) > subscribed lists > builtin.
- Status: parked for later to avoid scope creep; design documented for future implementation.

Quality & Safety Constraints
No destructive renames of source files in early phases.
Script dry-runs before committing normalized outputs.
Deterministic ordering for token scanning; explicit precedence doc maintained (NormalizationFlow.md).
Unit test harness (future) to lock regression for precedence & classification.

Tooling & Scripts (Planned)
quick_scan.py (existing) – collect residual tokens & basic classification pilot.
normalize_pass.py – implement ordered deterministic passes (Phase 1 subset).
residual_analyzer.py – frequency distribution & candidate vocab suggestions.
vocab_loader.py – unify loading of designers + codex units + faction tokens with version check.
collision_checker.py – detects alias collisions & ambiguous mappings.
 export_mismatch_queue.py – dump `mismatch_reports` (admin‑accepted only) to triage JSON with explainability details.
 apply_mismatch_fixes.py – read triage JSON and apply DB updates with `--dry-run/--apply`, `--min-confidence`, and `--overwrite` gates.
 update_vocab_subscriptions.py – fetch/validate subscribed vocab sources (remote URLs or local paths), compute diffs, write preview report, and optionally apply with safety gates.
 validate_vocab_sources.py – schema and collision checks for all subscribed sources; produces actionable diagnostics.

Data Artifacts
inventory_files.csv / .jsonl – raw file inventory.
normalized_variants.jsonl – one per variant after Phase 1.
vocab/ directory – modular vocab files versioned in Git.
reports/residual_tokens_{date}.csv – token mining snapshots.
 vocab/subscriptions.yaml – list of subscribed vocab sources and update policy.
 data/vocab_cache/ – cached copies of subscribed source payloads with checksums.
 reports/vocab_update_{timestamp}.json – diff/preview report for each update check.

Stretch / Maybe Later
Mesh thumbnail generation pipeline.
3D geometry normalization & measurement (height, volume) with OpenSCAD or mesh libs.
Slicer profile detection & parameter extraction.
License text extraction and classification.
ML assisted similarity / clustering (only after strong deterministic core).

Non-Goals (Explicitly Out of Scope Early)
Automatic printability analysis.
Complex semantic ML classification.
Automated support generation.
Cloud sync / multi-user auth (until local pipeline proven).

Risks & Mitigations
Mass false positives in classification: Mitigate with limited curated vocab, precedence doc, gating Phase 2 features.
Alias collision sprawl: collision_checker script + manual review before merge.
Performance over huge directory: streaming IO, optional hashing phase.
Path length limits on Windows: prefer relative paths; watch 260+ char edge cases.

Success Criteria (Early Phases)
Phase 0: Inventory completes on existing extracted tree within acceptable time (TBD) and produces stable artifact.
Phase 1: >95% precision on designer & franchise for curated test set; residual token list materially helpful.
Phase 2: Feature gate off by default; enabling yields acceptable precision on a pilot subset.

Tracking & Metrics (Future)
Unknown token count trend over time (should decrease).
Manual overrides count by field (monitor taxonomy stability).
Average classification time per 1k files.

Changelog Hooks
Every vocab addition -> DECISIONS.md entry referencing token_map_version or rationale for no bump.
Restructure operations (like docs/ & vocab/) logged once with rationale.

Notes
This file is intentionally high-level; implementation specifics live in API_SPEC.md, MetadataFields.md, NormalizationFlow.md.

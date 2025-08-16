Desired Features (migrated from root 2025-08-16)

Phase 0 (Inventory Only)
Scan existing extracted directory tree (no archive extraction).
Record path, size, mtimes, extension, hash (defer hash until after pilot performance test).
Lightweight media classification: mesh vs image vs other.
Skip large binary ingestion into Git.
Emit CSV + JSON lines per file for flexibility.
Configurable ignore patterns (e.g., previews, unsupported formats) – minimal at first.

Phase 1 (Deterministic Normalization – Low Risk Fields)
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

Data Artifacts
inventory_files.csv / .jsonl – raw file inventory.
normalized_variants.jsonl – one per variant after Phase 1.
vocab/ directory – modular vocab files versioned in Git.
reports/residual_tokens_{date}.csv – token mining snapshots.

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

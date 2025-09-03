# Scripts shims migration plan

Goal: remove legacy root-level shim scripts in `scripts/` that duplicate the canonical scripts now housed in subfolders, without breaking tasks, docs, or user workflows.

## Scope and principles
- Canonical source of truth lives under structured subfolders within `scripts/`:
  - `00_bootstrap/`, `10_integrations/`, `10_inventory/`, `20_loaders/`, `30_normalize_match/`, `40_kits/`, `50_cleanup_repair/`, `60_reports_analysis/`, `90_util/`.
- Root-level duplicates are considered shims and should be deprecated, then removed after tasks/docs are updated.
- Windows-first: preserve working PowerShell one-liners and VS Code tasks; prefer explicit venv python and `--db-url` flags over env var reliance.

## Inventory: root shims -> canonical script

Cohort A — Bootstrap
- `scripts/bootstrap_db.py` -> `scripts/00_bootstrap/bootstrap_db.py`
- Legacy (superseded, schedule retirement): `scripts/create_fresh_db.py`, `scripts/init_db.py`

Cohort B — Inventory
- `scripts/compute_hashes.py` -> `scripts/10_inventory/compute_hashes.py`
- `scripts/create_sample_inventory.py` -> `scripts/10_inventory/create_sample_inventory.py`
- `scripts/quick_scan.py` -> `scripts/10_inventory/quick_scan.py`
- `scripts/scan_sample_inventory.py` -> `scripts/10_inventory/scan_sample_inventory.py`
- `scripts/validate_tokenize_sample.py` -> `scripts/10_inventory/validate_tokenize_sample.py`

Cohort C — Loaders
- `scripts/create_missing_franchises.py` -> `scripts/20_loaders/create_missing_franchises.py`
- `scripts/load_codex_from_yaml.py` -> `scripts/20_loaders/load_codex_from_yaml.py`
- `scripts/load_designers.py` -> `scripts/20_loaders/load_designers.py`
- `scripts/load_franchises.py` -> `scripts/20_loaders/load_franchises.py`
- `scripts/load_sample.py` -> `scripts/20_loaders/load_sample.py`
- `scripts/sync_characters_to_vocab.py` -> `scripts/20_loaders/sync_characters_to_vocab.py`
- `scripts/sync_designers_from_tokenmap.py` -> `scripts/20_loaders/sync_designers_from_tokenmap.py`
- `scripts/sync_franchise_tokens_to_vocab.py` -> `scripts/20_loaders/sync_franchise_tokens_to_vocab.py`

Cohort D — Normalize/Match
- `scripts/apply_proposals_from_report.py` -> `scripts/30_normalize_match/apply_proposals_from_report.py`
- `scripts/apply_sample_folder_tokens.py` -> `scripts/30_normalize_match/apply_sample_folder_tokens.py`
- `scripts/apply_vocab_matches.py` -> `scripts/30_normalize_match/apply_vocab_matches.py`
- `scripts/find_vocab_matches.py` -> `scripts/30_normalize_match/find_vocab_matches.py`
- `scripts/match_collections.py` -> `scripts/30_normalize_match/match_collections.py`
- `scripts/match_franchise_characters.py` -> `scripts/30_normalize_match/match_franchise_characters.py`
- `scripts/match_parts_to_variants.py` -> `scripts/30_normalize_match/match_parts_to_variants.py`
- `scripts/match_variants_to_units.py` -> `scripts/30_normalize_match/match_variants_to_units.py`
- `scripts/normalize_inventory.py` -> `scripts/30_normalize_match/normalize_inventory.py`

Cohort E — Kits
- `scripts/backfill_kits.py` -> `scripts/40_kits/backfill_kits.py`
- `scripts/fix_infernus_kit.py` -> `scripts/40_kits/fix_infernus_kit.py`
- `scripts/link_virtual_parent.py` -> `scripts/40_kits/link_virtual_parent.py`

Cohort F — Cleanup/Repair
- `scripts/cleanup_merge_leaf_variants.py` -> `scripts/50_cleanup_repair/cleanup_merge_leaf_variants.py`
- `scripts/cleanup_remove_junk_only_variants.py` -> `scripts/50_cleanup_repair/cleanup_remove_junk_only_variants.py`
- `scripts/clear_variant_franchise.py` -> `scripts/50_cleanup_repair/clear_variant_franchise.py`
- `scripts/delete_variant.py` -> `scripts/50_cleanup_repair/delete_variant.py`
- `scripts/fix_skarix_designer.py` -> `scripts/50_cleanup_repair/fix_skarix_designer.py`
- `scripts/migrate_codex_to_character.py` -> `scripts/50_cleanup_repair/migrate_codex_to_character.py`
- `scripts/prune_invalid_variants.py` -> `scripts/50_cleanup_repair/prune_invalid_variants.py`
- `scripts/remove_loose_files_from_variant.py` -> `scripts/50_cleanup_repair/remove_loose_files_from_variant.py`
- `scripts/repair_orphan_variants.py` -> `scripts/50_cleanup_repair/repair_orphan_variants.py`
- `scripts/repair_sigmar_variants.py` -> `scripts/50_cleanup_repair/repair_sigmar_variants.py`
- `scripts/set_variant_franchise.py` -> `scripts/50_cleanup_repair/set_variant_franchise.py`

Cohort G — Reports/Analysis
- `scripts/annotate_proposals_with_hints.py` -> `scripts/60_reports_analysis/annotate_proposals_with_hints.py`
- `scripts/check_character_conflicts.py` -> `scripts/60_reports_analysis/check_character_conflicts.py`
- `scripts/check_codex_duplicates.py` -> `scripts/60_reports_analysis/check_codex_duplicates.py`
- `scripts/clean_proposals_file.py` -> `scripts/60_reports_analysis/clean_proposals_file.py`
- `scripts/count_franchise_characters.py` -> `scripts/60_reports_analysis/count_franchise_characters.py`
- `scripts/count_null_franchise.py` -> `scripts/60_reports_analysis/count_null_franchise.py`
- `scripts/debug_franchise_sample.py` -> `scripts/60_reports_analysis/debug_franchise_sample.py` (duplicate also exists in `90_util/` — unify)
- `scripts/debug_matching_state.py` -> `scripts/60_reports_analysis/debug_matching_state.py`
- `scripts/debug_variant_fields.py` -> `scripts/60_reports_analysis/debug_variant_fields.py`
- `scripts/dump_residual_token_counts.py` -> `scripts/60_reports_analysis/dump_residual_token_counts.py`
- `scripts/export_codex_candidates.py` -> `scripts/60_reports_analysis/export_codex_candidates.py`
- `scripts/filter_proposals.py` -> `scripts/60_reports_analysis/filter_proposals.py`
- `scripts/inspect_db.py` -> `scripts/60_reports_analysis/inspect_db.py`
- `scripts/inspect_db_characters.py` -> `scripts/60_reports_analysis/inspect_db_characters.py`
- `scripts/inspect_inference.py` -> `scripts/60_reports_analysis/inspect_inference.py`
- `scripts/inspect_orphan_tokens.py` -> `scripts/60_reports_analysis/inspect_orphan_tokens.py`
- `scripts/inspect_vocab_and_variants.py` -> `scripts/60_reports_analysis/inspect_vocab_and_variants.py`
- `scripts/parse_normalization_stdout.py` -> `scripts/60_reports_analysis/parse_normalization_stdout.py`
- `scripts/report_codex_counts.py` -> `scripts/60_reports_analysis/report_codex_counts.py`
- `scripts/report_franchise_coverage.py` -> `scripts/60_reports_analysis/report_franchise_coverage.py`
- `scripts/variant_field_stats.py` -> `scripts/60_reports_analysis/variant_field_stats.py`
- `scripts/verify_applied_matches.py` -> `scripts/60_reports_analysis/verify_applied_matches.py`
- `scripts/verify_migration_output.py` -> `scripts/60_reports_analysis/verify_migration_output.py`
- `scripts/verify_tokens_written.py` -> `scripts/60_reports_analysis/verify_tokens_written.py`

Cohort H — Utilities
- `scripts/dump_one_file.py` -> `scripts/90_util/dump_one_file.py`
- `scripts/list_variant_files.py` -> `scripts/90_util/list_variant_files.py`
- `scripts/show_variant.py` -> `scripts/90_util/show_variant.py`
- Note: `scripts/debug_franchise_sample.py` duplicate exists here; keep only one canonical location (prefer `60_reports_analysis/`) and remove the other.

Unmigrated root-only (evaluate destination or retire)
- `scripts/assign_codex_units_aos.py` — Candidate to move under `30_normalize_match/` (assignment) or `20_loaders/` (YAML-driven). Evaluate and rehome or retire if superseded.
- `scripts/db_check.py` — Candidate to move under `60_reports_analysis/` or `00_bootstrap/` (health checks). Update tasks accordingly.
- `scripts/create_fresh_db.py` — Superseded by `00_bootstrap/bootstrap_db.py`; deprecate and remove after deprecation window.
- `scripts/init_db.py` — Superseded by `00_bootstrap/bootstrap_db.py`; deprecate and remove after deprecation window.

Items not listed above either do not have root duplicates (e.g., `10_integrations/fetch_mmf_collections.py`) or are already only present in canonical locations.

## Migration steps

1) Freeze shims and add explicit deprecation notice
- Ensure every root-level shim does nothing but import and forward to the canonical script `main()` (no logic).
- Print a one-line stderr warning on invocation: "Deprecated: use scripts/<subfolder>/<name>.py".
- Guard Windows PowerShell usage by keeping CLI signatures identical.

Status (2025-09-03): Cohorts A–D shims updated with deprecation warnings and delegation; tasks/docs/tests now reference canonical scripts. Root shims retained temporarily for the deprecation window.

2) Update VS Code tasks and docs
- Replace all task command paths pointing to root `scripts/<name>.py` with canonical subfolder paths.
- Update `scripts/README.md` CLI quick-reference to show only canonical subfolder commands.
- Grep the repo for references to root shims and update them.

3) Verify green: build, lint, tests
- Run unit tests via venv:
  ```powershell
  c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q
  ```
- Smoke-run a representative sample per cohort (dry-run where supported) using `--db-url` instead of env var.

4) Remove shims (deletion phase)
- After tasks/docs are updated and tests pass, delete root-level shim files listed in the Inventory above.
- Keep `scripts/legacy/` for any truly obsolete binaries that might be useful as reference, but remove from tasks/docs.

Deletion checklist (batch 1 – A–D):
- [x] `scripts/bootstrap_db.py`
- [x] `scripts/compute_hashes.py`
- [x] `scripts/create_sample_inventory.py`
- [x] `scripts/load_codex_from_yaml.py`
- [x] `scripts/match_franchise_characters.py`
- [x] `scripts/match_variants_to_units.py`
- [x] `scripts/normalize_inventory.py`

Status: These root-level shims have been decommissioned to prevent accidental use. Where direct file deletion was not applied, the files now hard-fail with a clear message directing users to the canonical `scripts/<subfolder>/...` path. All tasks/docs/tests point to canonical entrypoints.

5) Add guardrails to prevent regression
- Add a CI check or pre-commit hook that fails if a new `scripts/*.py` file (at root) matches a name that exists in any `scripts/*/*` subfolder.
- Option: add a tiny `scripts/_shim_guard.py` invoked in tests to assert no known shims exist.

## Timeline and batching
- Batch 1: A–D cohorts (Bootstrap, Inventory, Loaders, Normalize/Match) — highest traffic; update tasks and remove shims in one PR.
- Batch 2: E–F cohorts (Kits, Cleanup/Repair) — moderate traffic.
- Batch 3: G–H cohorts (Reports/Analysis, Utilities) — low risk; unify `debug_franchise_sample.py` location.

## Risks and mitigations
- VS Code tasks drift: run tasks after edits to ensure quotes/paths are pwsh-safe; prefer `--db-url` over `$env:...`.
- External scripts/users: deprecation window with clear stderr warning before removal.
- Windows long paths: keep canonical scripts under subfolders (current structure is safe) and avoid symlinks.

## Success criteria
- No root-level duplicates remain; all commands and tasks reference canonical subfolder scripts.
- All tests pass; common operational commands run successfully in PowerShell with the venv.
- `scripts/README.md` accurately reflects the canonical CLI surface and stays current.

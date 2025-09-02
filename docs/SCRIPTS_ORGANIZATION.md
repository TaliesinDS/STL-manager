# Scripts organization proposal (Mini Beast)

This proposes a clean structure for `scripts/`, maps each current script to a category and destination, and recommends keep/merge/deprecate actions. Goals: safer workflows, clearer discoverability, consistent flags, and easier long‑term maintenance.

## Goals and conventions

- Separation of concerns: bootstrap/init, scan/inventory, load/ingest, normalize/match, kits/backfill, cleanup/repair, reports/analysis, and utilities.
- Defaults are safe: dry‑run by default; use `--apply` to write. Prefer `--db-url` for DB selection (PowerShell‑safe).
- Uniform CLI: `--db-url`, `--apply`, `--out reports/<script>_YYYYMMDD_HHMMSS.json` for any script that writes reports.
- Cross‑platform: Python scripts; Windows‑specific `.ps1` kept under a Windows tools subfolder.
- Logs and test artifacts kept out of `scripts/` root; put under `reports/` and `tests/fixtures/`.

## Proposed folder structure

```
scripts/
  00_bootstrap/           # create/upgrade DB, Alembic helpers, one‑time migrations
  10_inventory/           # quick scans, archiver helpers, inventory creation
  20_loaders/             # load YAML vocab (systems/factions/units/parts), designers, franchises, inventory
  30_normalize_match/     # normalization + all matchers (units/franchise/parts) and proposal application
  40_kits/                # kit detection/backfill, virtual parent linking, targeted kit fixers
  50_cleanup_repair/      # data hygiene, orphans, junk removal, prune/merge, targeted repairs
  60_reports_analysis/    # reports, counts, coverage, verification/inspection scripts
    maintenance/             # one-off maintenance utilities (e.g., MMF YAML cleanup)
  90_util/                # show/list helpers, debug tools, one‑off inspectors, dev helpers
  windows_tools/          # PowerShell helpers (extractor, open window, one‑click templates)
  legacy/                 # archived/deprecated once migrated or superseded by Alembic/other flows
```

## Naming rules

- Use imperative verbs and subjects: `load_*.py`, `match_*.py`, `repair_*.py`, `report_*.py`.
- Prefer singular actionable names per script (avoid overlapping responsibilities).
- Restrict platform‑specific logic (.ps1/.bat) to `windows_tools/` and document usage in `scripts/README.md`.

## Script inventory and recommendations

Legend: Keep = retain as‑is (with minor CLI standardization), Merge = fold into another canonical script, Deprecate = move to `legacy/` with note.

| Script | Proposed destination | Action | Notes |
|---|---|---|---|
| annotate_proposals_with_hints.py | 60_reports_analysis/ | Keep | Enhances reports pre‑apply. Ensure timestamped `--out`.
| apply_proposals_from_report.py | 30_normalize_match/ | Keep | Canonical applier for proposal JSON; standardize `--db-url`.
| apply_proposals_to_v1.py | legacy/ | Deprecate | Older path‑specific applier; superseded by the canonical applier.
| apply_sample_folder_tokens.py | 30_normalize_match/ | Keep | If still useful; else merge into `normalize_inventory.py` flags.
| apply_vocab_matches.py | 30_normalize_match/ | Keep | For vocab‑driven proposals; share code with applier.
| assign_codex_units_aos.py | 30_normalize_match/ | Merge | Fold into `match_variants_to_units.py` under `--system aos`.
| backfill_kits.py | 40_kits/ | Keep | Structure‑only backfill; parent/child/group, no parts matching.
| bootstrap_db.py | 00_bootstrap/ | Merge | Merge with `create_fresh_db.py` into single `bootstrap_db.py` using Alembic.
| bootstrap_dev.ps1 | windows_tools/ | Keep | Document in scripts README; optional.
| check_character_conflicts.py | 60_reports_analysis/ | Keep | Diagnostics report.
| check_codex_duplicates.py | 60_reports_analysis/ | Keep | Diagnostics report.
| cleanup_merge_leaf_variants.py | 50_cleanup_repair/ | Keep | Data hygiene.
| cleanup_remove_junk_only_variants.py | 50_cleanup_repair/ | Keep | Ensures no image‑only variants.
| clean_proposals_file.py | 60_reports_analysis/ | Keep | Report sanitation.
| clear_variant_franchise.py | 50_cleanup_repair/ | Keep | Targeted clearing tool.
| compute_hashes.py | 10_inventory/ | Keep | File hashing; consider worker batches.
| count_franchise_characters.py | 60_reports_analysis/ | Keep | Counts for coverage.
| count_null_franchise.py | 60_reports_analysis/ | Keep | Gap report.
| create_and_stamp.py | 00_bootstrap/ | Deprecate | Use Alembic CLI; move to legacy with note.
| create_fresh_db.py | 00_bootstrap/ | Merge | Merge into `bootstrap_db.py`.
| create_sample_inventory.py | 10_inventory/ | Keep | Inventory generator.
| db_check.py | 60_reports_analysis/ | Merge | Overlaps `inspect_db.py`; consolidate into one inspector.
| debug_franchise_sample.py | 90_util/ | Keep | Debug helper.
| debug_matching_state.py | 60_reports_analysis/ | Keep | Inspector report.
| debug_variant_fields.py | 60_reports_analysis/ | Keep | Inspector report.
| delete_variant.py | 50_cleanup_repair/ | Keep | Targeted delete with safety.
| dump_one_file.py | 90_util/ | Keep | Utility.
| dump_residual_token_counts.py | 60_reports_analysis/ | Keep | Token residuals.
| export_codex_candidates.py | 60_reports_analysis/ | Keep | Audit export.
| Extract-Archives.ps1 | windows_tools/ | Keep | Already documented; keep README with it.
| filter_proposals.py | 60_reports_analysis/ | Keep | Report post‑processing.
| find_vocab_matches.py | 30_normalize_match/ | Keep | Proposal generator; ensure `--out` timestamp.
| fix_infernus_kit.py | 40_kits/ | Keep | Targeted kit repair (document as example pattern).
| fix_skarix_designer.py | 50_cleanup_repair/ | Keep | Targeted cleaner example.
| gen_migration_from_metadata.py | 00_bootstrap/ | Deprecate | Prefer Alembic revisions; move to legacy.
| ignored_tokens.txt | 30_normalize_match/ | Keep | Treat as data; possibly move to `vocab/`.
| init_db.py | 00_bootstrap/ | Merge | Into `bootstrap_db.py`.
| inspect_db.py | 60_reports_analysis/ | Keep | Canonical DB inspector.
| inspect_db_characters.py | 60_reports_analysis/ | Keep | Focused inspector.
| inspect_inference.py | 60_reports_analysis/ | Keep | Inference inspector.
| inspect_orphan_tokens.py | 60_reports_analysis/ | Keep | Diagnostics.
| inspect_sqlite.py | legacy/ | Deprecate | Redundant with other inspectors.
| inspect_vocab_and_variants.py | 60_reports_analysis/ | Keep | Cross‑view inspector.
| launcher_debug.log | reports/ | Move | Artifact; keep logs under `reports/`.
| link_virtual_parent.py | 40_kits/ | Keep | Virtual parent creation/linking.
| list_variant_files.py | 90_util/ | Keep | Utility.
| load_codex_from_yaml.py | 20_loaders/ | Keep | Canonical unit loader for YAML (40K/HH/AoS).
| load_designers.py | 20_loaders/ | Keep | Designers vocab loader.
| load_franchises.py | 20_loaders/ | Keep | Franchises vocab loader.
| cleanup_mmf_collections.py | maintenance/ | Keep | Prune non-designer MMF entries from YAML collections.
| load_sample.py | 20_loaders/ | Keep | Inventory ingester.
| match_franchise_characters.py | 30_normalize_match/ | Keep | Franchise/character matcher.
| match_parts_to_variants.py | 30_normalize_match/ | Keep | New parts matcher; links kit children → Parts.
| match_variants_to_units.py | 30_normalize_match/ | Keep | Unit matcher for all systems.
| match_collections.py | 30_normalize_match/ | Keep | Match variants to per-designer collections (YAML SSOT; optional MMF refill).
| migrate_add_columns.py | legacy/ | Deprecate | Superseded by Alembic migrations.
| migrate_codex_to_character.py | 50_cleanup_repair/ | Keep | Safe one‑time field migration; document as legacy fixer.
| normalize_inventory.py | 30_normalize_match/ | Keep | Core normalization.
| one_click_start_template.bat | windows_tools/ | Keep | Template; optional.
| open_app_window.ps1 | windows_tools/ | Keep | Optional convenience.
| parse_normalization_stdout.py | 60_reports_analysis/ | Keep | Parser for normalizer logs.
| prune_invalid_variants.py | 50_cleanup_repair/ | Keep | Hygiene.
| quick_scan.py | 10_inventory/ | Keep | Tokenizer shared utility; avoid duplication.
| README.md | root of scripts/ | Keep | Update with new structure and links.
| README_ExtractArchives.md | windows_tools/ | Move | Co‑locate with the extractor.
| remove_loose_files_from_variant.py | 50_cleanup_repair/ | Keep | Hygiene.
| repair_orphan_variants.py | 50_cleanup_repair/ | Keep | Model‑files‑only recreate; already safe.
| repair_sigmar_variants.py | 50_cleanup_repair/ | Keep | Targeted fixer.
| report_codex_counts.py | 60_reports_analysis/ | Keep | Report.
| report_franchise_coverage.py | 60_reports_analysis/ | Keep | Report.
| run_quick_scan.bat | windows_tools/ | Keep | Helper to run scan.
| scan_sample_inventory.py | 10_inventory/ | Keep | Scanner wrapper.
| set_alembic_version.py | 00_bootstrap/ | Deprecate | Prefer Alembic CLI `stamp`; archive.
| set_variant_franchise.py | 50_cleanup_repair/ | Keep | Manual setter with `--apply`.
| show_variant.py | 90_util/ | Keep | Already supports `--db-url`; good.
| sync_characters_to_vocab.py | 20_loaders/ | Keep | Sync tool.
| sync_designers_from_tokenmap.py | 20_loaders/ | Keep | Sync tool.
| sync_franchise_tokens_to_vocab.py | 20_loaders/ | Keep | Sync tool.
| test folder.rar | tests/fixtures/archives/ | Move | Test archive; keep out of scripts root.
| test folder 2.rar | tests/fixtures/archives/ | Move | Test archive; keep out of scripts root.
| test_write_variant.py | tests/ | Move | Belongs under `tests/`.
| validate_tokenize_sample.py | 10_inventory/ | Keep | Validator; or convert to pytest.
| variant_field_stats.py | 60_reports_analysis/ | Keep | Stats.
| verify_applied_matches.py | 60_reports_analysis/ | Keep | Verification.
| verify_migration_output.py | 60_reports_analysis/ | Keep | Verification.
| verify_tokens_written.py | 60_reports_analysis/ | Keep | Verification.
| propose_missing_collections.py | 60_reports_analysis/ | Keep | Propose draft YAML entries for designer collections missing from YAML.

## Recommended workflow from new DB → app

1) 00_bootstrap
- `bootstrap_db.py` (single entry): create DB, run Alembic migrations to latest. Optionally seed minimal `game_system`/`faction` rows.

2) 10_inventory
- `create_sample_inventory.py` or scanner → JSON inventory → `load_sample.py` ingests into DB.
- Optional hashing: `compute_hashes.py`.

3) 20_loaders
- Load vocab: `load_designers.py`, `load_franchises.py`, and YAML codex files via `load_codex_from_yaml.py` (40K/AoS/HH). Parts vocab future‑ready here too.

4) 30_normalize_match
- `normalize_inventory.py` (dry‑run, then `--apply`).
- `match_franchise_characters.py` and `match_variants_to_units.py` for canonical matching; apply proposals with `apply_proposals_from_report.py` if using two‑stage flow.
- `match_parts_to_variants.py` (optional) to link kit children to Parts (dry‑run first).

5) 40_kits
- `backfill_kits.py` to mark/link kits and group children; targeted `fix_*_kit.py` or `link_virtual_parent.py` for edge cases.

6) 50_cleanup_repair
- Hygiene scripts (junk removal, prune/merge, orphan repair) and targeted fixers.

7) 60_reports_analysis
- Coverage, duplicate checks, residual tokens, verification reports.

8) 90_util
- Helpers (`show_variant.py`, `list_variant_files.py`) and ad‑hoc inspectors.

## MyMiniFactory (MMF) collections workflow (new)

- `scripts/10_integrations/update_collections_from_mmf.py` appends latest N designer collections into `vocab/collections/<designer_key>.yaml`.
- `vocab/mmf_usernames.json` contains `designer_key -> mmf_username` and is preferred over any hard-coded map.
- `scripts/maintenance/cleanup_mmf_collections.py` removes entries whose `source_urls` don’t match the designer’s MMF username (safe cleanup).

Augment with proposer for gaps:
- `scripts/60_reports_analysis/propose_missing_collections.py` scans designer-scoped variants with no collection yet and drafts entries under `vocab/collections/_drafts/`. Review, add `source_urls`, then move into canonical YAML.

Run order (suggested):
1) Adjust/add usernames in `vocab/mmf_usernames.json`.
2) Clean existing YAMLs:
  `python scripts/maintenance/cleanup_mmf_collections.py`
3) Fetch and append up to 5 newest per designer:
  `python scripts/10_integrations/update_collections_from_mmf.py --max 5 --apply`

## Standardize CLIs and outputs (short checklist)

- Add `--db-url` to any writer/reader script that doesn’t have it yet (prefer explicit over env vars on Windows).
- Dry‑run default; require `--apply` to commit.
- Reports always timestamped: `reports/<script>_YYYYMMDD_HHMMSS.json`.
- Ensure `sqlalchemy` Session.get() usage to avoid legacy warnings (low priority).

## Migration plan (incremental, low‑risk)

1) Create subfolders above; move non‑code artifacts now:
- `scripts/launcher_debug.log` → `reports/`.
- `scripts/test folder*.rar` → `tests/fixtures/archives/`.
- `scripts/test_write_variant.py` → `tests/`.
- `scripts/README_ExtractArchives.md` → `scripts/windows_tools/`.

2) Move Windows helpers into `scripts/windows_tools/`: `Extract-Archives.ps1`, `run_quick_scan.bat`, `open_app_window.ps1`, `one_click_start_template.bat`, `bootstrap_dev.ps1`.

3) Consolidate bootstrap:
- Merge `create_fresh_db.py` and `init_db.py` into `bootstrap_db.py` (00_bootstrap/).
- Move `create_and_stamp.py`, `gen_migration_from_metadata.py`, `set_alembic_version.py`, `migrate_add_columns.py` into `legacy/` with a README noting Alembic is canonical.

4) Re‑home the rest per the table. Update imports only if scripts refer to siblings (most are standalone entrypoints).

5) Standardize flags in pass 2: ensure `--db-url`, `--apply`, `--out` across writers and reporters; add timestamped filenames.

6) Update `scripts/README.md` to reflect new structure and link to this document; add a short “common patterns” section.

7) Optional: Add VS Code tasks grouped by these stages (e.g., “Run matcher (dry‑run)”, “Run kits backfill (apply)”, “Run reports”).

## Deprecations and legacy notes

- Alembic is canonical for schema changes; archive bespoke migration helpers in `scripts/legacy/` and rely on `alembic revision --autogenerate` + `alembic upgrade head`.
- System‑specific matchers should be subcommands/flags on a canonical matcher rather than separate ad‑hoc scripts. Example: fold `assign_codex_units_aos.py` into `match_variants_to_units.py --system aos`.
- Keep targeted fixers (`fix_*`) but document each with a header explaining scope and a suggested removal window after use.

## Open follow‑ups (can be done incrementally)

- Expand `match_parts_to_variants.py` classification depth to scan first 3–4 segments so fewer children are skipped.
- Add a tiny `scripts/lib/` shared module for common CLI helpers (`rebind_db(db_url)`, timestamped `out_path()`, session context). Gradually migrate scripts to it.
- Create lightweight smoke tests for normalization and matchers under `tests/` to guard against regressions.

---
This plan keeps your current workflow intact but makes the next steps predictable: you can move files in small batches and standardize CLIs without breaking muscle memory.

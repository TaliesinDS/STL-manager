# Workflow Tests Guide (Plain-English Edition)

This guide explains what the “workflow tests” do, how you can run them on Windows PowerShell, and how to read the results. It’s written to be approachable if you’re not deep into Python or databases.

## What are “workflow tests” and why do we have them?

Think of the project as a pipeline that takes folders of 3D model files, recognizes what they are, links them to game data (units, characters), and then cleans things up and reports on the results. The workflow tests run this pipeline end-to-end on a small sample so we know everything still works after changes.

At a high level, the pipeline does this:
- Create a fresh, temporary database so we don’t touch your real data.
- Scan a tiny “sample store” to make an inventory of files.
- Load game vocab (units, factions, parts) so we know what we’re matching to.
- Normalize and match: tidy up fields and link files to units/characters.
- Handle “kits” (multi-part sets with bodies/heads/weapons subfolders).
- Run safe cleanups and produce simple reports.

All of this is automated by tests so we can run it in one command and get a clear PASS/FAIL.

## A few terms in simple language

- Variant: a folder in your library that represents a model (or a container folder). It can have files (STL, OBJ, etc.).
- Kit: a model sold or organized as a set of parts (e.g., bodies, heads, weapons). Parent folder = kit container; subfolders = kit children.
- Codex / vocab: the “dictionary” of known units, factions, and parts we match against.
- Dry-run: show what would happen without changing the database. Safe mode.
- Apply: make the actual changes in the temporary database.
- Shim: a small compatibility wrapper so old script names still work after we reorganized folders.

## What’s inside the tests folder

- Location: `tests/workflow/`
  - `conftest.py`: shared helpers for the tests.
    - Picks the right Python in your virtual environment (`.venv`).
    - Creates a temporary database at `.pytest-tmp/stl_manager_e2e.db`.
    - Runs scripts as subprocesses and sets `PYTHONPATH` automatically so imports work.
  - `test_smoke_workflow.py`: the “smoke test” of the whole pipeline.
    - Bootstraps the temporary DB.
    - Creates and loads a tiny sample inventory.
    - Runs the normalizer in dry-run (writes a JSON report) and then in apply mode (twice, to ensure it’s safe to re-run).
    - Checks a few legacy shims (old script paths) to see that `--help` works and a quick dry-run can run.
  - `test_loaders_and_matchers.py`: focuses on vocab loaders and unit matching.
    - Loads designers, franchises, three codex files (40K, AoS, Heresy), and the 40K parts vocab (wargear, bodies).
    - Runs the unit matcher (dry-run to a JSON file), then apply mode, then verifies that the changes made sense using a verification utility.
  - `test_franchise_match_apply.py`:
    - Runs the franchise/character matcher (dry-run), applies proposals, and verifies via a helper script.
    - Also runs a tiny “compute hashes” sample just to ensure the hashing script works.
  - `test_kits_backfill.py`:
    - Runs the kits backfill in dry-run (writes a JSON report) and runs two safe cleanup/repair scripts in dry-run.
    - Applies kits backfill and runs it again to make sure re-running doesn’t cause extra changes (idempotent).

All tests are tagged as workflow tests, so you can run just these with `-k workflow`.

## What success looks like (in plain terms)

If everything is healthy:
- The temporary database is created under `.pytest-tmp/`.
- JSON reports are written either under `reports/test_artifacts/` (when tests specify a path) or under `reports/` with a timestamp in the name.
- “Dry-run” steps finish with exit code 0 and produce reasonable JSON. For our small sample, it’s normal that some reports have empty lists (there simply isn’t much to match).
- “Apply” steps succeed and are safe to run twice (the second run shouldn’t change anything).

## Where the files show up

You’ll most commonly see:
- Database: `.pytest-tmp/stl_manager_e2e.db` (safe, disposable).
- Reports (examples):
  - `reports/test_artifacts/normalize_inventory_test.json`
  - `reports/test_artifacts/match_units_with_children_test.json`
  - `reports/test_artifacts/match_franchise_test.json`
  - `reports/test_artifacts/match_parts_test.json`

What’s inside these reports?
- Unit matcher report: a JSON object with a `proposals` list (each proposal is a suggested link between a folder and a unit).
- Franchise matcher report: also a JSON object with `proposals` (may be empty in our tiny sample).
- Parts matcher report: contains `db_url`, whether we used `apply`, and counts of links/creations/skips.

Tip: Empty `proposals` doesn’t mean failure. On a small sample, it often just means there wasn’t a strong match.

## How to run the tests (Windows PowerShell)

Use the Python inside your virtual environment so the right packages and settings are used.

- Run everything:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q
```

- Only the workflow tests:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q -k workflow
```

- Make the output more chatty (handy when something fails):

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q -k workflow -vv -s
```

- Run one test file:

```powershell
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q tests/workflow/test_kits_backfill.py
```

## Reading failures without the jargon

Here are the most common issues and what they mean:

- “no such table …”: We tried to read from the database before creating it. Fix: make sure the bootstrap step ran against the same temporary DB.
- “unrecognized arguments: --db-url”: Some scripts prefer reading the DB URL from an environment variable (`STLMGR_DB_URL`). The tests already handle this by passing it internally; if you run a script by hand, set `STLMGR_DB_URL` first or use the canonical script that supports `--db-url`.
- “import module failed” or similar: Usually means Python can’t see the project root. The tests set `PYTHONPATH` automatically; if running manually, ensure you start from the repo root.
- Wrong Python: If you see odd missing-package errors, double-check you’re using the `.venv` Python shown above.

## FAQ

- Why are some reports empty?
  - The sample is intentionally small. Empty lists are fine; the test checks that the tool ran and wrote valid JSON.

- Why both dry-run and apply?
  - Dry-run shows what would happen without writing to the DB. Apply proves changes can be written and that running again does not create duplicates.

- What is a shim and why do we test it?
  - A shim is a small wrapper so old entrypoints still work after we moved files. We test `--help` and a tiny dry-run so users with old habits aren’t broken.

## Troubleshooting checklist

- Start from the repository root in your terminal.
- Activate your virtual environment (or use the explicit Python path shown above).
- If you run one script by hand, set the DB URL to the temp DB:
  - As a one-off in PowerShell: `$env:STLMGR_DB_URL = "sqlite:///./.pytest-tmp/stl_manager_e2e.db"`
- Re-run with `-vv -s` for more details if something fails.

## Want to extend the tests?

- Copy the style in `tests/workflow/`:
  - Use `venv_python` to call scripts.
  - Prefer writing reports to `reports/test_artifacts/` so they’re easy to find.
  - If you add an “apply” step, also re-run it once to confirm nothing new happens (idempotent).
  - Keep JSON checks simple and resilient (e.g., “has key X” rather than exact counts).

---

If you want the more technical version (full checklist and goals), see `docs/SCRIPTS_WORKFLOW_TEST_PLAN.md`.
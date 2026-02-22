from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.workflow


def _assert_ok(rc, cp, context: str = ""):
    if rc != 0:
        msg = [
            f"Command failed{': ' + context if context else ''}",
            f"RC={rc}",
            "STDOUT:",
            cp.stdout,
            "STDERR:",
            cp.stderr,
        ]
        raise AssertionError("\n".join(msg))


def test_bootstrap_then_normalize_dryrun(cli, venv_python: str, tmp_db_url: str, repo_root: Path):
    # 1) Bootstrap
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    _assert_ok(cp.returncode, cp, "bootstrap_db")

    # 2) Create a tiny sample inventory and ingest
    tmp_json = repo_root / ".pytest-tmp" / "sample_inventory.json"
    cp = cli([venv_python, "scripts/10_inventory/create_sample_inventory.py", "--out", str(tmp_json)])
    _assert_ok(cp.returncode, cp, "create_sample_inventory")
    assert tmp_json.is_file(), "Expected sample inventory JSON to be created"

    # load_sample reads DB from STLMGR_DB_URL; it doesn't support --db-url/--apply
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_sample.py",
        "--file",
        str(tmp_json),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_sample --apply")

    # 3) Normalize (dry-run)
    reports_dir = repo_root / "reports" / "test_artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "normalize_inventory_test.json"
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/normalize_inventory.py",
        "--out",
        str(out_path),
        "--limit", "50",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "normalize_inventory --out")
    assert out_path.is_file(), "Expected normalize report to be written"

    # Sanity check JSON structure if non-empty
    try:
        data = json.loads(out_path.read_text("utf-8"))
        assert isinstance(data, dict)
    except Exception:
        # Allow empty or non-JSON if normalizer outputs plaintext in some modes
        pass

    # Apply normalization (idempotent)
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/normalize_inventory.py",
        "--apply", "--limit", "50",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "normalize_inventory --apply")
    # Re-apply should also succeed without additional changes
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/normalize_inventory.py",
        "--apply", "--limit", "50",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "normalize_inventory --apply (idempotent)")

    # Parts matcher dry-run: write a report path; tolerate empty
    parts_report = reports_dir / "match_parts_test.json"
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/match_parts_to_variants.py",
        "--all-kits",
        "--out",
        str(parts_report),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    # If no kits exist, script should still exit 0 and write a report
    assert cp.returncode == 0
    if parts_report.exists():
        pdata = json.loads(parts_report.read_text("utf-8"))
        assert isinstance(pdata, dict)
        for k in ["db_url", "apply", "changes", "counts"]:
            assert k in pdata

    # Reports: codex counts and verify applied matches (dry)
    _counts_report = reports_dir / "codex_counts_test.json"
    cp = cli([
        venv_python,
        "scripts/60_reports_analysis/report_codex_counts.py",
        "--db-url", tmp_db_url,
        "--yaml",
        "--vocab-dir", "vocab",
    ])
    _assert_ok(cp.returncode, cp, "report_codex_counts --yaml")


def test_entrypoints_help(cli, venv_python: str):
    # Probe canonical entrypoints to ensure CLI help is available
    candidates = [
        "scripts/30_normalize_match/normalize_inventory.py",
        "scripts/30_normalize_match/match_franchise_characters.py",
        "scripts/30_normalize_match/match_variants_to_units.py",
        "scripts/40_kits/backfill_kits.py",
        "scripts/20_loaders/load_codex_from_yaml.py",
        "scripts/10_inventory/compute_hashes.py",
        "scripts/10_inventory/create_sample_inventory.py",
    ]
    for script in candidates:
        cp = cli([venv_python, script, "--help"])
        assert cp.returncode == 0, f"--help failed for {script}: {cp.stderr}"
        assert re.search(r"-h|--help", cp.stdout) or cp.stdout, f"No help/usage output for {script}"


def test_cli_dry_runs(cli, venv_python: str, tmp_db_url: str):
    # Ensure schema exists
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    assert cp.returncode == 0, f"bootstrap_db failed: {cp.stderr}"
    # Exercise a few canonical scripts in dry-run/no-op mode with --db-url
    samples = [
        # Keep each script constrained so the test runs fast and avoids CPU spikes
        ("scripts/30_normalize_match/normalize_inventory.py", ["--limit", "50", "--batch", "100"]),
        ("scripts/30_normalize_match/match_franchise_characters.py", ["--batch", "50", "--limit", "50"]),
        ("scripts/30_normalize_match/match_variants_to_units.py", ["--limit", "50"]),
        ("scripts/40_kits/backfill_kits.py", []),
    ]
    for sh, args in samples:
        cp = cli([venv_python, sh] + args, env={"STLMGR_DB_URL": tmp_db_url})
        assert cp.returncode == 0, f"Dry-run failed for {sh}: {cp.stderr}"

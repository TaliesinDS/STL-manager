from __future__ import annotations

import json
from pathlib import Path
import pytest


pytestmark = pytest.mark.workflow


def _assert_ok(rc, cp, context: str = ""):
    if rc != 0:
        raise AssertionError(f"{context} failed: rc={rc}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")


def _maybe_read_json(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def test_franchise_match_then_apply(cli, venv_python: str, tmp_db_url: str, repo_root: Path):
    # Ensure DB exists (bootstrap)
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    _assert_ok(cp.returncode, cp, "bootstrap_db")

    # Minimum preconditions: sample inventory present
    inv = repo_root / ".pytest-tmp" / "sample_inventory.json"
    if not inv.exists():
        cp = cli([venv_python, "scripts/10_inventory/create_sample_inventory.py", "--out", str(inv)])
        _assert_ok(cp.returncode, cp, "create_sample_inventory")
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_sample.py",
        "--file",
        str(inv),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_sample --apply")

    # Dry-run matcher
    reports_dir = repo_root / "reports" / "test_artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "match_franchise_test.json"
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/match_franchise_characters.py",
        "--batch",
        "100",
        "--out",
        str(out_path),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "match_franchise_characters --out")
    assert out_path.exists(), "Expected franchise matcher report"
    data = _maybe_read_json(out_path)
    # Schema sanity: either dict with proposals or empty list OK
    if isinstance(data, dict):
        assert "proposals" in data

    # Apply proposals (even if report is empty, apply script should succeed)
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/apply_proposals_from_report.py",
        "--report",
        str(out_path),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "apply_proposals_from_report")

    # Optional: compute hashes dry-run on a small limit to ensure script runs
    cp = cli([
        venv_python,
        "scripts/10_inventory/compute_hashes.py",
        "--limit",
        "5",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "compute_hashes --limit 5")

    # Verify applied matches using the same report
    cp = cli([
        venv_python,
        "scripts/60_reports_analysis/verify_applied_matches.py",
        "--db-url", tmp_db_url,
        "--file", str(out_path),
    ])
    _assert_ok(cp.returncode, cp, "verify_applied_matches (franchise)")

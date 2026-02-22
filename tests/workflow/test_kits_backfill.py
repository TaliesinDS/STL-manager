from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.workflow


def _assert_ok(rc, cp, context: str = ""):
    if rc != 0:
        raise AssertionError(f"{context} failed: rc={rc}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")


def test_kits_backfill_dryrun(cli, venv_python: str, tmp_db_url: str, repo_root: Path):
    # Bootstrap DB
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    _assert_ok(cp.returncode, cp, "bootstrap_db")

    # Load sample inventory
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
    _assert_ok(cp.returncode, cp, "load_sample")

    # Run backfill kits dry-run and check report
    reports_dir = repo_root / "reports" / "test_artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "backfill_kits_test.json"
    cp = cli([
        venv_python,
        "scripts/40_kits/backfill_kits.py",
        "--out",
        str(out_path),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "backfill_kits --out")
    assert out_path.exists(), "Expected backfill kits report to be written"

    # Cleanup/Repair (dry-run): prune_invalid_variants and repair_orphan_variants
    cp = cli([
        venv_python,
        "scripts/50_cleanup_repair/prune_invalid_variants.py",
        "--out",
        str(reports_dir),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "prune_invalid_variants (dry-run)")

    cp = cli([
        venv_python,
        "scripts/50_cleanup_repair/repair_orphan_variants.py",
        "--limit",
        "50",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "repair_orphan_variants (dry-run)")


def test_kits_backfill_apply(cli, venv_python: str, tmp_db_url: str, repo_root: Path):
    # Bootstrap and load sample if needed
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    _assert_ok(cp.returncode, cp, "bootstrap_db")
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
    _assert_ok(cp.returncode, cp, "load_sample")

    # Apply backfill kits (safe to run even if no kits; should exit 0)
    cp = cli([
        venv_python,
        "scripts/40_kits/backfill_kits.py",
        "--apply",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "backfill_kits --apply")

    # Idempotent re-apply
    cp = cli([
        venv_python,
        "scripts/40_kits/backfill_kits.py",
        "--apply",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "backfill_kits --apply (idempotent)")

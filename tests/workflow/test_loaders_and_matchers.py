from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.workflow


def _assert_ok(rc, cp, context: str = ""):
    if rc != 0:
        raise AssertionError(f"{context} failed: rc={rc}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")


def test_load_vocabs_and_match_units(cli, venv_python: str, tmp_db_url: str, repo_root: Path):
    # Ensure DB exists (bootstrap)
    cp = cli([venv_python, "scripts/00_bootstrap/bootstrap_db.py", "--db-url", tmp_db_url, "--use-metadata"])
    _assert_ok(cp.returncode, cp, "bootstrap_db")

    # Load minimal vocab sets
    # load_designers expects a positional path and --commit (no --db-url)
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_designers.py",
        "vocab/designers_tokenmap.md",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_designers --commit")

    # load_franchises expects a directory path and --commit
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_franchises.py",
        "vocab/franchises",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_franchises --commit")

    # Load at least one codex file (40K) to allow unit matcher to execute sanely
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_codex_from_yaml.py",
        "--file",
        "vocab/codex_units_w40k.yaml",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_codex_from_yaml (40K)")

    # Also load AoS and Heresy codex manifests (commit)
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_codex_from_yaml.py",
        "--file",
        "vocab/codex_units_aos.yaml",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_codex_from_yaml (AoS)")

    cp = cli([
        venv_python,
        "scripts/20_loaders/load_codex_from_yaml.py",
        "--file",
        "vocab/codex_units_horus_heresy.yaml",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_codex_from_yaml (Heresy)")

    # Load parts vocab for 40K (wargear and bodies)
    cp = cli([
        venv_python,
        "scripts/20_loaders/load_codex_from_yaml.py",
        "--file",
        "vocab/wargear_w40k.yaml",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_codex_from_yaml (wargear_w40k)")

    cp = cli([
        venv_python,
        "scripts/20_loaders/load_codex_from_yaml.py",
        "--file",
        "vocab/bodies_w40k.yaml",
        "--commit",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "load_codex_from_yaml (bodies_w40k)")

    # Run unit matcher dry-run with children; just verify it runs and writes a report
    reports_dir = repo_root / "reports" / "test_artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "match_units_with_children_test.json"
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/match_variants_to_units.py",
        "--include-kit-children",
        "--limit",
        "50",
        "--out",
        str(out_path),
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "match_variants_to_units --out")
    assert out_path.exists(), "Expected unit matcher report to be written"
    # Schema sanity: ensure proposals list exists
    import json
    data = json.loads(out_path.read_text("utf-8"))
    assert isinstance(data, dict) and "proposals" in data and isinstance(data["proposals"], list)

    # Apply unit matches (if any) by re-running with --apply and a small limit, then idempotency check
    cp = cli([
        venv_python,
        "scripts/30_normalize_match/match_variants_to_units.py",
        "--include-kit-children",
        "--limit",
        "50",
        "--apply",
        "--out",
        str(out_path),
        "--append-timestamp",
    ], env={"STLMGR_DB_URL": tmp_db_url})
    _assert_ok(cp.returncode, cp, "match_variants_to_units --apply")

    # Verify applied matches utility runs against the last proposals JSON if present
    # (we don't depend on exact contents; just ensure it executes)
    latest = out_path if out_path.exists() else None
    if latest:
        cp = cli([
            venv_python,
            "scripts/60_reports_analysis/verify_applied_matches.py",
            "--db-url", tmp_db_url,
            "--file", str(latest),
        ])
        _assert_ok(cp.returncode, cp, "verify_applied_matches")

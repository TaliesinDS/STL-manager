from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
import subprocess
import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    # tests/workflow/ -> tests -> repo_root
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def venv_python(repo_root: Path) -> str:
    # Prefer Windows path; fall back to POSIX for portability
    win_path = repo_root / ".venv" / "Scripts" / "python.exe"
    posix_path = repo_root / ".venv" / "bin" / "python"
    if win_path.exists():
        return str(win_path)
    if posix_path.exists():
        return str(posix_path)
    # As a last resort, use sys.executable (developer's interpreter)
    return sys.executable


@pytest.fixture(scope="session")
def tmp_dir(repo_root: Path) -> Path:
    d = repo_root / ".pytest-tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="function")
def tmp_db_url(tmp_dir: Path, repo_root: Path) -> str:
    db_file = tmp_dir / "stl_manager_e2e.db"
    # Ensure a clean slate for each test function that uses this fixture
    if db_file.exists():
        db_file.unlink()
    # Return a relative URL from repo root (so scripts resolve paths consistently)
    rel = Path(".pytest-tmp") / db_file.name
    return f"sqlite:///./{rel.as_posix()}"


def run_cli(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    # Execute a command without invoking a shell to avoid quoting issues
    merged_env = dict(os.environ)
    # Ensure Python can import modules from the repo root (db/, scripts/, etc.)
    py_path = merged_env.get("PYTHONPATH", "")
    sep = ";" if os.name == "nt" else ":"
    if str(cwd) not in (py_path.split(sep) if py_path else []):
        merged_env["PYTHONPATH"] = (py_path + (sep if py_path else "") + str(cwd))
    if env:
        merged_env.update(env)
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, env=merged_env)


@pytest.fixture
def cli(repo_root: Path):
    def _runner(argv: list[str], env: dict | None = None):
        return run_cli(argv, repo_root, env=env)
    return _runner


def ensure_reports_dir(repo_root: Path, sub: str = "test_artifacts") -> Path:
    r = repo_root / "reports" / sub
    r.mkdir(parents=True, exist_ok=True)
    return r


def latest_report(glob_pattern: str, repo_root: Path) -> Path | None:
    matches = sorted(repo_root.glob(glob_pattern))
    return matches[-1] if matches else None

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Avoid collecting the legacy module name that clashes with top-level placeholder
collect_ignore = [
    "test_multilingual_backfill.py",
]


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
        # On Windows a previous engine may briefly hold a handle; retry unlink
        for attempt in range(10):
            try:
                db_file.unlink()
                break
            except (PermissionError, FileNotFoundError):
                # Try to force-close any session engine still pointing at this file
                try:
                    import db.session as _dbs  # type: ignore
                    # Switch to in-memory to drop file handle, then dispose
                    if hasattr(_dbs, 'reconfigure'):
                        _dbs.reconfigure('sqlite:///:memory:')
                    else:
                        try:
                            _dbs.engine.dispose()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(0.1)
        else:
            # As a last resort, rename to a temp unique name to avoid clashes
            try:
                tmp_name = db_file.with_name(db_file.stem + f"_{int(time.time()*1000)}" + db_file.suffix)
                db_file.rename(tmp_name)
            except Exception:
                pass
    # Build an absolute sqlite URL to avoid relative path ambiguity across processes
    abs_path = (repo_root / ".pytest-tmp" / db_file.name).resolve()
    url = f"sqlite:///{abs_path.as_posix()}"
    # Also proactively bind the session engine to this DB for this test process
    try:
        import db.session as _dbs  # type: ignore
        if hasattr(_dbs, 'reconfigure'):
            _dbs.reconfigure(url)
        # Ensure child processes inherit the absolute URL
        os.environ["STLMGR_DB_URL"] = url
    except Exception:
        pass
    return url


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

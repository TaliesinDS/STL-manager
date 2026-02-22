#!/usr/bin/env python3
"""Run pytest only for changed test files (git-aware), with fast fallbacks.

Usage examples (run with your venv Python):
  .\\.venv\\Scripts\\python.exe scripts\\dev\run_changed_tests.py
  .\\.venv\\Scripts\\python.exe scripts\\dev\run_changed_tests.py --since main
  .\\.venv\\Scripts\\python.exe scripts\\dev\run_changed_tests.py --include-workflow

Behavior:
  - Collects changed files from git (staged + unstaged) relative to --since (default: HEAD).
  - If any changed files are tests under 'tests/' matching 'test_*.py', runs pytest only on those paths.
  - Else, runs a fast subset by default: pytest -m "not workflow".
  - Use --include-workflow to run the full suite when no changed tests are found.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_lines(args: list[str]) -> list[str]:
    try:
        cp = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        if cp.returncode != 0:
            return []
        return [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]
    except Exception:
        return []


def discover_changed_files(since: str | None) -> list[str]:
    files: set[str] = set()
    # Unstaged changes
    for ln in _git_lines(["diff", "--name-only"] if not since else ["diff", "--name-only", since]):
        files.add(ln)
    # Staged changes
    for ln in _git_lines(["diff", "--name-only", "--cached"]):
        files.add(ln)
    # Modified in working tree (git index view)
    for ln in _git_lines(["ls-files", "-m"]):
        files.add(ln)
    # Deleted files do not produce runnable tests; ignore
    return sorted(f for f in files if f)


def pick_changed_tests(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        if not p.lower().startswith("tests/"):
            continue
        name = Path(p).name
        if name.startswith("test_") and name.endswith(".py"):
            out.append(p)
    return sorted(set(out))


def run_pytest(pytest_args: list[str]) -> int:
    # Run pytest using current interpreter to ensure venv is used
    cmd = [sys.executable, "-m", "pytest", *pytest_args]
    print("Running:", " ".join(cmd))
    cp = subprocess.run(cmd, cwd=REPO_ROOT)
    return cp.returncode


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run pytest for changed test files; fallback to fast subset.")
    ap.add_argument("--since", default=None, help="Git ref to diff against for changed files (default: working tree vs HEAD)")
    ap.add_argument("--include-workflow", action="store_true", help="When no changed tests, run all tests including workflow")
    ap.add_argument("--print-only", action="store_true", help="Print discovered files/selection and exit")
    args, passthru = ap.parse_known_args(argv)

    changed = discover_changed_files(args.since)
    tests = pick_changed_tests(changed)

    if args.print_only:
        print("Changed files:")
        for f in changed:
            print("  ", f)
        print("\nSelected test files:")
        for t in tests:
            print("  ", t)
        return 0

    if tests:
        return run_pytest(["-q", *tests, *passthru])

    # No changed test files: choose fallback
    if args.include_workflow:
        print("No changed test files; running full suite (including workflow)...")
        return run_pytest(["-q", *passthru])
    else:
        print("No changed test files; running fast subset (-m 'not workflow')...")
        # Disable plugin autoload if the environment requests it
        # Users can set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 for faster startup
        return run_pytest(["-q", "-m", "not workflow", *passthru])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

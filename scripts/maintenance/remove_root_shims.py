#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

# Files we must keep at root because they are used as import facades in code/tests
WHITELIST = {
    "normalize_inventory.py",
    "quick_scan.py",
}

SHIM_MARKERS = (
    "Compatibility shim: delegates to",
    "Compatibility shim for",
    "Deprecated wrapper:",
    "This root-level shim was removed.",
)


def is_root_shim(path: Path) -> bool:
    if path.name in WHITELIST:
        return False
    try:
        text = path.read_text("utf-8", errors="ignore")
    except Exception:
        return False
    # Quick heuristic: only consider direct children under scripts/ as candidates
    if path.parent != SCRIPTS:
        return False
    # Identify typical shim markers
    return any(m in text for m in SHIM_MARKERS)


def discover_shims() -> list[Path]:
    out: list[Path] = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if is_root_shim(p):
            out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Remove legacy root-level shim scripts (dry-run by default)")
    ap.add_argument("--apply", action="store_true", help="Actually delete the files (otherwise dry-run)")
    ap.add_argument("--pattern", default=None, help="Optional regex to filter filenames before deletion")
    args = ap.parse_args(argv)

    shims = discover_shims()
    if args.pattern:
        rx = re.compile(args.pattern)
        shims = [p for p in shims if rx.search(p.name)]

    if not shims:
        print("No removable root-level shims found.")
        return 0

    print("Candidates (root-level shims):")
    for p in shims:
        print("  ", p.relative_to(ROOT))

    if not args.apply:
        print("\nDry-run: no files deleted. Re-run with --apply to remove them.")
        return 0

    errors = 0
    for p in shims:
        try:
            p.unlink()
            print("Deleted:", p.relative_to(ROOT))
        except Exception as e:
            errors += 1
            print(f"Failed to delete {p}: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

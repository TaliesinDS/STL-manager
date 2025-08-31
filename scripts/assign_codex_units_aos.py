"""Deprecated wrapper: use scripts/match_variants_to_units.py --systems aos

This script forwards its CLI to the canonical matcher with --systems aos.
Kept for backward compatibility during migration.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

def main(argv: list[str]) -> int:
    try:
        from scripts.match_variants_to_units import main as units_main  # type: ignore
    except Exception as e:
        print("[error] Failed to import canonical matcher:", e)
        return 1
    # Prepend system selection
    args = ["--systems", "aos", *argv]
    try:
        return int(units_main(args))
    except TypeError:
        # Fallback if main() has no argv param
        return int(units_main())  # type: ignore[misc]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

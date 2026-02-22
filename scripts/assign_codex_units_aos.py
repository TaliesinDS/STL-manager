"""
Wrapper to run the canonical matcher for AoS.
Resolves the matcher implementation by file path to avoid relying on
root-level shim modules.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent  # project root
_MATCHER_PATH = _ROOT / "scripts" / "30_normalize_match" / "match_variants_to_units.py"

def _load_matcher() -> ModuleType:
    if not _MATCHER_PATH.is_file():
        raise FileNotFoundError(f"Matcher not found at {_MATCHER_PATH}")
    spec = importlib.util.spec_from_file_location(
        "scripts.match_variants_to_units_impl", str(_MATCHER_PATH)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load spec for {_MATCHER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # type: ignore[attr-defined]
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str]) -> int:
    try:
        matcher = _load_matcher()
        units_main = getattr(matcher, "main")
    except Exception as e:
        print("[error] Failed to import canonical matcher:", e, file=sys.stderr)
        return 1
    # Prepend system selection
    args = ["--systems", "aos", *argv]
    try:
        return int(units_main(args))  # type: ignore[misc]
    except TypeError:
        # Fallback if main() has no argv param
        return int(units_main())  # type: ignore[call-arg]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Compatibility shim for scripts.match_collections.

Canonical module moved to scripts/30_normalize_match/match_collections.py.
This shim loads it via importlib and re-exports public symbols, including main().
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
_IMPL_PATH = _ROOT / "scripts" / "30_normalize_match" / "match_collections.py"

# Ensure project root is on sys.path for absolute imports like 'db.*'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if not _IMPL_PATH.is_file():
    raise FileNotFoundError(f"Relocated match_collections not found at {_IMPL_PATH}")

_SPEC = importlib.util.spec_from_file_location(
    "scripts.match_collections_impl", str(_IMPL_PATH)
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load spec for {_IMPL_PATH}")
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
# Ensure module is discoverable during execution
sys.modules[_SPEC.name] = _MOD  # type: ignore[attr-defined]
_SPEC.loader.exec_module(_MOD)

# Re-export public names
__all__ = [n for n in dir(_MOD) if not n.startswith("_")]
_g = globals()
for name in __all__:
    _g[name] = getattr(_MOD, name)


def main(argv: list[str]) -> int:  # type: ignore[override]
    impl_main = getattr(_MOD, "main", None)
    if not callable(impl_main):
        return 0
    try:
        res = impl_main(argv)  # type: ignore[misc]
    except TypeError:
        res = impl_main()  # type: ignore[call-arg]
    try:
        return int(res) if res is not None else 0
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

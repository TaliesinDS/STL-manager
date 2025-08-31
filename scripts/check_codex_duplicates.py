"""Compatibility shim for scripts.check_codex_duplicates.

Canonical module moved to scripts/60_reports_analysis/check_codex_duplicates.py.
This shim loads it via importlib and re-exports public symbols, including main().
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
_IMPL_PATH = _ROOT / "scripts" / "60_reports_analysis" / "check_codex_duplicates.py"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if not _IMPL_PATH.is_file():
    raise FileNotFoundError(f"Relocated check_codex_duplicates not found at {_IMPL_PATH}")

_SPEC = importlib.util.spec_from_file_location(
    "scripts.check_codex_duplicates_impl", str(_IMPL_PATH)
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load spec for {_IMPL_PATH}")
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD  # type: ignore[attr-defined]
_SPEC.loader.exec_module(_MOD)

__all__ = [n for n in dir(_MOD) if not n.startswith("_")]
_g = globals()
for name in __all__:
    _g[name] = getattr(_MOD, name)


def main(argv: list[str] | None = None) -> int:  # type: ignore[override]
    impl_main = getattr(_MOD, "main", None)
    if callable(impl_main):
        try:
            return int(impl_main(argv or []))  # type: ignore[misc]
        except TypeError:
            return int(impl_main())  # type: ignore[call-arg]
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
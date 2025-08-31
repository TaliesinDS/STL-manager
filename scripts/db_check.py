"""Deprecated wrapper: use scripts/60_reports_analysis/inspect_db.py instead.

This script forwards to the canonical inspector and is kept for backward compatibility.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv: list[str] | None = None) -> int:
    # Always use path-based dynamic import: folder name starts with a digit and isn't importable via dotted path
    import importlib.util
    from types import ModuleType
    impl_path = _ROOT / "scripts" / "60_reports_analysis" / "inspect_db.py"
    spec = importlib.util.spec_from_file_location("scripts.inspect_db_impl", str(impl_path))
    if spec is None or spec.loader is None:
        print("[error] Cannot locate canonical inspector at", impl_path)
        return 2
    mod: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("scripts.inspect_db_impl", mod)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    fn = getattr(mod, "main", None)
    if callable(fn):
        try:
            return int(fn(argv or []))
        except TypeError:
            return int(fn())  # type: ignore[misc]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Deprecated wrapper: use scripts/00_bootstrap/bootstrap_db.py with --use-metadata.

Example (PowerShell):
  .\.venv\Scripts\python.exe scripts\00_bootstrap\bootstrap_db.py \
      --db-url sqlite:///./data/stl_manager_fresh.db --use-metadata
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv: list[str] | None = None) -> int:
    import importlib.util
    from types import ModuleType
    impl_path = _ROOT / "scripts" / "00_bootstrap" / "bootstrap_db.py"
    spec = importlib.util.spec_from_file_location("scripts.bootstrap_db_impl", str(impl_path))
    if spec is None or spec.loader is None:
        print("[error] Cannot locate canonical bootstrapper at", impl_path)
        return 2
    mod: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("scripts.bootstrap_db_impl", mod)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    fn = getattr(mod, "main", None)
    if callable(fn):
        # Force metadata mode by appending flag if not present
        args = list(argv or [])
        if "--use-metadata" not in args:
            args.append("--use-metadata")
        try:
            return int(fn(args))
        except TypeError:
            return int(fn())  # type: ignore[misc]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

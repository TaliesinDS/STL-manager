"""Compatibility shim: delegates to canonical implementation in scripts/00_bootstrap/bootstrap_db.py"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
CANON = PROJECT / "scripts" / "00_bootstrap" / "bootstrap_db.py"
MODULE_NAME = "scripts.00_bootstrap.bootstrap_db"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, str(CANON))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot locate canonical script at {CANON}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(MODULE_NAME, mod)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_m = _load()
globals().update({k: v for k, v in _m.__dict__.items() if not k.startswith("__")})


def main(argv: list[str] | None = None) -> int:
    fn = getattr(_m, "main", None)
    if fn is None:
        raise SystemExit("canonical module missing main()")
    import sys as _sys
    _argv = _sys.argv[1:] if argv is None else argv
    try:
        return int(fn(_argv))  # type: ignore[misc]
    except TypeError:
        return int(fn())  # type: ignore[misc]


if __name__ == "__main__":
    raise SystemExit(main())

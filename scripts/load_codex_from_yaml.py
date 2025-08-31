"""
Compatibility shim: delegates to canonical implementation in scripts/20_loaders/load_codex_from_yaml.py

This wrapper keeps legacy CLI entrypoint stable while the code lives under the
organized scripts/ folder. It supports both importing symbols and running as a
script. Prefer passing --db-url explicitly on Windows.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
CANON = PROJECT / "scripts" / "20_loaders" / "load_codex_from_yaml.py"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

MODULE_NAME = "scripts.20_loaders.load_codex_from_yaml"


def _load_canonical() -> ModuleType:
    spec = importlib.util.spec_from_file_location(MODULE_NAME, str(CANON))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot locate canonical loader at {CANON}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(MODULE_NAME, mod)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


_mod = _load_canonical()
globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("__")})


def main(argv: list[str] | None = None) -> int:
    # Delegate to canonical main; prefer main(argv) and fall back to main()
    m = _mod
    fn = getattr(m, "main", None)
    if fn is None:
        raise SystemExit("Canonical module missing main()")
    import sys as _sys
    _argv = _sys.argv[1:] if argv is None else argv
    try:
        return fn(_argv)  # type: ignore[misc]
    except TypeError:
        # Fallback if signature differs
        return fn()  # type: ignore[misc]


if __name__ == "__main__":
    raise SystemExit(main())

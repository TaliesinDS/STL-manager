#!/usr/bin/env python3
"""
Import facade for normalize helpers.

Canonical implementation: scripts/30_normalize_match/normalize_inventory.py
This module re-exports public symbols so imports like
    from scripts.normalize_inventory import tokens_from_variant
continue to work even though the canonical file resides in a folder name
that is not a valid Python package identifier.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent  # project root
_IMPL_PATH = _ROOT / "scripts" / "30_normalize_match" / "normalize_inventory.py"

# Ensure project root is on sys.path for absolute imports like 'db.*'
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if not _IMPL_PATH.is_file():
    raise FileNotFoundError(f"Canonical normalize_inventory not found at {_IMPL_PATH}")

_SPEC = importlib.util.spec_from_file_location(
    "scripts.normalize_inventory_impl", str(_IMPL_PATH)
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load spec for {_IMPL_PATH}")
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD  # type: ignore[attr-defined]
_SPEC.loader.exec_module(_MOD)

# Re-export public names
__all__ = [n for n in dir(_MOD) if not n.startswith("_")]
_g = globals()
for name in __all__:
    _g[name] = getattr(_MOD, name)

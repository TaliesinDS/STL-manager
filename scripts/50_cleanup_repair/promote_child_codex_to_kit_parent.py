#!/usr/bin/env python3
"""Promote child codex assignments to kit parent when unanimous.

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\promote_child_codex_to_kit_parent.py \
    --db-url sqlite:///./data/stl_manager_v1.db --ids 292 --apply

Behavior:
  - For each specified kit parent (or all parents if --ids omitted):
      * If parent.is_kit_container is True and parent.codex_unit_name is empty,
        gather children (Variant.parent_id == parent.id).
            * If all children with non-empty codex_unit_name agree on the same
                (codex_unit_name, game_system), set those on the parent.
            * If children with non-empty codex_faction unanimously agree, set
                parent.codex_faction to that value and adopt a simple faction_path if
                parent.faction_path is empty.
  - Dry-run by default; requires --apply to write.
"""
from __future__ import annotations

import argparse
from collections import Counter
from typing import Iterable, Optional

from pathlib import Path
import sys

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, DB_URL
from db.models import Variant


def _agreeing_pair(pairs: Iterable[tuple[Optional[str], Optional[str]]]) -> Optional[tuple[str, str]]:
    vals = [(a or None, b or None) for a, b in pairs]
    # consider only those with non-empty codex_unit_name
    vals = [(a, b) for a, b in vals if a]
    if not vals:
        return None
    c = Counter(vals)
    if len(c) == 1:
        (uname, sysname), _ = c.most_common(1)[0]
        return uname, (sysname or None)
    return None


def promote(ids: Optional[list[int]], apply: bool) -> int:
    changed = 0
    checked = 0
    with get_session() as session:
        if ids:
            parents = (
                session.query(Variant)
                .filter(Variant.id.in_(ids))
                .all()
            )
        else:
            parents = (
                session.query(Variant)
                .filter(Variant.is_kit_container == True)  # noqa: E712
                .all()
            )
        for p in parents:
            checked += 1
            if not getattr(p, "is_kit_container", False):
                continue
            # gather children
            kids = (
                session.query(Variant)
                .filter(Variant.parent_id == p.id)
                .all()
            )
            # First, attempt to promote unanimous codex_faction
            facs = [getattr(k, "codex_faction", None) for k in kids if getattr(k, "codex_faction", None)]
            if facs:
                fac_set = set(facs)
                if len(fac_set) == 1:
                    fac_val = next(iter(fac_set))
                    print(f"Parent {p.id} ← unanimous children codex_faction='{fac_val}'")
                    if apply:
                        if not getattr(p, "codex_faction", None):
                            p.codex_faction = fac_val
                        # If parent has no faction_path, adopt a minimal one
                        if not getattr(p, "faction_path", None):
                            p.faction_path = [fac_val]
                        session.add(p)
                        changed += 1

            # Then, attempt to promote unit name/system when unanimous among children and parent missing name
            if not getattr(p, "codex_unit_name", None):
                pairs = [(getattr(k, "codex_unit_name", None), getattr(k, "game_system", None)) for k in kids]
                agree = _agreeing_pair(pairs)
                if agree:
                    uname, sysname = agree
                    print(f"Parent {p.id} ← unanimous children codex='{uname}', system='{sysname}'")
                    if apply:
                        p.codex_unit_name = uname
                        if sysname and not getattr(p, "game_system", None):
                            p.game_system = sysname
                        session.add(p)
                        changed += 1
        if apply and changed:
            session.commit()
    print(f"Checked {checked} parents; updated {changed}.")
    return changed


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Promote child codex to kit parent when unanimous")
    ap.add_argument("--ids", nargs="*", type=int, help="Specific parent Variant IDs to process (default: all kit parents)")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    ap.add_argument("--db-url", help="Database URL; can also use STLMGR_DB_URL env var")
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ids = args.ids or None
    promote(ids, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

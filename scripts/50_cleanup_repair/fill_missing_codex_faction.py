#!/usr/bin/env python3
"""Fill codex_faction (and faction_path) for variants that have a matched unit.

Usage (PowerShell):
  .\\.venv\\Scripts\\python.exe .\\scripts\50_cleanup_repair\fill_missing_codex_faction.py \
    --db-url sqlite:///./data/stl_manager_v1.db --ids 292 293 294 --apply

Behavior:
  - For each specified variant (or all when --ids omitted): if
    `codex_unit_name` is set and `codex_faction` is empty, look up the `Unit`
    by (`system`,`name`). If the unit has a `faction` (or `faction_id`), set
    `variant.codex_faction` to the leaf faction key and populate
    `variant.faction_path` from the faction's full path if missing.
  - Dry-run by default; requires --apply to write.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from db.models import Faction, Unit, Variant
from db.session import get_session


def resolve_faction_path(session, fac: Faction) -> Optional[List[str]]:
    if fac is None:
        return None
    # Prefer precomputed full_path if present
    fp = getattr(fac, 'full_path', None) or None
    if fp:
        return list(fp)
    # Build by walking parent chain
    chain: List[str] = []
    cur = fac
    guard = 0
    while cur is not None and guard < 20:
        k = getattr(cur, 'key', None)
        if isinstance(k, str) and k:
            chain.append(k)
        pid = getattr(cur, 'parent_id', None)
        if not pid:
            break
        cur = session.get(Faction, pid)
        guard += 1
    if chain:
        return list(reversed(chain))
    return None


def fill(ids: Optional[list[int]], apply: bool) -> int:
    updated = 0
    checked = 0
    with get_session() as session:
        q = session.query(Variant)
        if ids:
            q = q.filter(Variant.id.in_(ids))
        rows = q.all()
        for v in rows:
            checked += 1
            name = getattr(v, 'codex_unit_name', None)
            sysname = getattr(v, 'game_system', None)
            if not name or not sysname:
                continue
            if getattr(v, 'codex_faction', None):
                continue
            # Find unit by (system, name)
            u = (
                session.query(Unit)
                .filter(Unit.name == name)
                .filter(Unit.system.has(key=sysname))
                .first()
            )
            if u is None:
                continue
            # Resolve faction leaf key
            leaf_key: Optional[str] = None
            fobj = getattr(u, 'faction', None)
            if fobj is None and getattr(u, 'faction_id', None):
                fobj = session.get(Faction, getattr(u, 'faction_id'))
            if fobj is not None:
                k = getattr(fobj, 'key', None)
                if isinstance(k, str) and k:
                    leaf_key = k
            if not leaf_key:
                continue
            print(f"Variant {v.id}: setting codex_faction='{leaf_key}' from Unit")
            if apply:
                v.codex_faction = leaf_key
                # Populate a simple faction_path if missing
                fp_existing = getattr(v, 'faction_path', None)
                if not fp_existing:
                    fp = resolve_faction_path(session, fobj)
                    if fp:
                        v.faction_path = fp
                session.add(v)
                updated += 1
        if apply and updated:
            session.commit()
    print(f"Checked {checked} variants; updated {updated}.")
    return updated


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fill codex_faction from matched Unit")
    ap.add_argument("--ids", nargs="*", type=int, help="Variant IDs (default: all)")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    ap.add_argument("--db-url", help="Database URL; can also use STLMGR_DB_URL")
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ids = args.ids or None
    fill(ids, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

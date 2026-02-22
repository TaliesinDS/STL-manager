#!/usr/bin/env python3
"""Fix Infernus Squad kit parent/children linkage in the DB.

- Default behavior assumes: outer=291, parent=292, children=[293, 294].
- Marks 292 as kit parent (is_kit_container=True), aggregates child types,
  re-parents 293/294 to 292, unmarks 291 as a kit parent.
- Safe by default (dry-run). Use --apply to commit.

Usage (PowerShell):
  .\\.venv\\Scripts\\python.exe .\\scripts\fix_infernus_kit.py \
    --db-url sqlite:///./data/stl_manager_v1.db --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict, dataclass

# ensure project root
from typing import List, Optional, Set

from db.models import Variant
from db.session import DB_URL, get_session

KIT_CHILD_TOKENS: Set[str] = {
    "body", "bodies", "torsos", "torso",
    "head", "heads", "helmet", "helmets",
    "arm", "arms", "left arm", "right arm",
    "hand", "hands",
    "weapon", "weapons", "ranged", "melee", "flamer", "flamers",
    "bits", "bitz", "accessories", "options",
    "shields", "backpacks", "shoulder pads", "pauldrons",
}


def _norm(s: str) -> str:
    import re as _re
    s = _re.sub(r"[\W_]+", " ", (s or "").lower()).strip()
    s = _re.sub(r"\s+", " ", s)
    return s


def _segment_under(parent_rel: str, child_rel: str) -> str:
    for sep in ("\\", "/"):
        pref = parent_rel + sep
        if child_rel.startswith(pref) and len(child_rel) > len(pref):
            rest = child_rel[len(pref):]
            return re.split(r"[\\/]+", rest)[0]
    return ""


def _classify(seg: str) -> Optional[str]:
    segn = _norm(seg)
    preferred = [
        "bodies", "body", "heads", "helmet", "helmets", "head",
        "weapons", "weapon", "arms", "arm", "shields", "backpacks",
        "shoulder pads", "pauldrons", "accessories", "options", "torsos", "torso",
    ]
    for tok in preferred:
        if re.search(rf"\b{re.escape(tok)}\b", segn):
            return tok
    if re.search(r"\bhand(s)?\b", segn):
        return "arms"
    if re.search(r"\bflamer(s)?\b", segn):
        return "weapons"
    return None


@dataclass
class Change:
    variant_id: int
    rel_path: str
    action: str
    details: dict


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fix Infernus Squad kit parent/children linkage")
    p.add_argument("--db-url", help="Override DB URL (else uses STLMGR_DB_URL or default)")
    p.add_argument("--outer-id", type=int, default=291, help="Outer folder Variant ID (will be unmarked)")
    p.add_argument("--parent-id", type=int, default=292, help="Inner folder Variant ID (will be marked as kit parent)")
    p.add_argument("--child-ids", type=int, nargs="*", default=[293, 294], help="Child Variant IDs to link to parent")
    p.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    # Rebind DB if provided
    if args.db_url:
        try:
            from sqlalchemy import create_engine as _ce
            from sqlalchemy.orm import Session as _S
            from sqlalchemy.orm import sessionmaker as _sm

            import db.session as _dbs
            try:
                _dbs.engine.dispose()
            except Exception:
                pass
            _dbs.DB_URL = args.db_url
            _dbs.engine = _ce(args.db_url, future=True)
            _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
        except Exception as e:
            print(f"Failed to reconfigure DB session for URL {args.db_url}: {e}", file=sys.stderr)
            return 2

    changes: List[Change] = []
    with get_session() as session:
        outer = session.query(Variant).get(args.outer_id)
        parent = session.query(Variant).get(args.parent_id)
        childs = [session.query(Variant).get(cid) for cid in args.child_ids]
        if not parent:
            print(f"Parent variant {args.parent_id} not found", file=sys.stderr)
            return 1

        # Unmark outer if present
        if outer and getattr(outer, "is_kit_container", False):
            changes.append(Change(outer.id, outer.rel_path or "", "unmark_parent", {}))
            if args.apply:
                outer.is_kit_container = False
                outer.kit_child_types = []

        # Ensure parent is marked
        if not getattr(parent, "is_kit_container", False):
            changes.append(Change(parent.id, parent.rel_path or "", "mark_parent", {}))
            if args.apply:
                parent.is_kit_container = True

        # Link children and collect part types
        types: Set[str] = set(getattr(parent, "kit_child_types", []) or [])
        for c in childs:
            if not c:
                continue
            if c.parent_id != parent.id:
                changes.append(Change(c.id, c.rel_path or "", "link_child", {"parent_id": parent.id}))
                if args.apply:
                    c.parent_id = parent.id
            seg = _segment_under(parent.rel_path.lower(), (c.rel_path or "").lower()) if parent.rel_path and c.rel_path else ""
            chosen = _classify(seg)
            if args.apply and chosen and getattr(c, "part_pack_type", None) != chosen:
                c.part_pack_type = chosen
            if chosen:
                types.add(chosen)

        # Save kit child types aggregate
        if args.apply:
            parent.kit_child_types = sorted(types)
            # If 292 was accidentally parented under 291, clear it
            if parent.parent_id and outer and parent.parent_id == outer.id:
                parent.parent_id = None
            session.commit()

    # Emit summary
    payload = {
        "db_url": DB_URL,
        "apply": bool(args.apply),
        "outer_id": args.outer_id,
        "parent_id": args.parent_id,
        "child_ids": args.child_ids,
        "changes": [asdict(c) for c in changes],
    }
    import json
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

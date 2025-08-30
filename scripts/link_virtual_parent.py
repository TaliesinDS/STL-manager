#!/usr/bin/env python3
"""Create/link a virtual kit parent and attach children by Variant IDs.

- Ensures a Variant exists for the provided parent rel_path; creates one if missing.
- Marks the parent as a kit container and aggregates child part types from folder segments.
- Links provided child Variant IDs to the parent via parent_id.
- Optionally assigns a shared model_group_id to parent and children.

Safe by default: dry-run. Use --apply to write changes. Prints a concise JSON summary.

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\link_virtual_parent.py \
    --db-url sqlite:///./data/stl_manager_v1.db \
    --parent-rel "sample_store\\Terminator Squad\\Termi 3d models_V1_3\\Termi 3d Models Complete Library" \
    --child-ids 424 425 426 427 428 429 430 431 432 433 434 435 436 437 438 439 440 441 442 443 444 445 446 447 448 449 450 451 452 453 454 455 456 457 458 459 460 461 462 463 464 465 \
    --group --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

# Project import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, DB_URL
from db.models import Variant


def _norm(s: str) -> str:
    s = re.sub(r"[\W_]+", " ", (s or "").lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


PREFERRED_TOKENS = [
    "bodies", "body", "heads", "helmet", "helmets", "head",
    "weapons", "weapon", "arms", "arm", "shields", "backpacks",
    "shoulder pads", "pauldrons", "accessories", "options", "torsos", "torso",
]


def _classify_segment(seg: str) -> Optional[str]:
    segn = _norm(seg)
    for tok in PREFERRED_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", segn):
            return tok
    # Helpful fallbacks
    if re.search(r"\bhand(s)?\b", segn):
        return "arms"
    if re.search(r"\bflamer(s)?\b", segn):
        return "weapons"
    if re.search(r"\bshoulder(s)?\b", segn):
        return "shoulder pads"
    return None


def _child_segments_under(parent_rel: str, child_rel: str) -> Tuple[str, Optional[str]]:
    """Return (first_seg, second_seg) lowercased raw child segments under parent_rel for child_rel."""
    for sep in ("\\", "/"):
        pref = parent_rel + sep
        if child_rel.startswith(pref) and len(child_rel) > len(pref):
            rest = child_rel[len(pref):]
            parts = re.split(r"[\\/]+", rest)
            if len(parts) >= 2:
                return (parts[0], parts[1])
            if len(parts) == 1:
                return (parts[0], None)
    return ("", None)


@dataclass
class Change:
    variant_id: int
    rel_path: str
    action: str
    details: dict


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Create/link a virtual kit parent and attach children by Variant IDs")
    ap.add_argument("--db-url", help="Override DB URL (else uses STLMGR_DB_URL or default)")
    ap.add_argument("--parent-rel", required=True, help="Rel path of the kit parent folder (Variant will be created if missing)")
    ap.add_argument("--child-ids", type=int, nargs="+", help="Variant IDs to link under the parent")
    ap.add_argument("--group", action="store_true", help="Assign a shared model_group_id to parent and children")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    args = ap.parse_args(argv)

    # Rebind DB if provided
    if args.db_url:
        try:
            from sqlalchemy import create_engine as _ce
            from sqlalchemy.orm import sessionmaker as _sm, Session as _S
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
    created_parent = False
    parent_id: Optional[int] = None
    parent_rel = args.parent_rel
    parent_rel_lower = parent_rel.replace("/", "\\").lower()

    with get_session() as session:
        # Find or create the parent Variant by rel_path (case-insensitive match on normalized slashes)
        parent: Optional[Variant] = None
        candidates = session.query(Variant).all()
        for v in candidates:
            rl = (v.rel_path or "").replace("/", "\\").lower()
            if rl == parent_rel_lower:
                parent = v
                break
        if not parent:
            parent = Variant(
                rel_path=parent_rel,
                filename=None,
                extension=None,
                is_archive=False,
                is_dir=True,
                is_kit_container=True,
                kit_child_types=[],
                part_pack_type="squad_kit",
                segmentation="multi-part",
            )
            changes.append(Change(-1, parent_rel, "create_parent", {}))
            if args.apply:
                session.add(parent)
                session.flush()
                changes[-1].variant_id = parent.id
            created_parent = True
        else:
            # Ensure parent is marked as kit container
            if not getattr(parent, "is_kit_container", False):
                changes.append(Change(parent.id, parent.rel_path or parent_rel, "mark_parent", {}))
                if args.apply:
                    parent.is_kit_container = True

        parent_id = parent.id if parent and getattr(parent, "id", None) else None

        # Group ID if requested
        gid: Optional[str] = None
        if args.group:
            gid = parent.model_group_id or ("kit:" + hashlib.md5((parent.rel_path or parent_rel).encode("utf-8")).hexdigest()[:12])
            if parent.model_group_id != gid:
                changes.append(Change(parent.id if parent_id else -1, parent.rel_path or parent_rel, "set_group_id", {"model_group_id": gid}))
                if args.apply:
                    parent.model_group_id = gid

        # Link children and classify part types
        agg_types: Set[str] = set(getattr(parent, "kit_child_types", []) or [])
        for cid in (args.child_ids or []):
            c = session.query(Variant).get(cid)
            if not c:
                continue
            # Link
            if not parent_id or (c.parent_id != parent_id):
                changes.append(Change(c.id, c.rel_path or "", "link_child", {"parent_rel": parent_rel, "parent_id": parent_id}))
                if args.apply and parent_id:
                    c.parent_id = parent_id
            # Classify by immediate (or second-level) segment
            first, second = _child_segments_under(parent.rel_path.replace("/", "\\"), (c.rel_path or "").replace("/", "\\")) if parent.rel_path and c.rel_path else ("", None)
            chosen = _classify_segment(first)
            if not chosen and second:
                chosen = _classify_segment(second)
            if args.apply and chosen and getattr(c, "part_pack_type", None) != chosen:
                c.part_pack_type = chosen
            if chosen:
                agg_types.add(chosen)
            # Grouping for child
            if gid and (c.model_group_id != gid):
                changes.append(Change(c.id, c.rel_path or "", "set_group_id", {"model_group_id": gid}))
                if args.apply:
                    c.model_group_id = gid

        # Save kit child types aggregate on parent
        if args.apply:
            parent.kit_child_types = sorted(agg_types)
            session.commit()

    # Emit summary
    payload = {
        "db_url": DB_URL,
        "apply": bool(args.apply),
        "parent_rel": parent_rel,
        "created_parent": created_parent,
        "changes": [asdict(c) for c in changes],
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

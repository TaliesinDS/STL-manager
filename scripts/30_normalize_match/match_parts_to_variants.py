#!/usr/bin/env python3
"""Match kit children to Parts and create VariantPartLink associations.

Scope:
- Operates on kit parents (by --parent-rel, --parent-id, or --all-kits).
- For each child Variant under a kit parent, determine a classification
  (uses Variant.part_pack_type if present or infers from path), then:
  - Link to an existing Part that matches the classification and context, or
  - Optionally create a generic Part for this kit parent + classification.

Safety:
- Dry-run by default; use --apply to persist changes.
- PowerShell-friendly and accepts --db-url to target the correct DB.

Examples (PowerShell):
  # Dry-run on one kit by rel path
  .\\.venv\\Scripts\\python.exe .\\scripts\\match_parts_to_variants.py \
    --db-url sqlite:///./data/stl_manager_v1.db \
    --parent-rel 'sample_store\\Terminator Squad\\Termi 3d models_V1_3\\Termi 3d Models Complete Library'

  # Apply and auto-create generic Parts under Warhammer 40,000 system
  .\\.venv\\Scripts\\python.exe .\\scripts\\match_parts_to_variants.py \
    --db-url sqlite:///./data/stl_manager_v1.db \
    --parent-rel 'sample_store\\Terminator Squad\\Termi 3d models_V1_3\\Termi 3d Models Complete Library' \
    --create-missing-parts --system-key w40k --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Project root import
PROJECT_ROOT = Path(__file__).resolve().parents[2]

from db.models import Faction, GameSystem, Part, Variant, VariantPartLink
from db.session import DB_URL, get_session


def _norm(s: str) -> str:
    s = re.sub(r"[\W_]+", " ", (s or "").lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


CLASS_TO_PART: Dict[str, Dict[str, object]] = {
    # classification -> defaults: part_type, slot or slots, category
    "arms": {"part_type": "body", "slots": ["left_arm", "right_arm"]},
    "arm": {"part_type": "body", "slots": ["left_arm", "right_arm"]},
    "heads": {"part_type": "body", "slot": "head"},
    "head": {"part_type": "body", "slot": "head"},
    "helmet": {"part_type": "body", "slot": "head"},
    "helmets": {"part_type": "body", "slot": "head"},
    "torsos": {"part_type": "body", "slot": "torso"},
    "torso": {"part_type": "body", "slot": "torso"},
    "legs": {"part_type": "body", "slot": "legs"},
    "shoulder pads": {"part_type": "body", "slot": "shoulder_pad"},
    "weapons": {"part_type": "wargear", "category": "weapon"},
    "weapon": {"part_type": "wargear", "category": "weapon"},
    "bases": {"part_type": "decor", "category": "base"},
    "shields": {"part_type": "wargear", "category": "shield"},
    "backpacks": {"part_type": "body", "slot": "backpack"},
    "accessories": {"part_type": "decor", "category": "accessory"},
    "options": {"part_type": "decor", "category": "option"},
}


PREFERRED_TOKENS: List[str] = [
    "bodies", "body", "heads", "helmet", "helmets", "head",
    "weapons", "weapon", "arms", "arm", "shields", "backpacks",
    "shoulder pads", "pauldrons", "accessories", "options", "torsos", "torso",
    "shoulders", "legs", "bases", "base",
]


def _classify_from_seg(seg: str) -> Optional[str]:
    segn = _norm(seg)
    for tok in PREFERRED_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", segn):
            if tok == "shoulders":
                return "shoulder pads"
            if tok in ("base", "bases"):
                return "bases"
            return tok
    if re.search(r"\bhand(s)?\b", segn):
        return "arms"
    if re.search(r"\bflamer(s)?\b", segn):
        return "weapons"
    return None


def _child_first_second(parent_rel: str, child_rel: str) -> Tuple[str, Optional[str]]:
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


def _ensure_system_and_faction(session, system_key: Optional[str], faction_key: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    sys_id: Optional[int] = None
    fac_id: Optional[int] = None
    if system_key:
        gs = session.query(GameSystem).filter(GameSystem.key == system_key).first()
        if gs:
            sys_id = gs.id
    if faction_key:
        fac = session.query(Faction).filter(Faction.key == faction_key).first()
        if fac:
            fac_id = fac.id
    return sys_id, fac_id


def _find_part_for_class(session, parent: Variant, classification: str) -> Optional[Part]:
    # Try exact name match by a conventional name (parent basename + class)
    parent_base = (parent.rel_path or "").split("\\")[-1].split("/")[-1]
    name_cand = f"{parent_base} {classification}"
    p = session.query(Part).filter(Part.name == name_cand).first()
    if p:
        return p
    # Fallback: look for generic parts by category/slot/part_type
    meta = CLASS_TO_PART.get(classification) or {}
    q = session.query(Part)
    if meta.get("part_type"):
        q = q.filter(Part.part_type == meta["part_type"])  # type: ignore[index]
    # We can't filter by slots JSON easily; use category if available
    if meta.get("category"):
        q = q.filter(Part.category == meta["category"])  # type: ignore[index]
    p = q.first()
    return p


def _create_generic_part(session, system_id: Optional[int], faction_id: Optional[int], parent: Variant, classification: str) -> Optional[Part]:
    meta = CLASS_TO_PART.get(classification) or {}
    if not meta:
        return None
    # Require system_id due to NOT NULL constraint
    if not system_id:
        return None
    parent_base = (parent.rel_path or "").split("\\")[-1].split("/")[-1]
    key = _norm(f"{parent_base} {classification}").replace(" ", "_")
    name = f"{parent_base} {classification}"
    p = Part(
        system_id=system_id,
        faction_id=faction_id,
        key=key,
        name=name,
        part_type=str(meta.get("part_type") or "decor"),
        category=str(meta.get("category")) if meta.get("category") else None,
        slot=str(meta.get("slot")) if meta.get("slot") else None,
        slots=list(meta.get("slots") or []),
        aliases=[],
        available_to=[],
        attributes={},
        raw_data={},
    )
    session.add(p)
    session.flush()
    return p


@dataclass
class Change:
    action: str
    details: dict


def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Match kit children to Parts and create VariantPartLink associations")
    ap.add_argument("--db-url", help="Override DB URL (else uses STLMGR_DB_URL or default)")
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--parent-id", type=int, help="Single kit parent Variant ID to process")
    scope.add_argument("--parent-rel", help="Single kit parent rel_path to process (case-insensitive)")
    scope.add_argument("--all-kits", action="store_true", help="Process all variants marked is_kit_container=True")
    ap.add_argument("--create-missing-parts", action="store_true", help="Create a generic Part per (kit parent, classification) when no matching Part exists")
    ap.add_argument("--system-key", help="System key (e.g., w40k) required when creating missing parts")
    ap.add_argument("--faction-key", help="Optional faction key (e.g., adeptus_astartes) when creating missing parts")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    ap.add_argument("--out", help="Write JSON report to this path (default: reports/match_parts_YYYYMMDD_HHMMSS.json)")
    return ap.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    # Rebind DB for reliability on Windows
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

    report: Dict[str, object] = {
        "db_url": DB_URL,
        "apply": bool(args.apply),
        "create_missing_parts": bool(args.create_missing_parts),
        "system_key": args.system_key,
        "faction_key": args.faction_key,
        "changes": [],
        "counts": {"linked": 0, "created_parts": 0, "skipped_children": 0},
    }
    changes: List[Change] = []

    with get_session() as session:
        parents: List[Variant] = []
        if args.parent_id:
            v = session.query(Variant).get(args.parent_id)
            if v:
                parents = [v]
        elif args.parent_rel:
            target = (args.parent_rel or "").replace("/", "\\").lower()
            for v in session.query(Variant).all():
                rl = (v.rel_path or "").replace("/", "\\").lower()
                if rl == target:
                    parents = [v]
                    break
        elif args.all_kits:
            parents = session.query(Variant).filter(Variant.is_kit_container == True).all()  # noqa: E712

        sys_id: Optional[int] = None
        fac_id: Optional[int] = None
        if args.create_missing_parts:
            sys_id, fac_id = _ensure_system_and_faction(session, args.system_key, args.faction_key)

        for parent in parents:
            if not parent:
                continue
            # Direct children only
            for child in getattr(parent, "children", []) or []:
                # Classification from Variant or path
                cls = getattr(child, "part_pack_type", None)
                if not cls:
                    first, second = _child_first_second((parent.rel_path or "").replace("/", "\\"), (child.rel_path or "").replace("/", "\\"))
                    cls = _classify_from_seg(first) or (second and _classify_from_seg(second)) or None
                if not cls:
                    report["counts"]["skipped_children"] += 1  # type: ignore[index]
                    continue
                # Find or create a Part
                part = _find_part_for_class(session, parent, cls)
                created = False
                if not part and args.create_missing_parts:
                    part = _create_generic_part(session, sys_id, fac_id, parent, cls)
                    if part:
                        created = True
                        report["counts"]["created_parts"] = report["counts"].get("created_parts", 0) + 1  # type: ignore[index]

                if not part:
                    report["counts"]["skipped_children"] = report["counts"].get("skipped_children", 0) + 1  # type: ignore[index]
                    continue

                # Link variant to part if not already linked
                existing = (
                    session.query(VariantPartLink)
                    .filter(VariantPartLink.variant_id == child.id, VariantPartLink.part_id == part.id)
                    .first()
                )
                if not existing:
                    changes.append(Change("variant_part_link", {"variant_id": child.id, "part_id": part.id, "classification": cls, "part_name": part.name}))
                    if args.apply:
                        vpl = VariantPartLink(variant_id=child.id, part_id=part.id, is_primary=False, match_method="kit_classification", match_confidence=0.6)
                        session.add(vpl)
                        report["counts"]["linked"] = report["counts"].get("linked", 0) + 1  # type: ignore[index]
                # If we just created a Part, record it
                if created:
                    changes.append(Change("create_part", {"part_id": part.id, "name": part.name, "key": part.key, "classification": cls}))

        if args.apply:
            session.commit()

    report["changes"] = [asdict(c) for c in changes]
    # Output
    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = PROJECT_ROOT / "reports" / f"match_parts_report_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Part matcher report written: {out_path}")
    print(json.dumps({"counts": report["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

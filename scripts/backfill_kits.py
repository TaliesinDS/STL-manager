#!/usr/bin/env python3
"""Backfill kit container relationships in the Variant table.

- Detect parent folders that act as modular "kit" containers (children like bodies/heads/weapons)
- If a real parent Variant exists and looks like a kit container, mark it and aggregate child types.
- If only virtual parents exist (no Variant row for the parent folder), optionally create them.
- Link children to their kit parent via parent_id. Optionally assign a shared model_group_id.

Safe by default: dry-run. Use --apply to write changes. Always prints a JSON summary report.

Usage (PowerShell):
    .\.venv\Scripts\python.exe .\scripts\backfill_kits.py --db-url sqlite:///./data/stl_manager_v1.db --create-virtual-parents --group-children --out .\reports\backfill_kits.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Ensure project root importability
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, DB_URL
from db.models import Variant

KIT_CHILD_TOKENS: Set[str] = {
    "body", "bodies", "torsos", "torso",
    "head", "heads", "helmet", "helmets",
    "arm", "arms", "left arm", "right arm",
    # Also recognize hands as an arm synonym
    "hand", "hands",
    # Common weapon synonyms that appear in folder names
    "weapon", "weapons", "ranged", "melee", "flamer", "flamers",
    "bits", "bitz", "accessories", "options",
    "shields", "backpacks", "shoulder pads", "pauldrons",
    # Additional real-world labels we've seen
    "shoulders", "legs", "bases", "base",
}

# Parent folder name hints that strongly imply a modular kit container
KIT_PARENT_HINTS: Set[str] = {
    "complete library", "full kit", "all parts", "modular", "complete set",
    "upgrade set", "bits library", "bitz library", "kit", "complete pack", "full pack",
}

NOISE_FILENAMES = {".ds_store", "thumbs.db", "desktop.ini"}


def _norm(s: str) -> str:
    s = re.sub(r"[\W_]+", " ", (s or "").lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _is_noise_filename(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    if n in NOISE_FILENAMES:
        return True
    if n.startswith("._") and n[2:] in NOISE_FILENAMES:
        return True
    return False


def _has_meaningful_files(v: Variant) -> bool:
    try:
        files = getattr(v, "files", []) or []
        MEANINGFUL_EXTS = {"stl", "obj", "ztl", "lys", "lychee", "3mf", "step", "stp"}
        ARCHIVE_EXTS = {"zip", "rar", "7z"}
        for f in files:
            if getattr(f, "is_dir", False):
                continue
            name = (getattr(f, "filename", "") or "").strip().lower()
            if not name or _is_noise_filename(name):
                continue
            ext = (getattr(f, "extension", "") or "").strip().lower()
            if getattr(f, "is_archive", False) or ext in MEANINGFUL_EXTS or ext in ARCHIVE_EXTS:
                return True
    except Exception:
        return False
    return False


def _parent_of(rel_lower: str) -> str:
    if not rel_lower:
        return ""
    i1 = rel_lower.rfind("\\")
    i2 = rel_lower.rfind("/")
    idx = max(i1, i2)
    if idx <= 0:
        return ""
    return rel_lower[:idx]


def _immediate_child_segments(parent_rel_lower: str, all_rel_lowers: List[str]) -> Set[str]:
    segs: Set[str] = set()
    if not parent_rel_lower:
        return segs
    for sep in ("\\", "/"):
        prefix = parent_rel_lower + sep
        plen = len(prefix)
        for rp in all_rel_lowers:
            if rp and rp != parent_rel_lower and rp.startswith(prefix):
                rest = rp[plen:]
                nxt = re.split(r"[\\/]+", rest)[0]
                n = _norm(nxt)
                if n:
                    segs.add(n)
    return segs


def _immediate_child_segments_raw(parent_rel_lower: str, all_rel_lowers: List[str]) -> List[str]:
    """Return the raw (lowercased) immediate child segment names for a given parent.
    Unlike _immediate_child_segments, this preserves original spacing (lowercased) for reconstruction.
    """
    segs: List[str] = []
    if not parent_rel_lower:
        return segs
    for sep in ("\\", "/"):
        prefix = parent_rel_lower + sep
        plen = len(prefix)
        for rp in all_rel_lowers:
            if rp and rp != parent_rel_lower and rp.startswith(prefix):
                rest = rp[plen:]
                nxt = re.split(r"[\\/]+", rest)[0]
                n = (nxt or "").strip().lower()
                if n and n not in segs:
                    segs.append(n)
    return segs


def _is_kit_container(parent_rel_lower: str, all_rel_lowers: List[str]) -> Tuple[bool, List[str]]:
    """Determine if a parent folder is a kit container by scanning immediate child
    segment names and matching any known kit child tokens as word-boundary substrings
    within those segment names. Handles composite names like "Weapons, Arms, Accessories".
    """
    child_segs = _immediate_child_segments(parent_rel_lower, all_rel_lowers)
    matched_set: Set[str] = set()
    # Map common synonyms to canonical tokens
    def _add_match(token: str, seg: str) -> None:
        # unify synonyms
        if token == "shoulders":
            matched_set.add("shoulder pads")
        elif token in ("base", "bases"):
            matched_set.add("bases")
        else:
            matched_set.add(token)

    for seg in child_segs:
        for tok in KIT_CHILD_TOKENS:
            # word-boundary substring match to support multi-word tokens like 'shoulder pads'
            if re.search(rf"\b{re.escape(tok)}\b", seg):
                _add_match(tok, seg)
    matched = sorted(matched_set)
    child_count = len(child_segs)
    # Primary rule: at least two distinct kit child categories
    if len(matched) >= 2:
        return (True, matched)

    # Secondary rule: parent name hints + enough children
    parent_base = re.split(r"[\\/]+", parent_rel_lower)[-1]
    parent_base_norm = _norm(parent_base)
    if any(h in parent_base_norm for h in KIT_PARENT_HINTS) and child_count >= 3:
        # If no direct matches, still consider as a kit using whatever weak matches we have
        return (True, matched)

    # Fallback: handle double-named folder patterns where an immediate child name
    # matches the parent basename (e.g., ".../Infernus Squad/Infernus Squad/...").
    # Evaluate the inner folder's grandchildren for kit tokens and prefer it as
    # the true kit parent if it qualifies, even if siblings also exist alongside it.
    parent_base = re.split(r"[\\/]+", parent_rel_lower)[-1]
    parent_base_norm = _norm(parent_base)
    raw_children = _immediate_child_segments_raw(parent_rel_lower, all_rel_lowers)
    for child_raw in raw_children:
        if _norm(child_raw) == parent_base_norm:
            inner_parent = parent_rel_lower + "\\" + child_raw
            inner_child_segs = _immediate_child_segments(inner_parent, all_rel_lowers)
            inner_matched: Set[str] = set()
            for seg in inner_child_segs:
                for tok in KIT_CHILD_TOKENS:
                    if re.search(rf"\b{re.escape(tok)}\b", seg):
                        if tok == "shoulders":
                            inner_matched.add("shoulder pads")
                        elif tok in ("base", "bases"):
                            inner_matched.add("bases")
                        else:
                            inner_matched.add(tok)
            inner_matched_sorted = sorted(inner_matched)
            if len(inner_matched_sorted) >= 2:
                return (True, inner_matched_sorted)

    return (False, matched)


@dataclass
class Change:
    variant_id: int
    rel_path: str
    action: str
    details: dict


def backfill(create_virtual_parents: bool, group_children: bool, apply: bool, out: Optional[Path]) -> int:
    report: dict = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "db_url": DB_URL,
        "apply": bool(apply),
        "create_virtual_parents": bool(create_virtual_parents),
        "group_children": bool(group_children),
        "changes": [],
        "counts": {
            "marked_kit_parents": 0,
            "created_virtual_parents": 0,
            "linked_children": 0,
            "grouped_children": 0,
        },
    }

    with get_session() as session:
        variants = session.query(Variant).all()
        rel_lower_index: Dict[str, Variant] = {}
        all_rel_lowers: List[str] = []
        for v in variants:
            rl = (v.rel_path or "").strip().lower()
            if rl:
                rel_lower_index[rl] = v
                all_rel_lowers.append(rl)

        # Discover real and virtual kit parents
        real_kits: Dict[str, List[str]] = {}
        virtual_kits: Dict[str, List[str]] = {}

        for rl, _v in rel_lower_index.items():
            # has children?
            if any(rp.startswith(rl + sep) for sep in ("\\", "/") for rp in all_rel_lowers if rp != rl):
                # Prefer inner double-named folder as the true kit parent
                parent_base = rl.split("\\")[-1].split("/")[-1]
                parent_base_norm = _norm(parent_base)
                raw_children = _immediate_child_segments_raw(rl, all_rel_lowers)
                handled = False
                # Prefer any inner child that matches the parent's basename and qualifies as a kit
                for child_raw in raw_children:
                    if _norm(child_raw) == parent_base_norm:
                        inner = rl + "\\" + child_raw
                        is_kit_inner, types_inner = _is_kit_container(inner, all_rel_lowers)
                        if is_kit_inner:
                            if inner in rel_lower_index:
                                real_kits[inner] = types_inner
                            else:
                                virtual_kits[inner] = types_inner
                            handled = True
                            break
                        # If inner didn't hit threshold but the outer does, still promote the inner and carry outer types
                        is_kit_outer, types_outer = _is_kit_container(rl, all_rel_lowers)
                        if is_kit_outer:
                            if inner in rel_lower_index:
                                real_kits[inner] = types_outer
                            else:
                                virtual_kits[inner] = types_outer
                            handled = True
                            break
                if handled:
                    continue
                # Regular detection on this folder
                is_kit, types = _is_kit_container(rl, all_rel_lowers)
                if is_kit:
                    real_kits[rl] = types

        # Virtual: parents with children matching kit tokens but no Variant row
        parent_children: Dict[str, List[Variant]] = {}
        for rl, _v in rel_lower_index.items():
            parent = _parent_of(rl)
            if not parent:
                continue
            parent_children.setdefault(parent, []).append(_v)
        for parent, _childs in parent_children.items():
            if parent in rel_lower_index:
                continue  # real parent exists; handled above
            segs = _immediate_child_segments(parent, all_rel_lowers)
            # Regex word-boundary match against child segments to catch composite labels like 'hands and flamers'
            matched_set: Set[str] = set()
            for seg in segs:
                for tok in KIT_CHILD_TOKENS:
                    if re.search(rf"\b{re.escape(tok)}\b", seg):
                        if tok == "shoulders":
                            matched_set.add("shoulder pads")
                        elif tok in ("base", "bases"):
                            matched_set.add("bases")
                        else:
                            matched_set.add(tok)
            matched = sorted(matched_set)
            parent_base = parent.split("\\")[-1].split("/")[-1]
            parent_base_norm = _norm(parent_base)
            has_hint = any(h in _norm(parent_base) for h in KIT_PARENT_HINTS)
            # Primary: 2+ matches; Secondary: hint + at least 3 children
            if len(matched) >= 2 or (has_hint and len(segs) >= 3):
                virtual_kits[parent] = matched

        changes: List[Change] = []

        # If an outer parent was previously marked as a kit but we selected the inner as the true parent,
        # unmark the outer to avoid double-parenting.
        selected_parents = set(real_kits.keys()) | set(virtual_kits.keys())
        for rl, v in rel_lower_index.items():
            if getattr(v, "is_kit_container", False) and rl not in selected_parents:
                parent_base = rl.split("\\")[-1].split("/")[-1]
                raw_children = _immediate_child_segments_raw(rl, all_rel_lowers)
                # If any immediate child name matches the parent basename, and this rl wasn't selected,
                # it likely means the inner child was promoted; unmark the outer.
                if any(_norm(rc) == _norm(parent_base) for rc in raw_children):
                    changes.append(Change(v.id, v.rel_path or rl, "unmark_parent", {}))
                    if apply:
                        v.is_kit_container = False
                        v.kit_child_types = []

        # Mark real kit parents
        for parent_rl, types in real_kits.items():
            pv = rel_lower_index.get(parent_rl)
            if not pv:
                continue
            if not pv.is_kit_container or (pv.kit_child_types or []) != types:
                changes.append(Change(pv.id, pv.rel_path or parent_rl, "mark_parent", {"kit_child_types": types}))
                if apply:
                    pv.is_kit_container = True
                    pv.kit_child_types = types
                report["counts"]["marked_kit_parents"] += 1

        # Create virtual parents if requested
        created_parent_for: Dict[str, Variant] = {}
        if create_virtual_parents:
            for parent_rl, types in virtual_kits.items():
                v = Variant(
                    rel_path=parent_rl,
                    filename=None,
                    extension=None,
                    is_archive=False,
                    is_dir=True,
                    is_kit_container=True,
                    kit_child_types=types,
                    part_pack_type="squad_kit",
                    segmentation="multi-part",
                )
                changes.append(Change(-1, parent_rl, "create_parent", {"kit_child_types": types}))
                if apply:
                    session.add(v)
                    session.flush()
                    created_parent_for[parent_rl] = v
                    changes[-1].variant_id = v.id
                report["counts"]["created_virtual_parents"] += 1

        # Link children to parents and optionally group
        def _get_parent_variant(parent_rl: str) -> Optional[Variant]:
            if parent_rl in rel_lower_index:
                return rel_lower_index[parent_rl]
            return created_parent_for.get(parent_rl)

        grouped = 0
        linked = 0
        for rl, v in rel_lower_index.items():
            # Check real/virtual kit parent
            parent_rl: Optional[str] = None
            for p in list(real_kits.keys()) + list(virtual_kits.keys()):
                for sep in ("\\", "/"):
                    pref = p + sep
                    if rl != p and rl.startswith(pref):
                        parent_rl = p
                        break
                if parent_rl:
                    break
            if not parent_rl:
                continue
            pv = _get_parent_variant(parent_rl)
            if not pv:
                continue
            # Link
            if v.parent_id != pv.id:
                changes.append(Change(v.id, v.rel_path or rl, "link_child", {"parent_id": pv.id, "parent_rel": pv.rel_path}))
                if apply:
                    v.parent_id = pv.id
                linked += 1
            # Tag child part type based on its immediate segment under the parent
            child_seg = ""
            for sep in ("\\", "/"):
                pref = parent_rl + sep
                if rl.startswith(pref) and len(rl) > len(pref):
                    rest = rl[len(pref):]
                    parts = re.split(r"[\\/]+", rest)
                    parent_base = re.split(r"[\\/]+", parent_rl)[-1]
                    parent_base_norm = _norm(parent_base)
                    cand = parts[0] if parts else ""
                    if _norm(cand) == parent_base_norm and len(parts) >= 2:
                        cand = parts[1]
                    child_seg = cand
                    break
            seg_norm = _norm(child_seg)
            PREFERRED = [
                "bodies", "body", "heads", "helmet", "helmets", "head",
                "weapons", "weapon", "arms", "arm", "shields", "backpacks",
                "shoulder pads", "pauldrons", "accessories", "options", "torsos", "torso",
                "shoulders", "legs", "bases", "base"
            ]
            chosen: Optional[str] = None
            for tok in PREFERRED:
                if re.search(rf"\b{re.escape(tok)}\b", seg_norm):
                    # normalize synonyms
                    if tok == "shoulders":
                        chosen = "shoulder pads"
                    elif tok in ("base", "bases"):
                        chosen = "bases"
                    else:
                        chosen = tok
                    break
            if not chosen:
                if re.search(r"\bhand(s)?\b", seg_norm):
                    chosen = "arms"
                elif re.search(r"\bflamer(s)?\b", seg_norm):
                    chosen = "weapons"
                elif re.search(r"\bshoulder(s)?\b", seg_norm):
                    chosen = "shoulder pads"
            if apply and chosen:
                try:
                    v.part_pack_type = chosen
                except Exception:
                    pass
            # Group
            if group_children:
                gid = pv.model_group_id or ("kit:" + hashlib.md5((pv.rel_path or parent_rl).encode("utf-8")).hexdigest()[:12])
                if pv.model_group_id != gid:
                    changes.append(Change(pv.id, pv.rel_path or parent_rl, "set_group_id", {"model_group_id": gid}))
                    if apply:
                        pv.model_group_id = gid
                if v.model_group_id != gid:
                    changes.append(Change(v.id, v.rel_path or rl, "set_group_id", {"model_group_id": gid}))
                    if apply:
                        v.model_group_id = gid
                    grouped += 1

        report["counts"]["linked_children"] = linked
        report["counts"]["grouped_children"] = grouped

        if apply:
            session.commit()

    # Emit report
    payload = {
        **report,
        "changes": [asdict(c) for c in changes],
    }
    out_path = out or (PROJECT_ROOT / "reports" / f"backfill_kits_{datetime.now().strftime('%Y%m%d_%H%M%S')}{'_apply' if apply else ''}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Backfill report written: {out_path}")
    print(f"Counts: marked_parents={report['counts']['marked_kit_parents']}, created_virtual={report['counts']['created_virtual_parents']}, linked_children={report['counts']['linked_children']}, grouped_children={report['counts']['grouped_children']}")
    return 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Backfill kit container relationships in Variant table")
    ap.add_argument("--db-url", help="Override database URL (defaults to STLMGR_DB_URL env var or sqlite:///./data/stl_manager.db)")
    ap.add_argument("--create-virtual-parents", action="store_true", help="Create a Variant row for kit parent folders that do not yet exist")
    ap.add_argument("--group-children", action="store_true", help="Assign a shared model_group_id to kit parent and all children")
    ap.add_argument("--apply", action="store_true", help="Write changes to DB (default: dry-run)")
    ap.add_argument("--out", help="Write JSON report to this path (default: reports/backfill_kits_YYYYMMDD_HHMMSS.json)")
    return ap.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    # Reconfigure DB session if a URL override is provided to avoid env var quoting issues on Windows
    if args.db_url:
        try:
            from sqlalchemy import create_engine as _ce
            from sqlalchemy.orm import sessionmaker as _sm, Session as _S
            import db.session as _dbs
            # Dispose existing engine and rebind
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
    out = Path(args.out) if args.out else None
    return backfill(create_virtual_parents=args.create_virtual_parents, group_children=args.group_children, apply=args.apply, out=out)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

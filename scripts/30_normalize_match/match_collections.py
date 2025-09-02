#!/usr/bin/env python3
"""
Canonical location for the Collections matcher.

Note: This file was moved from scripts/match_collections.py to maintain
consistency with other matchers under scripts/30_normalize_match/.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Variant  # type: ignore
import db.session as _dbs  # type: ignore


@dataclass
class CollRule:
    coll_id: str
    name: str
    cycle: Optional[str]
    theme: Optional[str]
    aliases: List[str]
    path_patterns: List[str]
    seq_regex: List[str]


def reconfigure_db(db_url: Optional[str]) -> None:
    if not db_url:
        return
    try:
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm, Session as _S
        try:
            _dbs.engine.dispose()
        except Exception:
            pass
        _dbs.DB_URL = db_url
        _dbs.engine = _ce(db_url, future=True)
        _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
    except Exception as e:
        print(f"Failed to reconfigure DB session for URL {db_url}: {e}", file=sys.stderr)
        raise


def load_rules_for_designer(designer_key: str) -> List[CollRule]:
    path = ROOT / "vocab" / "collections" / f"{designer_key}.yaml"
    if not path.exists():
        return []
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    rules: List[CollRule] = []
    for node in (data.get("collections") or []):
        if not isinstance(node, dict):
            continue
        coll_id = str(node.get("id") or "").strip()
        name = str(node.get("name") or "").strip()
        if not coll_id or not name:
            continue
        cycle = (node.get("cycle") or None)
        theme = (node.get("theme") or None)
        aliases = [str(a) for a in (node.get("aliases") or []) if isinstance(a, str) and a.strip()]
        match = node.get("match") or {}
        path_patterns = [str(p) for p in (match.get("path_patterns") or []) if isinstance(p, str) and p.strip()]
        seq_regex = [str(r) for r in (match.get("sequence_number_regex") or []) if isinstance(r, str) and r.strip()]
        rules.append(CollRule(coll_id, name, cycle, theme, aliases, path_patterns, seq_regex))
    return rules


def first_match(patterns: List[str], text: str) -> Optional[Tuple[str, re.Match]]:
    for pat in patterns:
        try:
            m = re.search(pat, text, flags=0)  # allow inline (?i)
        except re.error:
            # ignore bad patterns silently
            continue
        if m:
            return pat, m
    return None


def contains_alias(aliases: List[str], text_lower: str) -> Optional[str]:
    for a in aliases:
        al = a.strip().lower()
        if not al:
            continue
        if al in text_lower:
            return a
    return None


def extract_sequence(seq_regex: List[str], filename_or_folder: str) -> Optional[int]:
    for r in seq_regex:
        try:
            m = re.search(r, filename_or_folder)
        except re.error:
            continue
        if m and m.groups():
            try:
                val = int(m.group(1))
                return val
            except Exception:
                continue
    return None


def path_tail_segments(rel_path: Optional[str], max_tail: int = 4) -> str:
    if not rel_path:
        return ""
    parts = re.split(r"[\\/]+", rel_path)
    tail = parts[-max_tail:]
    return "/".join(tail)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Match variants to designer collections (dry-run by default)")
    p.add_argument("--db-url", default=None, help="Override database URL")
    p.add_argument("--designer", action="append", default=None, help="Limit to one or more designer keys (can repeat)")
    p.add_argument("--limit", type=int, default=0, help="Process at most N variants (0=all)")
    p.add_argument("--apply", action="store_true", help="Apply updates to Variant.collection_* (default: dry-run)")
    p.add_argument("--out", default=None, help="Write JSON report to this path (default includes timestamp)")
    p.add_argument("--append-timestamp", action="store_true", help="Append timestamp to --out filename")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing collection_* fields if present")
    args = p.parse_args(argv)

    reconfigure_db(args.db_url)

    # Prepare report path
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.out:
        base = Path(args.out)
        if args.append_timestamp:
            out_path = base.with_name(f"{base.stem}_{ts}{'_apply' if args.apply else ''}{base.suffix or '.json'}")
        else:
            out_path = base
    else:
        out_path = reports_dir / f"match_collections_{ts}{'_apply' if args.apply else ''}.json"

    total = 0
    applied = 0
    proposals: List[Dict[str, Any]] = []

    with _dbs.get_session() as session:
        from sqlalchemy import select
        q = select(Variant)
        if args.limit and args.limit > 0:
            q = q.limit(args.limit)
        variants = session.execute(q).scalars().all()

        # Group rules per designer
        rules_cache: Dict[str, List[CollRule]] = {}

        for v in variants:
            total += 1
            dkey = (v.designer or "").strip().lower()
            if not dkey:
                continue
            if args.designer and dkey not in {k.lower() for k in args.designer}:
                continue

            # Lazy-load rules for this designer
            if dkey not in rules_cache:
                rules_cache[dkey] = load_rules_for_designer(dkey)
            rules = rules_cache.get(dkey) or []
            if not rules:
                continue

            tail = path_tail_segments(v.rel_path, max_tail=4)
            tail_lower = tail.lower()
            filename = (v.filename or "")
            joined = tail + " " + filename

            accepted: Optional[Dict[str, Any]] = None
            candidates: List[Dict[str, Any]] = []

            for r in rules:
                # 1) Deterministic pattern match near tail
                pm = first_match(r.path_patterns, tail)
                if pm:
                    pat, m = pm
                    seq = extract_sequence(r.seq_regex, filename or tail)
                    accepted = {
                        "collection_id": r.coll_id,
                        "collection_name": r.name,
                        "collection_cycle": r.cycle,
                        "collection_theme": r.theme,
                        "original_label": m.group(0),
                        "match_via": f"regex:{pat}",
                        "sequence": seq,
                    }
                # 2) Conservative alias contains match
                elif r.aliases:
                    hit = contains_alias(r.aliases, tail_lower)
                    if hit:
                        seq = extract_sequence(r.seq_regex, filename or tail)
                        candidates.append({
                            "collection_id": r.coll_id,
                            "collection_name": r.name,
                            "collection_cycle": r.cycle,
                            "collection_theme": r.theme,
                            "original_label": hit,
                            "match_via": "alias-contains",
                            "sequence": seq,
                        })

                if accepted:
                    break

            # If no deterministic accept, pick first candidate (we keep patterns specific, so low risk)
            if not accepted and candidates:
                accepted = candidates[0]

            prop: Dict[str, Any] = {
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "filename": v.filename,
                "designer": v.designer,
                "accepted": accepted,
            }
            proposals.append(prop)

            if accepted and args.apply:
                try:
                    if args.overwrite or not getattr(v, 'collection_id', None):
                        v.collection_id = accepted["collection_id"]
                    if args.overwrite or not getattr(v, 'collection_original_label', None):
                        v.collection_original_label = accepted["original_label"]
                    if args.overwrite or not getattr(v, 'collection_cycle', None):
                        v.collection_cycle = accepted.get("collection_cycle")
                    if args.overwrite or not getattr(v, 'collection_theme', None):
                        v.collection_theme = accepted.get("collection_theme")
                    seq = accepted.get("sequence")
                    if seq is not None and (args.overwrite or not getattr(v, 'collection_sequence_number', None)):
                        v.collection_sequence_number = int(seq)
                    applied += 1
                except Exception:
                    # continue collecting proposals even if one write fails
                    pass

        if args.apply:
            session.commit()

    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "ts": datetime.utcnow().isoformat() + "Z",
            "apply": args.apply,
            "limit": args.limit,
            "designers": args.designer,
            "total_variants": total,
            "applied": applied,
            "proposals": proposals,
        }, f, ensure_ascii=False, indent=2)

    print(f"Report written: {out_path}")
    if args.apply:
        print(f"Applied: {applied}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

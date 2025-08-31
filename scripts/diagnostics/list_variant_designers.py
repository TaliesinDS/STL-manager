#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, DB_URL  # type: ignore
from db.models import Variant, File  # type: ignore
from scripts.quick_scan import SPLIT_CHARS  # type: ignore
from scripts.quick_scan import tokenize  # type: ignore

def build_designer_alias_map(session) -> dict[str, str]:
    from db.models import VocabEntry  # lazy import
    rows = session.query(VocabEntry).filter_by(domain="designer").all()
    amap: dict[str, str] = {}
    for r in rows:
        key = r.key
        amap[key.lower()] = key
        for a in (r.aliases or []):
            amap[(a or '').strip().lower()] = key
    return amap

MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb', '.ztl', '.step', '.stp', '.lys', '.chitubox', '.ctb'}

def tokens_from_variant_simple(session, variant) -> list[str]:
    toks: list[str] = []
    seen = set()
    try:
        for t in tokenize(Path(variant.rel_path or "")):
            if t not in seen:
                seen.add(t); toks.append(t)
    except Exception:
        pass
    if variant.filename:
        try:
            for t in tokenize(Path(variant.filename)):
                if t not in seen:
                    seen.add(t); toks.append(t)
        except Exception:
            pass
    # include a few model-file tokens if present
    for f in getattr(variant, 'files', []) or []:
        p = Path((f.filename or f.rel_path or '')).suffix.lower()
        if not p or p not in MODEL_EXTS:
            continue
        try:
            for t in tokenize(Path(f.filename or f.rel_path)):
                if t not in seen:
                    seen.add(t); toks.append(t)
        except Exception:
            continue
    return toks


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="List variants and designer info for a given ID range")
    ap.add_argument("--start", type=int, required=True, help="Start ID (inclusive)")
    ap.add_argument("--end", type=int, required=True, help="End ID (inclusive)")
    ap.add_argument("--out", help="Write JSON output to this file")
    ap.add_argument("--limit-tokens", type=int, default=50, help="Max tokens to include per variant in output")
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    start_id, end_id = args.start, args.end
    if start_id > end_id:
        start_id, end_id = end_id, start_id
    print(f"Using database: {DB_URL}")
    with get_session() as session:
        dmap = build_designer_alias_map(session)
        q = (
            session.query(Variant)
            .filter(Variant.id >= start_id, Variant.id <= end_id)
            .order_by(Variant.id)
        )
        rows = q.all()
        print(f"Found {len(rows)} variants in [{start_id}, {end_id}]")
        out = []
        for v in rows:
            toks = tokens_from_variant_simple(session, v)
            hits = []
            for t in toks:
                k = t.lower()
                if k in dmap:
                    if dmap[k] not in hits:
                        hits.append(dmap[k])
            out.append(
                {
                    "id": v.id,
                    "rel_path": v.rel_path,
                    "filename": v.filename,
                    "designer_current": v.designer,
                    "designer_token_hits": hits,
                    "tokens": toks[: args.limit_tokens],
                }
            )
        if args.out:
            p = Path(args.out)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Wrote: {p}")
        else:
            print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

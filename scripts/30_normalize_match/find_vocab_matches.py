#!/usr/bin/env python3
"""Find variants whose path/filename tokens match franchise or character alias maps.

Usage:
    python scripts/30_normalize_match/find_vocab_matches.py --limit 50 --only-unassigned

Outputs JSON with counts and a small sample of matches.
"""
from __future__ import annotations
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from scripts.normalize_inventory import tokens_from_variant, build_franchise_alias_map, build_character_alias_map, build_designer_alias_map


def find_matches(limit: int = 100, only_unassigned: bool = False):
    results = []
    counts = {"variants_examined": 0, "franchise_matches": 0, "character_matches": 0}
    with get_session() as session:
        franchise_map = build_franchise_alias_map(session)
        character_map = build_character_alias_map(session)
        designer_map = build_designer_alias_map(session)

        q = session.query(Variant).join(Variant.files).distinct().limit(limit)
        for v in q:
            counts["variants_examined"] += 1
            toks = tokens_from_variant(session, v)
            matched_fr = []
            matched_ch = []
            for t in toks:
                if t in franchise_map:
                    matched_fr.append({"token": t, "canonical": franchise_map[t]})
                if t in character_map:
                    matched_ch.append({"token": t, "canonical": character_map[t]})
            if only_unassigned:
                if matched_fr and v.franchise is not None:
                    matched_fr = []
                if matched_ch and getattr(v, 'codex_unit_name', None) is not None:
                    matched_ch = []
                if not matched_fr and not matched_ch:
                    continue
            if matched_fr:
                counts["franchise_matches"] += 1
            if matched_ch:
                counts["character_matches"] += 1
            results.append({
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "franchise_existing": v.franchise,
                "codex_unit_existing": getattr(v, 'codex_unit_name', None),
                "matched_franchises": matched_fr,
                "matched_characters": matched_ch,
                "tokens": toks,
            })
    return {"counts": counts, "sample": results}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Find variants matching franchise/character alias maps')
    ap.add_argument('--limit', type=int, default=200, help='Max variants to examine')
    ap.add_argument('--only-unassigned', action='store_true', help='Only show matches where target field is not already set')
    args = ap.parse_args()
    out = find_matches(limit=args.limit, only_unassigned=args.only_unassigned)
    print(json.dumps(out, indent=2, ensure_ascii=False))

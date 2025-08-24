#!/usr/bin/env python3
"""Apply franchise/character vocab matches to Variants (safe: dry-run default).

Usage:
  python scripts/apply_vocab_matches.py --limit 200
  python scripts/apply_vocab_matches.py --limit 200 --apply --batch 50

This script:
  - Builds alias maps for `franchise` and `character` domains from VocabEntry
  - Scans Variants (joined to Files) and finds tokens matching those maps
  - Proposes setting `variant.franchise` or `variant.codex_unit_name` when
    the corresponding DB field is empty
  - Dry-run prints proposals; `--apply` writes changes (commits in batches)

Conservative by default: only writes when target fields are empty; use
`--force` to overwrite.
"""
from __future__ import annotations
import sys
from pathlib import Path
import json
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from scripts.normalize_inventory import (
    tokens_from_variant,
    build_franchise_alias_map,
    build_character_alias_map,
)


def propose_for_variant(session, v, franchise_map, character_map, force=False):
    toks = tokens_from_variant(session, v)
    proposal = {"variant_id": v.id, "rel_path": v.rel_path, "proposed": {}}
    # Franchise
    if (v.franchise in (None, "") ) or force:
        for t in toks:
            if t in franchise_map:
                # Weak token rule: 2-letter tokens are considered weak
                # (e.g., 'sw','gw') and should only be proposed if there's
                # supporting context: another franchise token present or a
                # character match.
                alias_count = sum(1 for c in toks if c in franchise_map)
                has_character = any(c in character_map for c in toks)
                strong = len(t) > 2 or alias_count > 1 or has_character
                if strong:
                    proposal["proposed"]["franchise"] = franchise_map[t]
                    proposal["proposed"]["franchise_token"] = t
                    break
    # Codex unit / character
    # Character hints: propose setting character_name/character_aliases.
    existing_char = getattr(v, 'character_name', None)
    if (existing_char in (None, "")) or force:
        for t in toks:
            if t in character_map:
                proposal["proposed"]["character_name"] = character_map[t]
                proposal["proposed"]["character_aliases"] = [t]
                break
    return proposal


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Apply franchise/character vocab matches to Variants")
    ap.add_argument('--limit', type=int, default=200, help='Max variants to examine')
    ap.add_argument('--batch', type=int, default=50, help='Commit batch size when applying')
    ap.add_argument('--apply', action='store_true', help='Write proposed changes to DB')
    ap.add_argument('--force', action='store_true', help='Overwrite existing fields when applying')
    args = ap.parse_args(argv)

    results = []
    with get_session() as session:
        franchise_map = build_franchise_alias_map(session)
        character_map = build_character_alias_map(session)

        q = session.query(Variant).join(Variant.files).distinct().limit(args.limit)
        for v in q:
            p = propose_for_variant(session, v, franchise_map, character_map, force=args.force)
            if p.get("proposed"):
                results.append(p)

        print(json.dumps({"dry_run": not args.apply, "count": len(results), "proposals": results[:50]}, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no changes written. Re-run with --apply to commit proposals.")
            return 0

        # Apply proposals in batches
        applied = 0
        to_commit = []
        for p in results:
            v = session.query(Variant).filter_by(id=p["variant_id"]).one_or_none()
            if not v:
                continue
            prop = p.get("proposed", {})
            any_changed = False
            if "franchise" in prop and ((v.franchise in (None, "")) or args.force):
                v.franchise = prop["franchise"]
                any_changed = True
            # Apply character proposals
            if "character_name" in prop and ((getattr(v, 'character_name', None) in (None, "")) or args.force):
                v.character_name = prop["character_name"]
                # set aliases if provided
            if "character_aliases" in prop and ((getattr(v, 'character_aliases', None) in (None, [])) or args.force):
                v.character_aliases = prop["character_aliases"]
                any_changed = True
            if any_changed:
                to_commit.append(v)
            if len(to_commit) >= args.batch:
                try:
                    session.commit()
                    applied += len(to_commit)
                    to_commit = []
                except Exception as e:
                    print(f"Commit failed: {e}")
                    raise

        if to_commit:
            session.commit()
            applied += len(to_commit)

        print(f"Applied changes to {applied} variants.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

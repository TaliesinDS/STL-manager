#!/usr/bin/env python3
"""Assign codex unit names for Age of Sigmar variants using vocab/codex_units_aos.md

Conservative by default: dry-run prints proposals; use --apply to write.
Matches only when variant appears to belong to Age of Sigmar (franchise or path/faction hints).
"""
from __future__ import annotations

from pathlib import Path
import sys
import re
import json
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from scripts.normalize_inventory import tokens_from_variant, TABLETOP_HINTS


CODex_PATH = PROJECT_ROOT / 'vocab' / 'codex_units_aos.md'


def parse_codex_aos(path: Path) -> Dict[str, str]:
    """Return alias (lower) -> canonical name for AoS codex units (cities_of_sigmar only).
    Parses the simple YAML-like structure in the markdown file.
    """
    text = path.read_text(encoding='utf-8')
    # Extract the cities_of_sigmar block
    # Find the line 'cities_of_sigmar:' and then collect nested lines until next top-level key
    lines = text.splitlines()
    in_block = False
    block_indent = None
    aliases_map: Dict[str, str] = {}
    canon = None
    # pattern: 		freeguild_steelhelms: ["steelhelm", ...]
    entry_re = re.compile(r"\s*([a-z0-9_]+):\s*\[(.*?)\]\s*$", re.I)
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith('cities_of_sigmar:'):
            in_block = True
            continue
        if not in_block:
            continue
        # stop if next top-level group (no leading spaces)
        if stripped and not ln.startswith('\t') and not ln.startswith('    '):
            # likely new top-level franchise block
            break
        m = entry_re.match(ln)
        if m:
            canonical = m.group(1).strip()
            list_part = m.group(2)
            # split by comma while handling quotes
            items = [it.strip().strip('"\'') for it in list_part.split(',') if it.strip()]
            # include canonical as alias as well
            aliases = [canonical] + items
            for a in aliases:
                if not a:
                    continue
                aliases_map[a.lower()] = canonical
    return aliases_map


def is_aos_variant(v: Variant) -> bool:
    # AoS detection heuristics: franchise explicitly set, or path contains 'Cities of Sigmar' or faction_general contains 'cities'
    if v.franchise and 'sigmar' in (v.franchise or '').lower():
        return True
    if v.rel_path and 'cities of sigmar' in (v.rel_path or '').lower():
        return True
    if v.faction_general and 'sigmar' in (v.faction_general or '').lower():
        return True
    return False


def process(apply: bool, batch: int):
    amap = parse_codex_aos(CODex_PATH)
    if not amap:
        print('No AoS codex aliases found; aborting.')
        return
    proposals = []
    with get_session() as session:
        q = session.query(Variant).join(Variant.files).distinct()
        total = q.count()
        print(f'Examining {total} variants for AoS unit matches...')
        offset = 0
        while True:
            rows = q.limit(batch).offset(offset).all()
            if not rows:
                break
            for v in rows:
                if not is_aos_variant(v):
                    continue
                # skip tabletop-only variants (we only want model units)
                tokens = tokens_from_variant(session, v)
                if not tokens:
                    continue
                token_set = {t.lower() for t in tokens}
                # find any alias intersection with cities_of_sigmar aliases
                matched = None
                for t in token_set:
                    if t in amap:
                        matched = amap[t]
                        break
                if matched:
                    # only propose if codex_unit_name empty
                    if not v.codex_unit_name:
                        proposals.append({'variant_id': v.id, 'rel_path': v.rel_path, 'codex_unit_name': matched})
            offset += batch

    print(f'Proposed codex_unit_name assignments for {len(proposals)} variants (dry-run={not apply}).')
    for p in proposals[:20]:
        print(json.dumps(p, indent=2))

    if apply and proposals:
        with get_session() as session:
            offset = 0
            while True:
                rows = q.limit(batch).offset(offset).all()
                if not rows:
                    break
                any_changed = False
                for v in rows:
                    if not is_aos_variant(v):
                        continue
                    tokens = tokens_from_variant(session, v)
                    if not tokens:
                        continue
                    token_set = {t.lower() for t in tokens}
                    matched = None
                    for t in token_set:
                        if t in amap:
                            matched = amap[t]
                            break
                    if matched and not v.codex_unit_name:
                        v.codex_unit_name = matched
                        curw = v.normalization_warnings or []
                        if 'codex_unit_assigned_auto' not in curw:
                            curw = list(curw) + ['codex_unit_assigned_auto']
                        v.normalization_warnings = curw
                        any_changed = True
                if any_changed:
                    session.commit()
                offset += batch
        print('Apply complete.')


def parse_args(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Assign AoS codex unit names from vocab/codex_units_aos.md')
    ap.add_argument('--batch', type=int, default=200)
    ap.add_argument('--apply', action='store_true')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    process(apply=args.apply, batch=args.batch)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))

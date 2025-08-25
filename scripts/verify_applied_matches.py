#!/usr/bin/env python3
"""Verify that applied proposals were written to the DB.
Reads match_proposals_v3.json and prints variant id, rel_path, franchise, character_name.
"""
import json
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from db.session import get_session
from db.models import Variant

PROPOSALS = PROJECT_ROOT / 'match_proposals_v3.json'
if not PROPOSALS.exists():
    print('No match_proposals_v3.json found.')
    raise SystemExit(2)

with PROPOSALS.open('r', encoding='utf8') as fh:
    raw = fh.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # File may contain trailing log lines after the JSON (e.g. "Dry-run: ...").
        # Extract the first top-level JSON object by matching braces.
        start = raw.find('{')
        if start == -1:
            print('No JSON object found in proposals file.')
            raise SystemExit(2)
        depth = 0
        end = None
        for i in range(start, len(raw)):
            ch = raw[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            print('Could not find end of JSON object in proposals file.')
            raise SystemExit(2)
        snippet = raw[start:end]
        data = json.loads(snippet)
ids = [p['variant_id'] for p in data.get('proposals', [])]

with get_session() as session:
    rows = session.query(Variant).filter(Variant.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}
    print('{:>6}  {:<60}  {:<30}  {}'.format('id','rel_path','franchise','character_name'))
    for vid in ids:
        v = by_id.get(vid)
        if not v:
            print(f'{vid:6}  MISSING')
            continue
        print('{:6}  {:<60}  {:<30}  {}'.format(v.id, (v.rel_path or '')[:60], (v.franchise or '')[:30], (v.character_name or '')))

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_json_with_trailer(path: Path) -> dict:
    raw = path.read_text(encoding='utf8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        if start == -1:
            raise ValueError('No JSON object found in file')
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
            raise ValueError('Could not find end of JSON object in file')
        snippet = raw[start:end]
        return json.loads(snippet)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Verify that applied proposals were written to the DB')
    ap.add_argument('--db-url', help='Database URL (overrides STLMGR_DB_URL)')
    ap.add_argument('--file', default=str(PROJECT_ROOT / 'match_proposals_v3.json'), help='Proposals JSON file to read')
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ['STLMGR_DB_URL'] = args.db_url

    path = Path(args.file)
    if not path.exists():
        print(f'No proposals file found at {path}.')
        return 2
    try:
        data = _load_json_with_trailer(path)
    except Exception as e:
        print(f'Failed to parse proposals file: {e}')
        return 2
    ids = [p.get('variant_id') for p in data.get('proposals', []) if 'variant_id' in p]

    from db.models import Variant
    from db.session import get_session  # late import to honor --db-url
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
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

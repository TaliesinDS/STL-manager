#!/usr/bin/env python3
"""
Sync characters from `vocab/franchises/*.json` into VocabEntry(domain='character').

Dry-run by default; pass `--apply` to commit changes.

This follows the same upsert pattern used by `scripts/load_franchises.py` and
`scripts/sync_franchise_tokens_to_vocab.py`.
"""
from pathlib import Path
import sys
import json
import argparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import SessionLocal
from db.models import VocabEntry

FR_DIR = PROJECT_ROOT / 'vocab' / 'franchises'


def load_characters_from_file(path: Path):
    try:
        obj = json.loads(path.read_text(encoding='utf8'))
    except Exception:
        return []
    chars = obj.get('characters') or []
    out = []
    for c in chars:
        if isinstance(c, str):
            name = c
            aliases = []
        elif isinstance(c, dict):
            name = c.get('name') or c.get('id') or c.get('canonical') or c.get('canonical_name')
            aliases = c.get('aliases') or c.get('alias') or []
        else:
            continue
        if not name:
            continue
        out.append({'name': str(name), 'aliases': [str(a) for a in aliases]})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Write VocabEntry rows to DB')
    args = p.parse_args()

    session = SessionLocal()
    created = 0
    updated = 0
    total = 0
    try:
        for jf in sorted(FR_DIR.glob('*.json')):
            chars = load_characters_from_file(jf)
            for c in chars:
                total += 1
                name = c['name']
                aliases = sorted(set([name.lower()] + [a.lower() for a in c['aliases'] or []]))
                # canonical key = normalized lowercased name
                key = name
                ve = session.query(VocabEntry).filter_by(domain='character', key=key).one_or_none()
                if ve:
                    # merge aliases
                    cur = set(ve.aliases or [])
                    new = set(aliases)
                    merged = sorted(cur.union(new))
                    if merged != (ve.aliases or []):
                        if args.apply:
                            ve.aliases = merged
                            updated += 1
                        else:
                            updated += 1
                else:
                    if args.apply:
                        ve = VocabEntry(domain='character', key=key, aliases=aliases, meta={'source':'vocab/franchises'})
                        session.add(ve)
                        created += 1
                    else:
                        created += 1
        if args.apply:
            session.commit()
    finally:
        session.close()
    if args.apply:
        print(f'Committed character vocab sync: total={total} created={created} updated={updated}')
    else:
        print(f'Dry-run character vocab sync: total={total} would_create={created} would_update={updated}')


if __name__ == '__main__':
    main()

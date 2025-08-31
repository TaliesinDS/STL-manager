from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

fr_dir = PROJECT_ROOT / 'vocab' / 'franchises'


def load_tokens_for_franchise(path: Path):
    try:
        obj = json.loads(path.read_text(encoding='utf8'))
    except Exception:
        return None
    key = obj.get('franchise') or obj.get('key') or path.stem
    tokens = obj.get('tokens', {}) or {}
    aliases = set(obj.get('aliases') or [])
    # include strong/weak/stop tokens as aliases so DB alias map finds them
    for s in tokens.get('strong_signals', []) or []:
        aliases.add(str(s).strip().lower())
    for w in tokens.get('weak_signals', []) or []:
        aliases.add(str(w).strip().lower())
    for st in tokens.get('stop_conflicts', []) or []:
        aliases.add(str(st).strip().lower())
    return key, sorted(a for a in aliases if a)
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Sync franchise tokens from vocab/franchises/*.json into DB VocabEntry')
    ap.add_argument('--db-url', help='Database URL (overrides STLMGR_DB_URL)')
    ap.add_argument('--apply', action='store_true', help='Apply changes to DB; default is dry-run')
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ['STLMGR_DB_URL'] = args.db_url

    from db.session import SessionLocal  # late import to honor --db-url
    from db.models import VocabEntry

    session = SessionLocal()
    created = 0
    updated = 0
    try:
        for jf in sorted(fr_dir.glob('*.json')):
            info = load_tokens_for_franchise(jf)
            if not info:
                continue
            key, aliases = info
            ve = session.query(VocabEntry).filter_by(domain='franchise', key=key).one_or_none()
            if ve:
                # merge aliases
                cur = set(ve.aliases or [])
                new = set(aliases)
                merged = sorted(cur.union(new))
                if merged != (ve.aliases or []):
                    ve.aliases = merged
                    updated += 1
            else:
                ve = VocabEntry(domain='franchise', key=key, aliases=aliases, meta={'source': 'vocab/franchises'})
                session.add(ve)
                created += 1
        if args.apply:
            session.commit()
            print(f'Committed franchise alias sync: created={created} updated={updated}')
        else:
            session.rollback()
            print(f'Dry-run: would create={created} update={updated}')
    finally:
        session.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

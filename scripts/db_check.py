#!/usr/bin/env python3
"""Check which DB URL the app is using and print a quick summary.

Prints:
 - Effective DB_URL
 - Local SQLite path when applicable
 - Count of variants with a non-empty `franchise`
 - A small sample of variants with franchise set
"""
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import DB_URL, engine
from sqlalchemy import text

print('Effective DB_URL:', DB_URL)
if DB_URL.startswith('sqlite:///'):
    local_path = DB_URL.replace('sqlite:///', '')
    print('Local SQLite file path:', Path(local_path).resolve())

try:
    with engine.connect() as conn:
        r = conn.execute(text("select count(*) from variant where franchise is not null and franchise != ''"))
        total = r.scalar()
        print('Variants with franchise set:', total)
        print('\nSample rows (id, franchise, rel_path):')
        rows = conn.execute(text("select id, franchise, rel_path from variant where franchise is not null and franchise != '' order by id limit 20")).fetchall()
        for row in rows:
            print(f"{row[0]:6}  {row[1]:<30}  {row[2]}")
except Exception as e:
    print('Error querying DB:', e)
    raise

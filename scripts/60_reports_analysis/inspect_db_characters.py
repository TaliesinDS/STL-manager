#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from db.session import engine, SessionLocal
from db.models import Character


def main(argv: list[str] | None = None) -> int:
    print('DB_URL from session engine:', engine.url)
    with engine.connect() as conn:
        rs = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        tables = [r[0] for r in rs.fetchall()]
    print('tables:', tables)

    s = SessionLocal()
    try:
        count = s.query(Character).count()
        print('db_character_count', count)
        if count > 0:
            for ch in s.query(Character).limit(10).all():
                print('SAMPLE:', ch.id, ch.name, 'aliases=', ch.aliases, 'franchise=', ch.franchise)
    finally:
        s.close()
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

"""Canonical DB inspector: prints effective DB URL, basic counts, and samples.

Combines previous `inspect_db.py` and `db_check.py` behaviors.
"""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from db.session import DB_URL, engine, get_session
from db.models import Variant, File, Archive, Collection, Character


def main(argv: list[str] | None = None) -> int:
    print('Effective DB_URL:', DB_URL)
    if DB_URL.startswith('sqlite:///'):
        local_path = DB_URL.replace('sqlite:///', '')
        print('Local SQLite file path:', Path(local_path).resolve())

    # Quick raw SQL samples for franchise presence
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
        print('[warn] Error querying DB for franchise summary:', e)

    # ORM-based global counts and samples
    try:
        with get_session() as session:
            v_count = session.query(Variant).count()
            f_count = session.query(File).count()
            a_count = session.query(Archive).count()
            c_count = session.query(Collection).count()
            ch_count = session.query(Character).count()

            print(f"\nCounts -> Variants: {v_count} | Files: {f_count} | Archives: {a_count} | Collections: {c_count} | Characters: {ch_count}\n")

            print("Sample Variants:")
            for v in session.query(Variant).limit(5):
                print(f"- id={v.id} rel_path={v.rel_path} filename={v.filename} files={len(v.files)}")

            print("\nSample Files:")
            for f in session.query(File).limit(5):
                print(f"- id={f.id} rel_path={f.rel_path} filename={f.filename} hash={f.hash_sha256}")
    except Exception as e:
        print('[warn] Error during ORM inspection:', e)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

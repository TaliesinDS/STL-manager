"""Canonical DB inspector: prints DB summary and optional samples.

Combines previous `inspect_db.py` and `db_check.py` behaviors and adds
Windows-friendly CLI options for focused spot checks (e.g., english_tokens).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

from db.models import Archive, Character, Collection, File, Variant


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Inspect STL-manager database')
    ap.add_argument('--db-url', type=str, help='Override DB URL (e.g., sqlite:///./data/stl_manager_v1.db)')
    ap.add_argument('--english-sample', action='store_true', help='Print counts and a sample of english_tokens/ui_display_en')
    ap.add_argument('--limit', type=int, default=5, help='Sample size for listings')
    return ap.parse_args(argv or [])


def _maybe_reconfigure_db(db_url: str | None) -> None:
    if not db_url:
        return
    try:
        import db.session as _dbs
        if hasattr(_dbs, 'reconfigure'):
            _dbs.reconfigure(db_url)
            return
        # Fallback minimal reconfigure
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import Session as _S
        from sqlalchemy.orm import sessionmaker as _sm
        try:
            _dbs.engine.dispose()
        except Exception:
            pass
        _dbs.DB_URL = db_url
        _dbs.engine = _ce(db_url, future=True)
        _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
    except Exception as e:
        print('[warn] Failed to reconfigure DB session:', e)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _maybe_reconfigure_db(getattr(args, 'db_url', None))
    # Import after potential reconfigure so DB_URL/engine reflect changes
    from db.session import DB_URL as _DBURL  # type: ignore
    from db.session import engine as _engine
    from db.session import get_session as _get_session

    print('Effective DB_URL:', _DBURL)
    if _DBURL.startswith('sqlite:///'):
        local_path = _DBURL.replace('sqlite:///', '')
        print('Local SQLite file path:', Path(local_path).resolve())

    # Quick raw SQL samples for franchise presence
    try:
        with _engine.connect() as conn:
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
        with _get_session() as session:
            v_count = session.query(Variant).count()
            f_count = session.query(File).count()
            a_count = session.query(Archive).count()
            c_count = session.query(Collection).count()
            ch_count = session.query(Character).count()

            print(f"\nCounts -> Variants: {v_count} | Files: {f_count} | Archives: {a_count} | Collections: {c_count} | Characters: {ch_count}\n")

            print("Sample Variants:")
            for v in session.query(Variant).limit(getattr(args, 'limit', 5)):
                print(f"- id={v.id} rel_path={v.rel_path} filename={v.filename} files={len(v.files)}")

            print("\nSample Files:")
            for f in session.query(File).limit(getattr(args, 'limit', 5)):
                print(f"- id={f.id} rel_path={f.rel_path} filename={f.filename} hash={f.hash_sha256}")

            if getattr(args, 'english_sample', False):
                print("\nenglish_tokens / ui_display_en summary:")
                # Counts via SQL for performance
                try:
                    with _engine.connect() as conn:
                        row_total = conn.execute(text("select count(*) from variant")).scalar() or 0
                        row_eng = conn.execute(text("select count(*) from variant where english_tokens is not null")).scalar() or 0
                        row_ui = conn.execute(text("select count(*) from variant where ui_display_en is not null and trim(ui_display_en) != ''")).scalar() or 0
                        print(json.dumps({
                            'total_variants': int(row_total),
                            'english_tokens_not_null': int(row_eng),
                            'ui_display_en_not_null': int(row_ui),
                        }, indent=2))
                except Exception as e:
                    print('[warn] Error computing english/ui counts:', e)

                print("\nSample rows (id, token_locale, english_tokens, ui_display_en, rel_path):")
                # Prefer rows with english_tokens present
                try:
                    q = session.query(Variant).filter(Variant.english_tokens != None).limit(getattr(args, 'limit', 5))  # noqa: E711
                    for v in q:
                        print("-", json.dumps({
                            'id': v.id,
                            'token_locale': getattr(v, 'token_locale', None),
                            'english_tokens': getattr(v, 'english_tokens', None),
                            'ui_display_en': getattr(v, 'ui_display_en', None),
                            'rel_path': v.rel_path,
                        }, ensure_ascii=False))
                except Exception as e:
                    print('[warn] Error sampling english_tokens rows:', e)
    except Exception as e:
        print('[warn] Error during ORM inspection:', e)

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

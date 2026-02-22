#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from db.models import Variant
from db.session import get_session


def rebind_db(db_url: str | None) -> None:
    if not db_url:
        return
    try:
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import Session as _S
        from sqlalchemy.orm import sessionmaker as _sm

        import db.session as _dbs
        try:
            _dbs.engine.dispose()
        except Exception:
            pass
        _dbs.DB_URL = db_url
        _dbs.engine = _ce(db_url, future=True)
        _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
    except Exception as e:
        print(f"Failed to reconfigure DB session for URL {db_url}: {e}")


def show(ids: list[int]):
    with get_session() as session:
        for vid in ids:
            v = session.query(Variant).get(vid)
            if not v:
                print(f"Variant id={vid} not found")
                continue
            raw = {c.name: getattr(v, c.name) for c in v.__table__.columns}
            data = {}
            for k, val in raw.items():
                try:
                    json.dumps(val)
                    data[k] = val
                except Exception:
                    data[k] = str(val)
            print(json.dumps({"variant_id": vid, "data": data}, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Show Variant rows by id")
    ap.add_argument("ids", nargs="+", help="Variant ids to display (space-separated)")
    ap.add_argument("--db-url", dest="db_url", help="Override DB URL (else uses STLMGR_DB_URL or default)")
    args = ap.parse_args(argv)
    rebind_db(args.db_url)
    try:
        ids = [int(x) for x in args.ids]
    except Exception as e:
        print(f"Error parsing ids: {e}")
        return 2
    show(ids)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

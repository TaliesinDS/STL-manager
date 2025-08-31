from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJ = Path(__file__).resolve().parent.parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify residual_tokens presence for a sample file/variant")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--like", default="%Ryuko%", help="SQL LIKE pattern to search in File.rel_path (default: %Ryuko%)")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    from db.session import get_session  # late import to honor --db-url
    from db.models import File, Variant

    with get_session() as s:
        f = s.query(File).filter(File.rel_path.like(args.like)).first()
        if f:
            print("Found file:", f.id)
            print("rel_path:", f.rel_path)
            print("file residual_tokens sample:", (f.residual_tokens or [])[:20])
            v = s.query(Variant).get(f.variant_id)
            print("variant residual_tokens sample:", (v.residual_tokens or [])[:20])
        else:
            print("No matching file found; printing sample file id=1 tokens")
            f2 = s.query(File).get(1)
            if not f2:
                print("No file with id=1 found.")
                return 2
            print("File 1 rel_path:", f2.rel_path)
            print("File 1 residual_tokens:", (f2.residual_tokens or [])[:40])
            v2 = s.query(Variant).get(f2.variant_id)
            if v2:
                print("Variant 1 residual_tokens:", (v2.residual_tokens or [])[:40])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

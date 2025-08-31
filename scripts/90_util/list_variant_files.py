#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if len(argv) < 1:
        print('Usage: list_variant_files.py <variant_id>')
        return 2
    vid = int(argv[0])
    with get_session() as session:
        v = session.query(Variant).get(vid)
        if not v:
            print(f'Variant {vid} not found')
            return 1
        files = getattr(v, 'files', [])
        out = []
        for f in files:
            out.append({
                'id': f.id,
                'filename': f.filename,
                'rel_path': f.rel_path,
                'size_bytes': f.size_bytes,
                'hash_sha256': f.hash_sha256
            })
        print(out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

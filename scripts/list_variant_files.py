#!/usr/bin/env python3
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from db.session import get_session
from db.models import Variant

if len(sys.argv) < 2:
    print('Usage: python scripts/list_variant_files.py <variant_id>')
    raise SystemExit(2)

vid = int(sys.argv[1])
with get_session() as session:
    v = session.query(Variant).get(vid)
    if not v:
        print(f'Variant {vid} not found')
        raise SystemExit(1)
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

#!/usr/bin/env python3
"""Export variants that currently have non-empty codex_unit_name for audit.
Writes a timestamped JSON file into reports/ with fields: variant_id, rel_path,
codex_unit_name, character_name, character_aliases.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant


def main():
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    out_path = ROOT / 'reports' / f'codex_unit_name_candidates_{ts}.json'
    results = []
    with get_session() as session:
        rows = session.query(Variant).filter(Variant.codex_unit_name.isnot(None), Variant.codex_unit_name != '').all()
        for v in rows:
            results.append({
                'variant_id': v.id,
                'rel_path': v.rel_path,
                'codex_unit_name': v.codex_unit_name,
                'character_name': getattr(v, 'character_name', None),
                'character_aliases': getattr(v, 'character_aliases', None),
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    raise SystemExit(main())

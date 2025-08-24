#!/usr/bin/env python3
"""Report which Variant.franchise keys exist and whether they have a
corresponding VocabEntry(domain='franchise', key=...).

Outputs a simple tab-separated report to stdout.
"""
from __future__ import annotations

from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant, VocabEntry


def run():
    out_lines = ["variant_id\trel_path\tfranchise\tvocab_exists"]
    with get_session() as session:
        rows = session.query(Variant).filter(Variant.franchise.isnot(None)).all()
        # Build set of existing franchise keys
        vrows = session.query(VocabEntry).filter_by(domain='franchise').all()
        existing = {v.key for v in vrows}
        for v in rows:
            key = v.franchise or ""
            exists = 'yes' if key in existing else 'no'
            out_lines.append(f"{v.id}\t{v.rel_path}\t{key}\t{exists}")

    print('\n'.join(out_lines))


if __name__ == '__main__':
    run()

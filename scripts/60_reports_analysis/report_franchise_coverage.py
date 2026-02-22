#!/usr/bin/env python3
"""Report which Variant.franchise keys exist and whether they have a
corresponding VocabEntry(domain='franchise', key=...).

Outputs a simple tab-separated report to stdout.
"""
from __future__ import annotations

import sys

from db.models import Variant, VocabEntry
from db.session import get_session


def main(argv: list[str] | None = None) -> int:
    out_lines = ["variant_id\trel_path\tfranchise\tvocab_exists"]
    with get_session() as session:
        rows = session.query(Variant).filter(Variant.franchise.isnot(None)).all()
        vrows = session.query(VocabEntry).filter_by(domain='franchise').all()
        existing = {v.key for v in vrows}
        for v in rows:
            key = v.franchise or ""
            exists = 'yes' if key in existing else 'no'
            out_lines.append(f"{v.id}\t{v.rel_path}\t{key}\t{exists}")

    print('\n'.join(out_lines))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

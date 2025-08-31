#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import VocabEntry, Variant


def main(argv: list[str] | None = None) -> int:
    with get_session() as s:
        total_vocab = s.query(VocabEntry).count()
        franchises = s.query(VocabEntry).filter_by(domain='franchise').count()
        characters = s.query(VocabEntry).filter_by(domain='character').count()
        print('VocabEntry total:', total_vocab)
        print('franchise entries:', franchises)
        print('character entries:', characters)
        print('\nSample franchise rows:')
        for r in s.query(VocabEntry).filter_by(domain='franchise').limit(5):
            print('-', r.key, 'aliases=', (r.aliases or [])[:10])
        print('\nSample character rows:')
        for r in s.query(VocabEntry).filter_by(domain='character').limit(5):
            print('-', r.key, 'aliases=', (r.aliases or [])[:10])
        vt = s.query(Variant).count()
        vt_tokens = s.query(Variant).filter(Variant.residual_tokens != None).count()
        print('\nVariants total:', vt)
        print('Variants with residual_tokens not null:', vt_tokens)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

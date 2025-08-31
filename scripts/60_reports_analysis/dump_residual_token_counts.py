#!/usr/bin/env python3
"""Dump global residual token frequencies to CSV for review.

Usage:
  .venv\Scripts\python.exe scripts/dump_residual_token_counts.py --top 2000 --out reports/residual_tokens_top.csv

Writes CSV with columns: token,count
Also prints top 50 tokens to stdout.
"""
from __future__ import annotations

import csv
import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant


def dump(top: int, out_path: Path) -> None:
    counter = Counter()
    with get_session() as session:
        for v in session.query(Variant).yield_per(200):
            toks = v.residual_tokens or []
            toks = [t.lower() for t in toks if t]
            counter.update(toks)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['token', 'count'])
        for tok, cnt in counter.most_common(top):
            writer.writerow([tok, cnt])

    for tok, cnt in counter.most_common(50):
        print(f"{tok}\t{cnt}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=2000)
    ap.add_argument('--out', type=Path, default=Path('reports') / 'residual_tokens_top.csv')
    args = ap.parse_args(argv)
    dump(args.top, args.out)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

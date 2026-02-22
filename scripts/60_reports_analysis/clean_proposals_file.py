#!/usr/bin/env python3
"""Clean a proposals file by keeping only JSON objects (one per line).

Some tools accidentally append stray JSON values (arrays/strings). This
utility will read the input file, skip any line that doesn't parse to a
JSON object (dict), and write a cleaned output file. By default it writes
to the same directory with a `.clean` suffix to avoid accidental data loss.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def clean_file(in_path: Path, out_path: Path) -> int:
    kept = 0
    skipped = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with in_path.open('r', encoding='utf-8') as fh_in, out_path.open('w', encoding='utf-8') as fh_out:
        for i, line in enumerate(fh_in, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                skipped += 1
                print(f"[warn] skipping malformed JSON at line {i}")
                continue
            if not isinstance(obj, dict):
                skipped += 1
                print(f"[warn] skipping non-object JSON at line {i}: {type(obj).__name__}")
                continue
            fh_out.write(json.dumps(obj, ensure_ascii=False))
            fh_out.write('\n')
            kept += 1
    print(f"Clean complete: kept={kept} skipped={skipped} (wrote {out_path})")
    return 0


def parse_args(argv: list[str]):
    ap = argparse.ArgumentParser(description='Clean proposals file (keep only JSON objects)')
    ap.add_argument('--in', dest='infile', required=True)
    ap.add_argument('--out', dest='outfile', required=False)
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ip = Path(args.infile)
    if not ip.exists():
        print(f'Input not found: {ip}', file=sys.stderr); return 2
    if args.outfile:
        op = Path(args.outfile)
    else:
        op = ip.with_suffix(ip.suffix + '.clean')
    return clean_file(ip, op)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

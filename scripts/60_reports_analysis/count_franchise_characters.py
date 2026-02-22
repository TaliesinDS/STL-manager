#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    files = sorted((ROOT / 'vocab' / 'franchises').glob('*.json'))
    total_files = len(files)
    files_with_chars = 0
    total_chars = 0
    for p in files:
        try:
            obj = json.loads(p.read_text(encoding='utf8'))
            chars = obj.get('characters') or []
            if chars:
                files_with_chars += 1
                total_chars += len(chars)
        except Exception as e:
            print('ERR', p, e)

    print('files_total', total_files)
    print('files_with_characters', files_with_chars)
    print('total_characters', total_chars)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

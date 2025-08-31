#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main(argv: list[str] | None = None) -> int:
    # Print the first franchise manifest with a characters array and a snippet
    for p in sorted((ROOT / 'vocab' / 'franchises').glob('*.json')):
        try:
            obj = json.loads(p.read_text(encoding='utf8'))
        except Exception:
            continue
        chars = obj.get('characters') or []
        if chars:
            print('FOUND', p)
            print('top-level keys:', list(obj.keys())[:20])
            print('characters_count', len(chars))
            print('first_char (raw):', chars[0])
            if isinstance(chars[0], dict):
                print('first_char keys:', list(chars[0].keys()))
            print('\n-- RAW JSON SNIPPET --\n')
            print(json.dumps(obj, indent=2)[:2000])
            break
    print('done')
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

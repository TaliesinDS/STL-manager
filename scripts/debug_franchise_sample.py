#!/usr/bin/env python3
import json
from pathlib import Path

for p in sorted(Path('vocab/franchises').glob('*.json')):
    try:
        obj = json.loads(p.read_text(encoding='utf8'))
    except Exception as e:
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

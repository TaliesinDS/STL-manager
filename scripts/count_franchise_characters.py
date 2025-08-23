#!/usr/bin/env python3
import json
from pathlib import Path

files = sorted(Path('vocab/franchises').glob('*.json'))
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

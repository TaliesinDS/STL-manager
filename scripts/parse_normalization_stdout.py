#!/usr/bin/env python3
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / 'reports' / 'normalization_stdout.txt'
OUT = ROOT / 'reports' / 'normalization_proposals.json'
text = IN.read_text(encoding='utf-8') if IN.exists() else ''
props = []
# capture JSON objects like {"variant_id": 123, ...}
for m in re.finditer(r'\{\s*\"variant_id\".*?\n\}', text, flags=re.DOTALL):
    candidate = m.group(0)
    try:
        props.append(json.loads(candidate))
    except Exception:
        pass
# Also try to capture lines that start with '{' and appear to be JSON per-line
for ln in text.splitlines():
    ln = ln.strip()
    if ln.startswith('{') and ln.endswith('}'):
        try:
            props.append(json.loads(ln))
        except Exception:
            pass
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(props, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote', OUT, 'with', len(props), 'proposal objects')

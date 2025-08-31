#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    IN = ROOT / 'reports' / 'normalization_stdout.txt'
    OUT = ROOT / 'reports' / 'normalization_proposals.json'
    text = IN.read_text(encoding='utf-8') if IN.exists() else ''
    props = []
    for m in re.finditer(r'\{\s*\"variant_id\".*?\n\}', text, flags=re.DOTALL):
        candidate = m.group(0)
        try:
            props.append(json.loads(candidate))
        except Exception:
            pass
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
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

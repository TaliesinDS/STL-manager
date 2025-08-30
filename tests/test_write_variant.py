#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant

def test(vid: int):
    with get_session() as session:
        v = session.query(Variant).get(vid)
        print('before support_state=', repr(v.support_state))
        v.support_state = 'supported_test'
        session.commit()
    with get_session() as session:
        v2 = session.query(Variant).get(vid)
        print('after support_state=', repr(v2.support_state))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/test_write_variant.py <id>')
        raise SystemExit(2)
    test(int(sys.argv[1]))

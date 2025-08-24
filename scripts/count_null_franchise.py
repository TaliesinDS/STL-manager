#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant

def main():
    with get_session() as s:
        c = s.query(Variant).filter(Variant.franchise.is_(None)).count()
    print(c)

if __name__ == '__main__':
    main()

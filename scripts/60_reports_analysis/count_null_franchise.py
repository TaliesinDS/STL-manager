#!/usr/bin/env python3
from __future__ import annotations

import sys

from db.models import Variant
from db.session import get_session


def main(argv: list[str] | None = None) -> int:
    with get_session() as s:
        c = s.query(Variant).filter(Variant.franchise.is_(None)).count()
    print(c)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

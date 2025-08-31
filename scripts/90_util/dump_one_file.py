#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import File


def main(argv: list[str] | None = None) -> int:
    with get_session() as s:
        f = s.query(File).first()
        if f:
            print('Sample File.rel_path:', f.rel_path)
            print('Sample File.filename:', f.filename)
        else:
            print('No File rows found')
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))

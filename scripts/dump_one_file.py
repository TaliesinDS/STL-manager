#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_and_run(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    scripts_dir = here.parent
    canonical = scripts_dir / '90_util' / 'dump_one_file.py'

    proj_root = scripts_dir.parent
    if str(proj_root) not in sys.path:
        sys.path.insert(0, str(proj_root))

    spec = importlib.util.spec_from_file_location('scripts.90_util.dump_one_file', canonical)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot import canonical script at: {canonical}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['scripts.90_util.dump_one_file'] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    if hasattr(mod, 'main'):
        try:
            return int(mod.main(argv))  # type: ignore[arg-type]
        except TypeError:
            return int(mod.main())  # type: ignore[call-arg]
    return 0


def main(argv: list[str] | None = None) -> int:
    return _load_and_run(argv)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

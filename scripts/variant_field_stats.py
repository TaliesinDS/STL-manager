#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_and_run(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    scripts_dir = here.parent
    canonical = scripts_dir / '60_reports_analysis' / 'variant_field_stats.py'

    spec = importlib.util.spec_from_file_location('scripts.60_reports_analysis.variant_field_stats', canonical)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot import canonical script at: {canonical}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['scripts.60_reports_analysis.variant_field_stats'] = mod
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

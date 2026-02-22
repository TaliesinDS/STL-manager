#!/usr/bin/env python
"""
Validate all YAML files under vocab/collections using ruamel.yaml.
Prints OK/ERR per file and exits with non-zero status if any errors are found.
"""
from __future__ import annotations

import glob
import os
import sys
from typing import List

try:
    from ruamel.yaml import YAML
except Exception:  # pragma: no cover
    print("ERR - ruamel.yaml is required. Please install requirements.", file=sys.stderr)
    raise


def validate(paths: List[str]) -> int:
    yaml = YAML(typ="rt")
    errs = 0
    for path in sorted(paths):
        try:
            with open(path, encoding="utf-8") as f:
                yaml.load(f)
            print(f"OK  - {path}")
        except Exception as e:
            errs += 1
            print(f"ERR - {path}: {e}")
    return errs


def main() -> int:
    root = os.path.join(".", "vocab", "collections")
    paths = glob.glob(os.path.join(root, "*.yaml"))
    if not paths:
        print(f"No YAML files found in {root}")
        return 0
    errs = validate(paths)
    print(f"Done. Errors: {errs}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

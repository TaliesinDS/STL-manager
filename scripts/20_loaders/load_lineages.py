#!/usr/bin/env python3
"""
Load vocab/lineages.yaml into the DB lineage table (dry-run by default).

Usage:
  .\.venv\Scripts\python.exe scripts/20_loaders/load_lineages.py --file vocab/lineages.yaml [--db-url sqlite:///./data/stl_manager_v1.db] [--commit]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root on sys.path for db imports regardless of CWD
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, reconfigure
from db.models import Lineage

from ruamel.yaml import YAML


def load_yaml(path: Path) -> Dict[str, Any]:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf8") as f:
        return yaml.load(f) or {}


def upsert_lineages(data: Dict[str, Any], source_file: str, commit: bool = False) -> dict:
    fams = data.get("families") or []
    created = 0
    updated = 0
    total = 0
    with get_session() as session:
        for fam in fams:
            family_key = fam.get("key")
            family_name = fam.get("name")
            context_tags = fam.get("context_tags") or []
            aliases_strong = fam.get("aliases_strong") or []
            aliases_weak = fam.get("aliases_weak") or []
            locale_aliases = fam.get("locale_aliases") or {}
            excludes = fam.get("excludes") or []

            # Upsert family row (primary_key = None)
            row = session.query(Lineage).filter_by(family_key=family_key, primary_key=None).one_or_none()
            if row:
                row.family_name = family_name
                row.name = family_name or family_key
                row.context_tags = context_tags
                row.aliases_strong = aliases_strong
                row.aliases_weak = aliases_weak
                row.locale_aliases = locale_aliases
                row.excludes = excludes
                row.source_file = source_file
                updated += 1
            else:
                row = Lineage(
                    family_key=family_key,
                    primary_key=None,
                    family_name=family_name,
                    name=family_name or family_key,
                    context_tags=context_tags,
                    aliases_strong=aliases_strong,
                    aliases_weak=aliases_weak,
                    locale_aliases=locale_aliases,
                    excludes=excludes,
                    source_file=source_file,
                )
                session.add(row)
                created += 1
            total += 1

            # Sublineages
            for sub in fam.get("sublineages") or []:
                pk = sub.get("key")
                name = sub.get("name")
                s_aliases_strong = sub.get("aliases_strong") or []
                s_aliases_weak = sub.get("aliases_weak") or []
                s_excludes = sub.get("excludes") or []
                row = session.query(Lineage).filter_by(family_key=family_key, primary_key=pk).one_or_none()
                if row:
                    row.family_name = family_name
                    row.name = name or pk
                    row.aliases_strong = s_aliases_strong
                    row.aliases_weak = s_aliases_weak
                    row.excludes = s_excludes
                    row.source_file = source_file
                    updated += 1
                else:
                    row = Lineage(
                        family_key=family_key,
                        primary_key=pk,
                        family_name=family_name,
                        name=name or pk,
                        context_tags=context_tags,
                        aliases_strong=s_aliases_strong,
                        aliases_weak=s_aliases_weak,
                        locale_aliases={},
                        excludes=s_excludes,
                        source_file=source_file,
                    )
                    session.add(row)
                    created += 1
                total += 1

        if commit:
            session.commit()
        else:
            session.rollback()
    return {"created": created, "updated": updated, "total": total}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Load lineages YAML into DB (dry-run by default)")
    p.add_argument("--file", default=str(PROJECT_ROOT / "vocab" / "lineages.yaml"), help="Path to vocab/lineages.yaml")
    p.add_argument("--db-url", dest="db_url", default=None, help="Database URL (overrides STLMGR_DB_URL)")
    p.add_argument("--commit", action="store_true", help="Apply changes (default: dry-run)")
    args = p.parse_args(argv)

    if args.db_url:
        reconfigure(args.db_url)

    path = Path(args.file)
    if not path.exists():
        print("File not found:", path)
        return 2

    data = load_yaml(path)
    summary = upsert_lineages(data, source_file=path.name, commit=args.commit)
    mode = "APPLY" if args.commit else "DRY-RUN"
    print(f"{mode}: lineage upsert summary -> created={summary['created']} updated={summary['updated']} total={summary['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

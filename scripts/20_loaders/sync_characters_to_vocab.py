#!/usr/bin/env python3
from __future__ import annotations

"""Sync characters from `vocab/franchises/*.json` into VocabEntry(domain='character').

Dry-run by default; pass --apply to commit. Supports --db-url to override DB
target. Optionally filter by franchise filename for faster iteration.
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FR_DIR = PROJECT_ROOT / "vocab" / "franchises"


def load_characters_from_file(path: Path) -> list[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf8"))
    except Exception:
        return []
    chars = obj.get("characters") or []
    out: list[dict] = []
    for c in chars:
        if isinstance(c, str):
            name = c
            aliases: list[str] = []
        elif isinstance(c, dict):
            name = c.get("name") or c.get("id") or c.get("canonical") or c.get("canonical_name")
            aliases = c.get("aliases") or c.get("alias") or []
        else:
            continue
        if not name:
            continue
        out.append({"name": str(name), "aliases": [str(a) for a in aliases]})
    return out


def normalize_key(s: str | None) -> str:
    return (s or "").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync characters from vocab/franchises/*.json to DB (dry-run by default)")
    ap.add_argument("--franchise", help="Optional franchise filename filter (e.g., 'warhammer_40k.json') to limit sync")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    from db.session import get_session  # late import to honor --db-url
    from db.models import VocabEntry

    # Gather characters from franchises JSON files
    targets = sorted(FR_DIR.glob("*.json"))
    if args.franchise:
        targets = [p for p in targets if p.name.lower() == args.franchise.lower()]
        if not targets:
            print(f"No franchise file matched: {args.franchise}")
            return 1

    desired: dict[str, dict] = {}
    for jf in targets:
        characters = load_characters_from_file(jf)
        for c in characters:
            key = normalize_key(c.get("name"))
            if not key:
                continue
            aliases = sorted(set([normalize_key(a) for a in (c.get("aliases") or []) if normalize_key(a)]))
            existing = desired.get(key)
            if existing:
                merged_aliases = sorted(set(existing["aliases"]).union(aliases))
                existing["aliases"] = merged_aliases
            else:
                desired[key] = {"key": key, "aliases": aliases}

    with get_session() as session:
        existing = session.query(VocabEntry).filter_by(domain="character").all()
        existing_by_key = {normalize_key(v.key): v for v in existing}

        to_create: list[dict] = []
        to_update: list[dict] = []
        to_delete: list[VocabEntry] = []

        for key, spec in desired.items():
            v = existing_by_key.get(key)
            if not v:
                to_create.append(spec)
            else:
                old_aliases = sorted([normalize_key(a) for a in (v.aliases or []) if normalize_key(a)])
                if old_aliases != spec["aliases"]:
                    to_update.append({"row": v, "spec": spec})

        for key, row in existing_by_key.items():
            if key not in desired:
                to_delete.append(row)

        report = {
            "create": to_create,
            "update": [{"id": u["row"].id, "key": u["row"].key, "aliases_new": u["spec"]["aliases"]} for u in to_update],
            "delete": [{"id": r.id, "key": r.key} for r in to_delete],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no DB changes made. Rerun with --apply to commit.")
            return 0

        # Apply
        for spec in to_create:
            row = VocabEntry(domain="character", key=spec["key"], aliases=spec["aliases"], meta={"source": "vocab/franchises"})
            session.add(row)
        for upd in to_update:
            row: VocabEntry = upd["row"]
            spec = upd["spec"]
            row.aliases = spec["aliases"]
        for row in to_delete:
            session.delete(row)
        session.commit()
        print("Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

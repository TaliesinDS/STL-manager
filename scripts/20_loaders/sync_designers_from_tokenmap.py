#!/usr/bin/env python3
from __future__ import annotations

"""Sync designers tokenmap file with DB VocabEntry/Variant rows.

Dry-run by default; pass --apply to write. Supports --db-url to override DB target.
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FENCE_RE = re.compile(r"^```")
ENTRY_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(\[.*\])\s*$")


def parse_tokenmap(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf8")
    lines = text.splitlines()
    inside = False
    result: dict[str, list[str]] = {}
    for ln in lines:
        if FENCE_RE.match(ln.strip()):
            inside = not inside
            continue
        if not inside:
            continue
        ln = ln.rstrip()
        if not ln or ln.lstrip().startswith("#"):
            continue
        m = ENTRY_RE.match(ln)
        if not m:
            continue
        key = m.group(1).strip()
        aliases_str = m.group(2)
        try:
            aliases_obj = ast.literal_eval(aliases_str)
            if not isinstance(aliases_obj, (list, tuple)):
                aliases = [str(aliases_obj)]
            else:
                aliases = [str(a) for a in aliases_obj]
        except Exception:
            aliases = []
        result[key] = aliases
    return result


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def build_tokenmap_sets(entries: dict[str, list[str]]) -> tuple[set[str], dict[str, str]]:
    canonicals: set[str] = set()
    alias_map: dict[str, str] = {}
    for canonical, aliases in entries.items():
        canonicals.add(canonical)
        alias_map[normalize_alias(canonical)] = canonical
        for a in aliases:
            alias_map[normalize_alias(a)] = canonical
    return canonicals, alias_map


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync designers tokenmap with DB (dry-run by default)")
    ap.add_argument("tokenmap", help="Path to designers_tokenmap.md")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--apply", action="store_true", help="Apply changes to DB (default: dry-run)")
    ap.add_argument("--delete-vocab", action="store_true", help="When --apply, also delete stale designer VocabEntry rows")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    from db.session import get_session  # late import to honor --db-url
    from db.models import VocabEntry, Variant

    path = Path(args.tokenmap)
    if not path.exists():
        print("Tokenmap file not found:", path)
        return 2

    entries = parse_tokenmap(path)
    tokenmap_keys = set(entries.keys())
    canonicals_set, alias_map = build_tokenmap_sets(entries)

    def find_stale_vocab(session, tokenmap_keys: set[str]) -> list[VocabEntry]:
        rows = session.query(VocabEntry).filter_by(domain="designer").all()
        return [r for r in rows if r.key not in tokenmap_keys]

    def find_variants_for_vocab(session, ve: VocabEntry) -> list[Variant]:
        target_norm = normalize_alias(ve.key or "")
        ve_alias_norms = [normalize_alias(x) for x in (ve.aliases or [])]
        matches: list[Variant] = []
        for v in session.query(Variant).filter(Variant.designer.isnot(None)).all():
            dn = normalize_alias(str(v.designer))
            if dn == target_norm or dn in ve_alias_norms:
                matches.append(v)
        return matches

    def find_orphaned_variants(session) -> list[Variant]:
        res: list[Variant] = []
        for v in session.query(Variant).filter(Variant.designer.isnot(None)).all():
            dn = normalize_alias(str(v.designer))
            if dn not in alias_map:
                res.append(v)
        return res

    with get_session() as session:
        stale = find_stale_vocab(session, tokenmap_keys)
        results = []
        total_variant_hits = 0
        for ve in stale:
            variants = find_variants_for_vocab(session, ve)
            total_variant_hits += len(variants)
            results.append({
                "vocab_id": ve.id,
                "key": ve.key,
                "aliases": ve.aliases,
                "variant_count": len(variants),
                "variant_sample": [{"id": v.id, "rel_path": v.rel_path, "designer": v.designer} for v in variants[:20]],
            })

        orphaned = find_orphaned_variants(session)
        orphaned_sample = [{"id": v.id, "rel_path": v.rel_path, "designer": v.designer} for v in orphaned[:20]]

        out = {
            "tokenmap_keys_count": len(tokenmap_keys),
            "stale_vocab_count": len(stale),
            "total_variant_matches": total_variant_hits,
            "details": results,
            "orphaned_variants_count": len(orphaned),
            "orphaned_variants_sample": orphaned_sample,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no DB changes made. Rerun with --apply to clear Variant.designer for matches and optionally --delete-vocab to remove entries.")
            return 0

        # apply changes
        if len(stale) == 0 and total_variant_hits == 0 and len(orphaned) == 0:
            print("Nothing to apply.")
            return 0

        print("Applying changes: clearing designer on matched Variants and orphaned variants...")
        for ve in stale:
            variants = find_variants_for_vocab(session, ve)
            for v in variants:
                v.designer = None
        for v in orphaned:
            v.designer = None
        if args.delete_vocab:
            print("Deleting stale VocabEntry rows...")
            for ve in stale:
                session.delete(ve)
        session.commit()
        print("Apply complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

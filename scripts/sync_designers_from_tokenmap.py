#!/usr/bin/env python3
"""Sync designers tokenmap file with DB VocabEntry/Variant rows.

Features:
 - Parse a designers tokenmap file (same format as `vocab/designers_tokenmap.md`).
 - Detect VocabEntry(domain='designer') rows that are not present in the tokenmap.
 - Report Variant rows that reference those stale designer keys (or aliases).
 - Optionally (--apply) clear Variant.designer on matches and optionally delete the stale VocabEntry rows (--delete-vocab).

Usage:
  python scripts/sync_designers_from_tokenmap.py vocab/designers_tokenmap.md
  python scripts/sync_designers_from_tokenmap.py vocab/designers_tokenmap.md --apply --delete-vocab
"""
from __future__ import annotations
import re
import ast
from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import VocabEntry, Variant

FENCE_RE = re.compile(r"^```")
ENTRY_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(\[.*\])\s*$")


def parse_tokenmap(path: Path) -> dict:
    text = path.read_text(encoding="utf8")
    lines = text.splitlines()
    inside = False
    result = {}
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
            aliases = ast.literal_eval(aliases_str)
            if not isinstance(aliases, (list, tuple)):
                aliases = [aliases]
            aliases = [str(a) for a in aliases]
        except Exception:
            aliases = []
        result[key] = aliases
    return result


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def build_tokenmap_sets(entries: dict) -> tuple[set, dict]:
    """Return (canonicals_set, alias_to_canonical_map) with normalized keys."""
    canonicals = set()
    alias_map = {}
    for canonical, aliases in entries.items():
        canonicals.add(canonical)
        # canonical itself maps to canonical
        alias_map[normalize_alias(canonical)] = canonical
        for a in aliases:
            alias_map[normalize_alias(a)] = canonical
    return canonicals, alias_map


def find_stale_vocab(session, tokenmap_keys: set) -> list[VocabEntry]:
    rows = session.query(VocabEntry).filter_by(domain="designer").all()
    return [r for r in rows if r.key not in tokenmap_keys]


def find_variants_for_vocab(session, ve: VocabEntry, alias_map: dict) -> list[Variant]:
    """Find variants that reference the given vocab entry as designer (matching key or alias)."""
    target_norm = normalize_alias(ve.key or "")
    # Also consider the aliases stored in the ve row (they may be normalized already)
    ve_alias_norms = [normalize_alias(x) for x in (ve.aliases or [])]

    matches = []
    for v in session.query(Variant).filter(Variant.designer.isnot(None)).all():
        dn = normalize_alias(str(v.designer))
        # if the variant designer normalizes to the vocab key or to any alias of this vocab entry
        if dn == target_norm or dn in ve_alias_norms:
            matches.append(v)
    return matches


def find_orphaned_variants(session, alias_map: dict) -> list[Variant]:
    """Find variants whose designer value does not map to any canonical in the tokenmap (or an alias)."""
    res = []
    for v in session.query(Variant).filter(Variant.designer.isnot(None)).all():
        dn = normalize_alias(str(v.designer))
        if dn not in alias_map:
            res.append(v)
    return res


def main():
    import argparse
    p = argparse.ArgumentParser(description="Sync designers tokenmap with DB")
    p.add_argument("tokenmap", nargs=1, help="Path to designers tokenmap file")
    p.add_argument("--apply", action="store_true", help="Apply changes (clear Variant.designer and optionally delete vocab entries)")
    p.add_argument("--delete-vocab", action="store_true", help="When --apply, also delete stale VocabEntry rows")
    args = p.parse_args()

    path = Path(args.tokenmap[0])
    if not path.exists():
        print("Tokenmap file not found:", path)
        return 2

    entries = parse_tokenmap(path)
    tokenmap_keys = set(entries.keys())
    canonicals_set, alias_map = build_tokenmap_sets(entries)

    with get_session() as session:
        stale = find_stale_vocab(session, tokenmap_keys)
        results = []
        total_variant_hits = 0
        for ve in stale:
            variants = find_variants_for_vocab(session, ve, alias_map)
            total_variant_hits += len(variants)
            results.append({
                "vocab_id": ve.id,
                "key": ve.key,
                "aliases": ve.aliases,
                "variant_count": len(variants),
                "variant_sample": [{"id": v.id, "rel_path": v.rel_path, "designer": v.designer} for v in variants[:20]]
            })

        # Also detect orphaned Variant.designer values (designer values that do not map to any tokenmap alias/canonical)
        orphaned = find_orphaned_variants(session, alias_map)
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
        # clear designers for variants referring to stale vocab entries
        for ve in stale:
            variants = find_variants_for_vocab(session, ve, alias_map)
            for v in variants:
                v.designer = None

        # clear designers for orphaned variants (designer value doesn't map to any tokenmap alias/canonical)
        for v in orphaned:
            v.designer = None

        if args.delete_vocab:
            print("Deleting stale VocabEntry rows...")
            for ve in stale:
                session.delete(ve)
        session.commit()
        print("Apply complete.")
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

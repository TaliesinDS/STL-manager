#!/usr/bin/env python3
"""
Load designers_tokenmap (MD or JSON) into the DB as VocabEntry(domain='designer').

Canonical location: scripts/20_loaders/load_designers.py
"""
from __future__ import annotations

import sys
import re
import ast
from pathlib import Path
from typing import Optional
from collections import defaultdict

# Ensure project root on sys.path for db imports regardless of CWD
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import SessionLocal
from db.models import VocabEntry, Variant

FENCE_RE = re.compile(r"^```")
ENTRY_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(\[.*\])\s*$")


def parse_tokenmap_md(path: Path):
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
        except Exception as e:
            print(f"WARN: failed to parse aliases for {key}: {e}")
            aliases = []
        result[key] = aliases
    return result


def parse_tokenmap_json(path: Path):
    try:
        import json
        data = json.loads(path.read_text(encoding='utf8'))
    except Exception as e:
        print("ERROR: failed to parse JSON:", e)
        return {}, {}
    designers = (data or {}).get('designers', {})
    aliases = {k: list((v or {}).get('aliases') or []) for k, v in designers.items()}
    meta = {k: {kk: vv for kk, vv in (v or {}).items() if kk != 'aliases'} for k, v in designers.items()}
    map_version = (data or {}).get('designers_map_version')
    return aliases, {"map_version": map_version, "per_key_meta": meta}


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def build_alias_map(entries: dict[str, list[str]]) -> dict[str, str]:
    """Return mapping of normalized alias -> canonical key from provided entries."""
    alias_map: dict[str, str] = {}
    for canonical, aliases in (entries or {}).items():
        alias_map[normalize_alias(canonical)] = canonical
        for a in aliases or []:
            alias_map[normalize_alias(a)] = canonical
    return alias_map


def reconcile_renamed_designers(session, entries: dict[str, list[str]], update_variants: bool = False) -> dict:
    """Detect legacy designer keys in DB that now resolve to a different canonical in the tokenmap and reconcile.

    Steps per legacy key:
    - Ensure target canonical VocabEntry exists
    - Merge aliases (authoritative from tokenmap + DB + old key)
    - Optionally update Variant.designer values to target canonical
    - Delete legacy VocabEntry
    Returns a summary dict with counts and samples.
    """
    alias_map = build_alias_map(entries)

    def resolve_target_for_db_row(ve: VocabEntry) -> str | None:
        # Prefer mapping by exact key, else by any of its aliases
        key_norm = normalize_alias(ve.key)
        if key_norm in alias_map:
            return alias_map[key_norm]
        for a in (ve.aliases or []):
            na = normalize_alias(a)
            if na in alias_map:
                return alias_map[na]
        return None

    db_rows: list[VocabEntry] = session.query(VocabEntry).filter_by(domain="designer").all()
    rename_actions: list[tuple[str, str]] = []
    for ve in db_rows:
        tgt = resolve_target_for_db_row(ve)
        if not tgt:
            continue
        if tgt != ve.key:
            rename_actions.append((ve.key, tgt))

    # De-duplicate and avoid cycles
    unique_actions = []
    seen = set()
    for old, new in rename_actions:
        if old == new:
            continue
        key = (old, new)
        if key in seen:
            continue
        seen.add(key)
        unique_actions.append((old, new))

    updated_variants = 0
    merged_aliases_for = {}
    deleted_vocab = []

    for old_key, new_key in unique_actions:
        legacy = session.query(VocabEntry).filter_by(domain="designer", key=old_key).one_or_none()
        target = session.query(VocabEntry).filter_by(domain="designer", key=new_key).one_or_none()
        if not target:
            # Create target if missing
            target = VocabEntry(domain="designer", key=new_key, aliases=[], meta={})
            session.add(target)
            session.flush()

        # Merge aliases: authoritative from file
        file_aliases = list((entries.get(new_key) or []))
        merged = []
        def _extend(vals):
            nonlocal merged
            for v in vals or []:
                v = (v or "").strip()
                if not v:
                    continue
                if v not in merged:
                    merged.append(v)

        _extend(file_aliases)
        _extend(target.aliases)
        if legacy:
            _extend(legacy.aliases)
            # Keep old canonical as an alias for back-compat
            if old_key not in merged:
                merged.append(old_key)

        target.aliases = merged

        # Meta: track previous_keys
        meta = dict(target.meta or {})
        prev = set(meta.get("previous_keys", []))
        prev.add(old_key)
        meta["previous_keys"] = sorted(prev)
        target.meta = meta

        # Optionally update variants to point to new canonical
        if update_variants and legacy:
            legacy_norms = {normalize_alias(legacy.key)} | {normalize_alias(a) for a in (legacy.aliases or [])}
            # Iterate all designer-tagged variants and normalize in Python (DB may contain various casings)
            for v in session.query(Variant).filter(Variant.designer.isnot(None)).all():
                dn = normalize_alias(str(v.designer))
                if dn in legacy_norms:
                    v.designer = new_key
                    updated_variants += 1

        if legacy:
            deleted_vocab.append(old_key)
            session.delete(legacy)

        merged_aliases_for[old_key] = {"into": new_key, "aliases": merged}

    if unique_actions or updated_variants or deleted_vocab:
        session.commit()

    return {
        "rename_actions": unique_actions,
        "updated_variants": updated_variants,
        "deleted_vocab": deleted_vocab,
        "merged_aliases": merged_aliases_for,
    }


def detect_conflicts(entries: dict, session):
    """Detect alias collisions within the provided entries and against existing DB rows.
    Returns a tuple (infile_conflicts, db_conflicts) where each is a dict alias->set(canonicals).
    """
    infile_map = defaultdict(set)
    for canonical, aliases in entries.items():
        # include canonical itself as an alias for detection
        infile_map[normalize_alias(canonical)].add(canonical)
        for a in aliases:
            infile_map[normalize_alias(a)].add(canonical)

    infile_conflicts = {a: cs for a, cs in infile_map.items() if len(cs) > 1}

    # build existing alias map from DB
    db_rows = session.query(VocabEntry).filter_by(domain="designer").all()
    db_map = defaultdict(set)
    for r in db_rows:
        db_map[normalize_alias(r.key)].add(r.key)
        for a in (r.aliases or []):
            db_map[normalize_alias(a)].add(r.key)

    # conflicts where alias maps to multiple canonicals across file+db
    combined = defaultdict(set)
    for a, cs in infile_map.items():
        combined[a].update(cs)
    for a, cs in db_map.items():
        combined[a].update(cs)

    db_conflicts = {a: cs for a, cs in combined.items() if len(cs) > 1}
    return infile_conflicts, db_conflicts


def sniff_map_version_md(path: Path):
    text = path.read_text(encoding="utf8")
    m = re.search(r"designers_map_version\s*:\s*(\d+)", text)
    if m:
        return int(m.group(1))
    return None


def upsert_vocab_entries(session, entries: dict, source_file: str, map_version=None, extra_meta_per_key: Optional[dict] = None):
    # detect conflicts and annotate meta
    infile_conflicts, db_conflicts = detect_conflicts(entries, session)
    if infile_conflicts:
        print("Found in-file alias conflicts (alias -> canonicals):")
        for a, cs in infile_conflicts.items():
            print(f"  {a} -> {sorted(list(cs))}")
    if db_conflicts:
        print("Found conflicts with existing DB entries (alias -> canonicals):")
        for a, cs in db_conflicts.items():
            print(f"  {a} -> {sorted(list(cs))}")

    for canonical, aliases in entries.items():
        normalized_aliases = [a.strip() for a in aliases if a and a.strip()]
        meta = {"source_file": str(source_file)}
        if map_version is not None:
            meta["map_version"] = map_version
        # merge extra meta (e.g., intended_use_bucket from JSON)
        if extra_meta_per_key and canonical in extra_meta_per_key:
            meta.update({k: v for k, v in (extra_meta_per_key.get(canonical) or {}).items() if v is not None})
        # attach conflict hints for this canonical if any of its aliases are conflicted
        conflicts_for_key = []
        for a in normalized_aliases + [canonical]:
            na = normalize_alias(a)
            if na in db_conflicts or na in infile_conflicts:
                conflicts_for_key.append(na)
        if conflicts_for_key:
            meta["conflicts_with"] = list(sorted(set(conflicts_for_key)))

        ve = session.query(VocabEntry).filter_by(domain="designer", key=canonical).one_or_none()
        if ve:
            ve.aliases = normalized_aliases
            ve.meta = meta
        else:
            ve = VocabEntry(domain="designer", key=canonical, aliases=normalized_aliases, meta=meta)
            session.add(ve)
    session.commit()


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Load designers tokenmap into DB (dry-run by default)")
    p.add_argument("path", help="Path to designers_tokenmap.(md|json)")
    p.add_argument("--commit", action="store_true", help="Apply changes to the DB (default: dry-run)")
    p.add_argument("--reconcile-renamed", action="store_true", help="When --commit, reconcile legacy designer keys to new canonical names from tokenmap")
    p.add_argument("--update-variants", action="store_true", help="When reconciling, also update Variant.designer to the new canonical name")
    args = p.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print("File not found:", path)
        return 2
    extra_meta_per_key = None
    map_version = None
    if path.suffix.lower() == '.json':
        entries, meta = parse_tokenmap_json(path)
        map_version = (meta or {}).get('map_version')
        extra_meta_per_key = (meta or {}).get('per_key_meta')
    else:
        entries = parse_tokenmap_md(path)
        map_version = sniff_map_version_md(path)

    session = SessionLocal()
    try:
        upsert_vocab_entries(session, entries, source_file=path.name, map_version=map_version, extra_meta_per_key=extra_meta_per_key)
        print(f"Upserted {len(entries)} designer vocab entries (map_version={map_version})")
        if args.commit and args.reconcile_renamed:
            summary = reconcile_renamed_designers(session, entries, update_variants=args.update_variants)
            print("Reconcile summary:")
            print(f"  renames: {len(summary.get('rename_actions', []))}")
            print(f"  updated_variants: {summary.get('updated_variants', 0)}")
            if summary.get("rename_actions"):
                sample = summary["rename_actions"][:10]
                print(f"  sample renames: {sample}")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

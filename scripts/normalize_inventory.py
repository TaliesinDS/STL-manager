#!/usr/bin/env python3
"""Normalize inventory entries (variant + file rows) by tokenizing paths and
applying conservative tokenmap rules to populate designer, franchise,
lineage_family, variant axes, scale and simple flags.

Safe by default: runs in dry-run mode and prints a summary of proposed updates.
Use `--apply` to write changes back to the DB. Respects existing non-null fields
and will not overwrite them unless `--force` is used.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
import json
import re
from typing import Iterable

# Ensure project root is on sys.path so `from db...` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant, File, VocabEntry

# Reuse tokenizer and tokenmap loader from quick_scan to keep behavior consistent
from scripts.quick_scan import (
    tokenize,
    load_tokenmap,
    load_external_designers,
    classify_token,
    SCALE_RATIO_RE,
    SCALE_MM_RE,
)

# Lightweight local rule seeds (kept conservative and aligned with tokenmap.md)
ROLE_POSITIVE = {"hero", "rogue", "wizard", "fighter", "paladin", "cleric", "barbarian", "ranger", "sorcerer", "warlock", "bard"}
ROLE_NEGATIVE = {"horde", "swarm", "minion", "mob", "unit", "regiment"}
NSFW_STRONG = {"nude", "naked", "topless", "nsfw", "lewd", "futa"}
NSFW_WEAK = {"sexy", "pinup", "pin-up", "lingerie"}

SEGMENTATION_SPLIT = {"split", "parts", "multi-part", "multi_part", "part"}
SEGMENTATION_MERGED = {"onepiece", "one_piece", "merged", "solidpiece", "uncut"}
INTERNAL_HOLLOW = {"hollow", "hollowed"}
INTERNAL_SOLID = {"solid"}
SUPPORT_PRESUPPORTED = {"presupported", "pre-supported", "pre_supported"}
SUPPORT_SUPPORTED = {"supported"}
SUPPORT_UNSUPPORTED = {"unsupported", "no_supports", "clean"}
PART_BUST = {"bust"}
PART_BASE = {"base_pack", "bases_only", "base_set"}
PART_ACCESSORY = {"bits", "bitz", "accessories"}
# Tokens that suggest a tabletop miniature/terrain context. When present,
# we deliberately avoid assigning a `franchise` automatically because most
# tabletop hobby STLs (scenery, terrain, independent miniatures) are not
# franchise-owned in this domain model.
TABLETOP_HINTS = {
    "mini", "miniature", "miniatures", "terrain", "scenery", "base",
    "bases", "bust", "miniaturesupports", "support", "church", "decor",
    "mm", "scale", "mini_supports", "squad"
}


def build_designer_alias_map(session) -> dict[str, str]:
    """Return alias->canonical mapping from VocabEntry(domain='designer')."""
    rows = session.query(VocabEntry).filter_by(domain="designer").all()
    amap: dict[str, str] = {}
    for r in rows:
        key = r.key
        amap[key.lower()] = key
        for a in (r.aliases or []):
            amap[a.strip().lower()] = key
    return amap


def build_franchise_alias_map(session) -> dict[str, str]:
    """Return alias->canonical mapping from VocabEntry(domain='franchise')."""
    rows = session.query(VocabEntry).filter_by(domain="franchise").all()
    fmap: dict[str, str] = {}
    for r in rows:
        key = r.key
        fmap[key.lower()] = key
        for a in (r.aliases or []):
            fmap[a.strip().lower()] = key
    return fmap


def build_character_alias_map(session) -> dict[str, str]:
    """Return alias->canonical mapping from VocabEntry(domain='character')."""
    rows = session.query(VocabEntry).filter_by(domain="character").all()
    cmap: dict[str, str] = {}
    for r in rows:
        key = r.key
        cmap[key.lower()] = key
        for a in (r.aliases or []):
            cmap[a.strip().lower()] = key
    return cmap


def tokens_from_variant(session, variant: Variant) -> list[str]:
    # Build a conservative token set for the variant. To avoid unrelated
    # "loose" files (previews, archives, other top-level items) contaminating
    # a variant's tokens, we: (1) prefer tokens derived from the variant's
    # rel_path and filename, and (2) only include tokens from associated
    # files when there's contextual evidence they belong to the same variant
    # (shared tokens, matching filename or rel_path prefix). We also skip
    # common non-model file extensions (images, archives, etc.).
    toks: list[str] = []
    base_tokens: list[str] = []
    # tokens from rel_path
    try:
        base_tokens += tokenize(Path(variant.rel_path or ""))
    except Exception:
        pass
    # tokens from variant filename if present
    if variant.filename:
        try:
            base_tokens += tokenize(Path(variant.filename))
        except Exception:
            pass

    # seed output with base tokens (deduped as we go)
    seen = set()
    out: list[str] = []
    for t in base_tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)

    # Only include tokens from associated files when they reasonably belong
    # to the same variant. Skip common preview/archive extensions.
    MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb'}
    for f in getattr(variant, "files", []):
        fname = (f.filename or "")
        frel = (f.rel_path or "")
        # decide which path to tokenize for the file
        token_source = fname or frel
        if not token_source:
            continue
        p = Path(token_source)
        ext = p.suffix.lower()
        # Skip obvious non-model files (previews, archives, text, etc.)
        if ext and ext not in MODEL_EXTS:
            continue
        try:
            file_tokens = tokenize(Path(token_source))
        except Exception:
            continue

        # Heuristics to decide whether this file should contribute tokens:
        # - file path starts with the variant rel_path (strong signal), or
        # - file name contains the variant filename, or
        # - the file shares at least one token with the variant base tokens.
        include = False
        if variant.rel_path and frel:
            try:
                if Path(frel).as_posix().lower().startswith(Path(variant.rel_path or "").as_posix().lower()):
                    include = True
            except Exception:
                pass
        if not include and variant.filename and fname:
            if variant.filename.lower() in fname.lower():
                include = True
        if not include and base_tokens:
            if set(file_tokens) & set(base_tokens):
                include = True
        # Fallback: if the variant had no base tokens (loose/empty rel_path),
        # allow file tokens (better to have tokens than none in that case)
        if not include and not base_tokens:
            include = True

        if not include:
            continue

        for t in file_tokens:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)

    return out


def classify_tokens(tokens: Iterable[str], designer_map: dict[str, str], franchise_map: dict[str, str] | None = None, character_map: dict[str, str] | None = None):
    """Return a dictionary of inferred fields and residual tokens."""
    inferred = {
        "designer": None,
        "franchise": None,
        "lineage_family": None,
        "faction_hint": None,
        "segmentation": None,
        "internal_volume": None,
        "support_state": None,
        "part_pack_type": None,
        "has_bust_variant": False,
        "scale_ratio_den": None,
        "height_mm": None,
        "pc_candidate_flag": False,
        "content_flag": None,
        "residual_tokens": [],
        "character_hint": None,
        "character_name": None,
        "normalization_warnings": [],
    }

    # Ensure we have a list for co-occurrence checks
    token_list = list(tokens)
    # Conservative tabletop detection: require tabletop hint tokens AND no
    # stronger evidence tokens (designer/franchise/character). This avoids
    # treating artist/collection labels like "minis" or store names as
    # tabletop context when explicit franchise/character/designer tokens are
    # present.
    has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
    has_stronger_context = False
    if designer_map and any(t in designer_map for t in token_list):
        has_stronger_context = True
    if franchise_map and any(t in franchise_map for t in token_list):
        has_stronger_context = True
    if character_map and any(t in character_map for t in token_list):
        has_stronger_context = True
    is_tabletop = has_tabletop_hint and not has_stronger_context
    for tok in token_list:
        dom = classify_token(tok)
        # Designer: prefer canonical mapping via DB alias map
        if not inferred["designer"] and tok in designer_map:
            inferred["designer"] = designer_map[tok]
            continue
        # Direct domain matches from tokenmap small parse
        if dom == "lineage_family" and not inferred["lineage_family"]:
            inferred["lineage_family"] = tok
            continue
    # Faction-like tokens are recorded as a faction hint. Franchise is a
    # separate higher-level concept (e.g., 'Marvel', 'Naruto') and should
    # not be stored in faction fields. When a token maps to a franchise
    # alias, set `franchise` when strong enough; otherwise store the token
    # in `franchise_hints` (not `faction_hint`).
        if dom == "faction_hint":
            # If this token maps to a known franchise alias, decide whether
            # it's strong enough to set `franchise`. Two-letter tokens (e.g.,
            # 'sw', 'gw') are weak on their own and require supporting
            # context: another franchise alias present, or a character/unit
            # alias present. Otherwise record only a hint and warning.
            is_franchise_alias = franchise_map and tok in franchise_map
            if is_franchise_alias and not inferred.get("franchise"):
                # Strength checks
                alias_count = sum(1 for c in token_list if franchise_map and c in franchise_map)
                has_character_hint = character_map and any(c in character_map for c in token_list)
                strong = len(tok) > 2 or alias_count > 1 or has_character_hint
                # If this looks like a tabletop item, do NOT auto-assign a
                # franchise: tabletop STLs (indie minis, terrain, etc.) should
                # remain franchise-less in this Phase-1 model. Record a
                # normalization warning and skip franchise assignment.
                if is_tabletop:
                    inferred.setdefault("normalization_warnings", [])
                    if "tabletop_no_franchise" not in inferred["normalization_warnings"]:
                        inferred["normalization_warnings"].append("tabletop_no_franchise")
                    # record hint but avoid assigning franchise
                    if not inferred.get("faction_hint"):
                        inferred["faction_hint"] = tok
                    continue
                if strong:
                    inferred["franchise"] = franchise_map[tok]
                    inferred["faction_hint"] = tok
                    continue
            # Otherwise record franchise hint only and warn (no automatic franchise)
            inferred.setdefault("franchise_hints", [])
            if tok not in inferred["franchise_hints"]:
                inferred["franchise_hints"].append(tok)
            inferred.setdefault("normalization_warnings", [])
            if "faction_without_system" not in inferred["normalization_warnings"]:
                inferred["normalization_warnings"].append("faction_without_system")
            continue
        if dom == "variant_axis":
            if tok in SEGMENTATION_SPLIT:
                inferred["segmentation"] = "split"
                continue
            if tok in SEGMENTATION_MERGED:
                inferred["segmentation"] = "merged"
                continue
            if tok in INTERNAL_HOLLOW:
                inferred["internal_volume"] = "hollowed"
                continue
            if tok in INTERNAL_SOLID:
                inferred["internal_volume"] = "solid"
                continue
            if tok in SUPPORT_PRESUPPORTED:
                inferred["support_state"] = "presupported"
                continue
            if tok in SUPPORT_SUPPORTED:
                inferred["support_state"] = "supported"
                continue
            if tok in SUPPORT_UNSUPPORTED:
                inferred["support_state"] = "unsupported"
                continue
            if tok in PART_BUST:
                inferred["has_bust_variant"] = True
                inferred["part_pack_type"] = inferred.get("part_pack_type") or "bust_only"
                continue
            if tok in PART_BASE:
                inferred["part_pack_type"] = inferred.get("part_pack_type") or "base_only"
                continue
            if tok in PART_ACCESSORY:
                inferred["part_pack_type"] = inferred.get("part_pack_type") or "accessory"
                continue
        # Character / codex unit hints: record non-destructively unless
        # there is stronger contextual resolution (game_system, franchise)
        # later. We add a warning so these can be reviewed before committing
        # a `codex_unit_name` value.
        if franchise_map and tok in franchise_map:
            # franchise_map handled earlier; skip here
            pass
        # Character/unit alias match: non-destructively record the hint and
        # canonical name for review. We do not auto-assign codex_unit_name
        # to persistent fields unless later phases confirm game_system + faction.
        if character_map and not inferred.get("character_hint") and tok in character_map:
            # Record a character hint and canonical character name for review.
            inferred["character_hint"] = tok
            inferred["character_name"] = character_map[tok]
            inferred.setdefault("normalization_warnings", [])
            if "character_without_context" not in inferred["normalization_warnings"]:
                inferred["normalization_warnings"].append("character_without_context")
            continue
        # Scale detection
        m = SCALE_RATIO_RE.match(tok)
        if m and not inferred["scale_ratio_den"]:
            try:
                den = int(m.group(1))
                inferred["scale_ratio_den"] = den
            except Exception:
                pass
            continue
        m2 = SCALE_MM_RE.match(tok)
        if m2 and not inferred["height_mm"]:
            try:
                mm = int(m2.group(1))
                inferred["height_mm"] = mm
            except Exception:
                pass
            continue
        # Role heuristics for pc candidate
        if tok in ROLE_POSITIVE and tok not in ROLE_NEGATIVE:
            inferred["pc_candidate_flag"] = True
            continue
        if tok in NSFW_STRONG:
            inferred["content_flag"] = "nsfw"
            continue
        if tok in NSFW_WEAK and inferred.get("content_flag") is None:
            inferred["content_flag"] = "nsfw_weak"
            continue
        # If not matched above and not a stopword/classified, add to residuals
        if dom is None:
            inferred["residual_tokens"].append(tok)

    return inferred


def apply_updates_to_variant(variant: Variant, inferred: dict, session, force: bool = False) -> dict:
    """Apply inferred fields to variant object in memory; return dict of changed fields."""
    changed = {}
    # conservative write: only populate if None or force=True
    def set_if_empty(field, value):
        cur = getattr(variant, field)
        # Only set when current value is empty (None/empty string/empty list/dict) or when force=True
        # And only if the proposed value is non-empty (not None/list/dict)
        if (cur in (None, "", [], {}) or force) and value not in (None, [], {}):
            setattr(variant, field, value)
            changed[field] = value

    set_if_empty("raw_path_tokens", inferred.get("residual_tokens") or [])
    set_if_empty("residual_tokens", inferred.get("residual_tokens") or [])
    set_if_empty("token_version", inferred.get("token_version"))
    set_if_empty("designer", inferred.get("designer"))
    set_if_empty("designer_confidence", "high" if inferred.get("designer") else None)
    set_if_empty("franchise", inferred.get("franchise"))
    set_if_empty("lineage_family", inferred.get("lineage_family"))
    # Do not set faction_general from franchise evidence; only set when a true faction is detected elsewhere
    # set_if_empty("faction_general", inferred.get("faction_hint"))
    # But do record franchise hints separately for review
    if inferred.get("franchise_hints"):
        cur_hints = variant.franchise_hints or []
        merged = list(dict.fromkeys(cur_hints + inferred["franchise_hints"]))
        if merged != cur_hints:
            variant.franchise_hints = merged
            changed["franchise_hints"] = merged
    # Populate character fields (name + alias list) conservatively.
    if inferred.get("character_name"):
        set_if_empty("character_name", inferred.get("character_name"))
        # if we have a character hint token, include it in aliases
        hint = inferred.get("character_hint")
        if hint:
            set_if_empty("character_aliases", [hint])
    set_if_empty("segmentation", inferred.get("segmentation"))
    set_if_empty("internal_volume", inferred.get("internal_volume"))
    set_if_empty("support_state", inferred.get("support_state"))
    set_if_empty("part_pack_type", inferred.get("part_pack_type"))
    set_if_empty("has_bust_variant", inferred.get("has_bust_variant"))
    set_if_empty("scale_ratio_den", inferred.get("scale_ratio_den"))
    set_if_empty("height_mm", inferred.get("height_mm"))
    set_if_empty("pc_candidate_flag", inferred.get("pc_candidate_flag"))
    set_if_empty("content_flag", inferred.get("content_flag"))
    # normalization warnings if any
    if inferred.get("normalization_warnings"):
        curw = variant.normalization_warnings or []
        neww = list(curw)
        for w in inferred.get("normalization_warnings"):
            if w not in neww:
                neww.append(w)
        if neww != curw:
            variant.normalization_warnings = neww
            changed["normalization_warnings"] = neww

    return changed


def process_variants(batch_size: int, apply: bool, only_missing: bool, force: bool):
    root = Path(__file__).resolve().parent.parent
    # try to load tokenmap to set token version & domain sets
    tm_path = root / 'vocab' / 'tokenmap.md'
    if tm_path.exists():
        stats = load_tokenmap(tm_path)
        token_map_version = getattr(sys.modules.get('scripts.quick_scan'), 'TOKENMAP_VERSION', None)
    else:
        token_map_version = None

    with get_session() as session:
        designer_map = build_designer_alias_map(session)
        franchise_map = build_franchise_alias_map(session)
        character_map = build_character_alias_map(session)

        # Build base query: only variants with at least one file (simple heuristic)
        q = session.query(Variant).join(File).distinct()
        if only_missing:
            q = q.filter(Variant.token_version.is_(None))

        total = q.count()
        print(f"Found {total} variants to examine (only_missing={only_missing}).")
        offset = 0
        proposed_updates = []
        while True:
            rows = q.limit(batch_size).offset(offset).all()
            if not rows:
                break
            for v in rows:
                tokens = tokens_from_variant(session, v)
                inferred = classify_tokens(tokens, designer_map, franchise_map, character_map)
                inferred["token_version"] = token_map_version
                changed = apply_updates_to_variant(v, inferred, session, force=force)
                if changed:
                    proposed_updates.append({"variant_id": v.id, "rel_path": v.rel_path, "changes": changed})
            offset += batch_size
        print(f"Proposed updates for {len(proposed_updates)} variants (dry-run={not apply}).")
        # Print a small sample
        for s in proposed_updates[:10]:
            print(json.dumps(s, indent=2))
        if apply and proposed_updates:
            # commit in batches to limit transaction size
            print("Applying updates to DB...")
            offset = 0
            while True:
                rows = q.limit(batch_size).offset(offset).all()
                if not rows: break
                any_changed = False
                for v in rows:
                    tokens = tokens_from_variant(session, v)
                    inferred = classify_tokens(tokens, designer_map, franchise_map, character_map)
                    inferred["token_version"] = token_map_version
                    changed = apply_updates_to_variant(v, inferred, session, force=force)
                    if changed:
                        any_changed = True
                if any_changed:
                    session.commit()
                offset += batch_size
            print("Apply complete.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize Variant+File metadata from path tokens")
    ap.add_argument('--batch', type=int, default=200, help='Variants per DB batch')
    ap.add_argument('--apply', action='store_true', help='Write inferred metadata to DB (default: dry-run)')
    ap.add_argument('--only-missing', action='store_true', help='Only process variants lacking token_version')
    ap.add_argument('--force', action='store_true', help='Overwrite existing fields (use with care)')
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    process_variants(batch_size=args.batch, apply=args.apply, only_missing=args.only_missing, force=args.force)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

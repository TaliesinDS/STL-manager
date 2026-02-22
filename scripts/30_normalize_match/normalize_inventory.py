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
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Dict, List, Optional

# scripts/30_normalize_match/ -> scripts -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

from db.models import Character, File, Variant, VocabEntry
from db.session import DB_URL, get_session
from scripts.lib.alias_rules import (
    AMBIGUOUS_ALIASES,
)
from scripts.lib.alias_rules import (
    is_short_or_numeric as _short_or_numeric,
)

# Reuse tokenizer and tokenmap loader from quick_scan to keep behavior consistent
from scripts.quick_scan import (
    ALLOWED_DENOMS,
    SCALE_MM_RE,
    SCALE_RATIO_RE,
    SPLIT_CHARS,
    classify_token,
    load_tokenmap,
    tokenize,
)


def _detect_token_locale(tokens: list[str]) -> str | None:
    if not tokens:
        return None
    if all(all(ord(c) < 128 for c in t) for t in tokens):
        return 'en'
    def has_range(t: str, start: int, end: int) -> bool:
        return any(start <= ord(c) <= end for c in t)
    any_hira = any(has_range(t, 0x3040, 0x309F) for t in tokens)
    any_kata = any(has_range(t, 0x30A0, 0x30FF) for t in tokens)
    if any_hira or any_kata:
        return 'ja'
    any_cjk = any(has_range(t, 0x4E00, 0x9FFF) for t in tokens)
    if any_cjk:
        return 'zh'
    return None

def load_designers_json(path: Path) -> tuple[dict, list[tuple[list[str], str]], dict[str, str]]:
    """Load designers_tokenmap.json if present.
    Returns:
      - alias_map: alias->canonical
      - phrases: list of (token_sequence, canonical)
      - specialization: canonical->intended_use_bucket (if provided)
    """
    try:
        import json as _json
        data = _json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}, [], {}
    designers = (data or {}).get('designers', {})
    alias_map: dict[str, str] = {}
    phrases: list[tuple[list[str], str]] = []
    specialization: dict[str, str] = {}
    for canon, meta in designers.items():
        aliases = [a for a in (meta or {}).get('aliases', []) if a]
        for a in aliases + [canon]:
            alias_map[a.strip().lower()] = canon
            toks = [t for t in SPLIT_CHARS.split(a.lower()) if t]
            if len(toks) >= 2:
                phrases.append((toks, canon))
        if (meta or {}).get('intended_use_bucket'):
            specialization[canon] = meta['intended_use_bucket']
    return alias_map, phrases, specialization

def load_franchise_preferences(path: Path) -> tuple[list[tuple[list[str], str]], dict[str, str]]:
    """Load franchise_preferences.json if present.
    Returns:
      - franchise_phrases: list of (token_sequence, canonical_franchise)
      - default_bucket: canonical_franchise -> default intended_use_bucket
    """
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return [], {}
    franchises = (data or {}).get('franchises', {})
    franchise_phrases: list[tuple[list[str], str]] = []
    default_bucket: dict[str, str] = {}
    for canon, meta in franchises.items():
        aliases = [a for a in (meta or {}).get('aliases', []) if a]
        for a in aliases + [canon]:
            toks = [t for t in SPLIT_CHARS.split(a.lower()) if t]
            if toks:
                franchise_phrases.append((toks, canon))
        if (meta or {}).get('default_intended_use_bucket'):
            default_bucket[canon] = meta['default_intended_use_bucket']
    # Prefer longer phrases first during matching
    franchise_phrases.sort(key=lambda pc: -len(pc[0]))
    return franchise_phrases, default_bucket

# Lightweight local rule seeds (kept conservative and aligned with tokenmap.md)
ROLE_POSITIVE = {"hero", "rogue", "wizard", "fighter", "paladin", "cleric", "barbarian", "ranger", "sorcerer", "warlock", "bard"}
ROLE_NEGATIVE = {"horde", "swarm", "minion", "mob", "unit", "regiment"}
NSFW_STRONG = {"nude", "naked", "topless", "nsfw", "lewd", "futa"}
# Include common English and select CJK tokens that imply suggestive content
NSFW_WEAK = {"sexy", "pinup", "pin-up", "lingerie", "瑟瑟妹子", "瑟瑟"}
# Some tokens are sources/channels (e.g., Telegram groups), not designers; never assign them
DESIGNER_IGNORE = {"moxomor"}

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


# Context heuristics for lineage suppression
ACTION_VERBS = {"kill", "killing", "slay", "slaying", "vs", "versus", "against", "defeating", "beating", "revenge"}
SPACE_MARINE_HINTS = {"primaris", "astartes", "adeptus", "templar", "templars", "black", "black_templar", "black_templars", "emperor", "champion", "emperor's", "purity", "seal", "seals", "purity_seal", "purity_seals", "space", "marine", "marines", "space_marine", "space_marines", "bayard", "bayards", "bayard's"}
ORK_SUBJECT_HINTS = {"nob", "warboss", "boy", "boys", "slugga", "choppa", "grot", "grots", "gretchin"}
ORX_EQUIV = {"ork", "orc", "orcs"}
RAT_STRONG = {"rat","ratkin","ratmen","ratman","ratogre","ratogres","rodent","rodents","vermin","vermins"}
RAT_WEAK = {"gnaw","gnawnine","fang","fangs","claw","claws","scratch","scratchfang","whisker","whiskers","tail","tails","screecher","swarm"}
UNDEAD_HINTS = {"undead","vampire","vampires","vampiric","wight","wights","skeleton","skeletons","tomb","tombshade","necropolis","damnation","ark"}

# --- Lightweight parsers for selected tokenmap.md domains (conservative) ---
_TOKENLIST_RE = re.compile(r"^\s*([a-z0-9_]+):\s*\[(.*?)\]\s*$", re.IGNORECASE)

def _split_list(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.split(','):
        part = part.strip().strip("'\"")
        if part:
            out.append(part)
    return out

def parse_tokenmap_intended_use(path: Path) -> Optional[Dict[str, set]]:
    """Parse intended_use section from tokenmap.md returning {bucket: set(tokens)} or None."""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None
    in_section = False
    buckets: Dict[str, set] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if in_section:
                # allow blank lines inside code blocks; continue until code fence or next header
                pass
        if s.startswith('intended_use:'):
            in_section = True
            continue
        if in_section:
            m = _TOKENLIST_RE.match(line)
            if m:
                key, raw = m.groups()
                toks = set(_split_list(raw))
                buckets[key] = toks
                continue
            # Heuristic stop: next top-level header or section marker
            if s.startswith('## ') or s.startswith('---') or s.startswith('```'):
                if buckets:
                    break
    return buckets or None

def parse_tokenmap_general_faction(path: Path) -> Optional[Dict[str, set]]:
    """Parse general_faction section returning {bucket: set(tokens)} or None."""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None
    in_section = False
    buckets: Dict[str, set] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if in_section:
                pass
        if s.startswith('general_faction:'):
            in_section = True
            continue
        if in_section:
            m = _TOKENLIST_RE.match(line)
            if m:
                key, raw = m.groups()
                toks = set(_split_list(raw))
                buckets[key] = toks
                continue
            if s.startswith('## ') or s.startswith('---') or s.startswith('```'):
                if buckets:
                    break
    return buckets or None


def parse_designers_aliases(path: Path) -> list[tuple[list[str], str]]:
    """Parse designers alias list from designers_tokenmap.md and return phrases as
    a list of (token_sequence, canonical_key). Token sequence is split using the
    same separators as the tokenizer (spaces/underscore/hyphen). Single-token
    aliases are ignored here because they are already handled by per-token
    classify_token via global designer alias sets loaded elsewhere.
    """
    phrases: list[tuple[list[str], str]] = []
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return phrases
    in_designers = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if in_designers:
                in_designers = False
            continue
        if s.startswith('designers:'):
            in_designers = True
            continue
        m = _TOKENLIST_RE.match(line)
        if m and in_designers:
            canonical, raw = m.groups()
            # split raw alias list as in quick_scan
            alias_list = []
            for part in raw.split(','):
                part = part.strip().strip("'\"")
                if part:
                    alias_list.append(part)
            for alias in alias_list:
                # split alias to tokens using SPLIT_CHARS; lowercased
                toks = [t for t in SPLIT_CHARS.split(alias.lower()) if t]
                if len(toks) >= 2:
                    phrases.append((toks, canonical))
    return phrases


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
    """Return alias->canonical mapping from the Character table.

    Canonical is the Character.name (snake_case). All aliases from the row's
    `aliases` JSON array are mapped to that canonical. The canonical key itself
    is also mapped so direct mentions like 'nami_one_piece' hit as well.
    """
    rows = session.query(Character).all()
    cmap: dict[str, str] = {}
    for r in rows:
        key = (r.name or "").strip()
        if not key:
            continue
        cmap[key.lower()] = key
        for a in (r.aliases or []):
            if not a:
                continue
            cmap[str(a).strip().lower()] = key
    return cmap


def tokens_from_variant(session, variant: Variant) -> list[str]:
    # Build a conservative token set for the variant. To avoid unrelated
    # "loose" files (previews, archives, other top-level items) contaminating
    # a variant's tokens, we: (1) prefer tokens derived from the variant's
    # rel_path and filename, and (2) only include tokens from associated
    # files when there's contextual evidence they belong to the same variant
    # (shared tokens, matching filename or rel_path prefix). We also skip
    # common non-model file extensions (images, archives, etc.).
    _toks: list[str] = []
    base_tokens: list[str] = []
    # tokens from rel_path
    try:
        rp = Path(variant.rel_path or "")
        # Ignore tokens from macOS metadata trees entirely
        if "__macosx" not in {part.lower() for part in rp.parts}:
            base_tokens += tokenize(rp)
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

    # Guard: if this variant is the top-level container (e.g., 'sample_store'),
    # do not include tokens from associated files. Historically, loose files
    # under the root were lumped into a single variant; we treat the container
    # as non-variant and avoid aggregating its child file tokens.
    if (variant.rel_path or '').strip().lower() == 'sample_store':
        return out

    # Only include tokens from associated files when they reasonably belong
    # to the same variant. Skip common preview/archive extensions.
    MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb', '.ztl', '.step', '.stp', '.lys', '.chitubox', '.ctb'}
    for f in getattr(variant, "files", []):
        fname = (f.filename or "")
        frel = (f.rel_path or "")
        # Skip any files under __MACOSX
        try:
            if frel and "__macosx" in {part.lower() for part in Path(frel).parts}:
                continue
        except Exception:
            pass
        # decide which path to tokenize for the file
        token_source = fname or frel
        if not token_source:
            continue
        p = Path(token_source)
        ext = p.suffix.lower()
        # Skip obvious non-model files (previews, archives, text, etc.)
        if ext and ext not in MODEL_EXTS:
            continue
        # Skip macOS sidecar files
        try:
            if p.name == ".DS_Store" or p.name.startswith("._"):
                continue
        except Exception:
            pass
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

    # Inject synthetic scale tokens from raw path strings so that downstream
    # classifiers can detect scale even when single-digit tokens like '1' or '6'
    # are dropped by the tokenizer (TOKEN_MIN_LEN=2).
    try:
        rel_raw = (variant.rel_path or "")
    except Exception:
        rel_raw = ""
    try:
        fname_raw = (variant.filename or "")
    except Exception:
        fname_raw = ""
    full_raw = f"{rel_raw}\n{fname_raw}".lower()
    def _maybe_add(tok: str):
        if tok and tok not in seen:
            seen.add(tok)
            out.append(tok)
    # Ratio forms that mention 'scale' near the number; require 'scale' to avoid false positives
    for m in re.finditer(r"1[\s\-_:/*]*([0-9]{1,3})\s*scale", full_raw):
        try:
            den = int(m.group(1))
        except Exception:
            den = None
        if den and (den in ALLOWED_DENOMS or den in {5, 8, 11}):
            _maybe_add(f"{den}scale")
            break
    if 'scale' in full_raw and not any(t.endswith('scale') for t in out):
        # 'scale 10' or 'scale 1 10'
        m2 = re.search(r"scale[\s\-_:/*]*1?[\s\-_:/*]*([0-9]{2,3})\b", full_raw)
        if m2:
            try:
                den = int(m2.group(1))
            except Exception:
                den = None
            if den and (den in ALLOWED_DENOMS or den in {5, 8, 11}):
                _maybe_add(f"{den}scale")
    # Height in mm like '75mm'
    for m3 in re.finditer(r"\b([0-9]{2,3})\s*mm\b", full_raw):
        try:
            mm = int(m3.group(1))
        except Exception:
            mm = None
        if mm:
            _maybe_add(f"{mm}mm")

    return out


def _posix_path(s: str) -> str:
    return (s or "").replace("\\", "/")


def _leaf_name(rel_path: str) -> str:
    p = _posix_path(rel_path)
    return p.rsplit('/', 1)[-1] if '/' in p else p


def _parent_dir(rel_path: str) -> str:
    p = _posix_path(rel_path)
    return p.rsplit('/', 1)[0] if '/' in p else ''


_BOILERPLATE_TOKENS = {
    'uncut','scale','stl','lys','base','bases','images','image','preview','supported','presupported','pre','sup','sup_',
}


def _extract_scale_den_from_name(name: str) -> Optional[int]:
    s = (name or '').lower()
    # 1-6, 1/10, 1_56, 1:72 patterns with optional 'scale'
    m = re.search(r"\b1[\-_/,:]([0-9]{1,3})(?:\s*scale)?\b", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    # '6scale' form
    m = re.search(r"\b([0-9]{1,3})\s*scale\b", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _normalize_model_key(name: str) -> str:
    toks = [t for t in SPLIT_CHARS.split((name or '').lower()) if t]
    out: list[str] = []
    for t in toks:
        if t in _BOILERPLATE_TOKENS:
            continue
        dom = classify_token(t)
        if dom in ("scale_ratio", "scale_mm"):
            continue
        out.append(t)
    return ' '.join(out)


def infer_segmentation_from_siblings(session, variant: Variant, current_segmentation: Optional[str], allow_cross_scale: bool = True) -> tuple[Optional[str], bool]:
    """Infer segmentation by checking sibling variants in the same parent folder.
    Heuristic:
      - If current leaf contains token 'uncut' => 'merged' (already handled upstream; return current as-is if set).
      - Else, if any sibling's leaf name equals ours when removing 'uncut' tokens AND that sibling contains 'uncut', infer 'split'.
    """
    try:
        rel = variant.rel_path or ''
    except Exception:
        return (current_segmentation, False)
    leaf = _leaf_name(rel)
    leaf_toks = [t for t in SPLIT_CHARS.split(leaf.lower()) if t]
    if 'uncut' in leaf_toks:
        # Prefer explicit token signal; keep current if already set to merged
        return (current_segmentation or 'merged', False)
    parent = _parent_dir(rel)
    if not parent:
        return (current_segmentation, False)
    # Helper to query by prefix in a cross-platform manner
    def _query_by_prefix(prefix: str):
        try:
            from sqlalchemy import or_  # type: ignore
        except Exception:
            return session.query(Variant).filter(Variant.rel_path.like(prefix + '/%')).all()
        return (
            session.query(Variant).filter(
                or_(
                    Variant.rel_path.like(prefix + '/%'),
                    Variant.rel_path.like(prefix.replace('/', '\\') + '\\%')
                )
            ).all()
        )
    # Query siblings under same parent (both slash/backslash forms)
    sibs = []
    try:
        sibs = _query_by_prefix(parent)
    except Exception:
        sibs = []
    base_key = _normalize_model_key(leaf)
    cur_den = _extract_scale_den_from_name(leaf)
    for s in sibs:
        if s.id == variant.id:
            continue
        s_leaf = _leaf_name(getattr(s, 'rel_path', '') or '')
        s_toks = [t for t in SPLIT_CHARS.split(s_leaf.lower()) if t]
        if 'uncut' not in s_toks:
            continue
        if _normalize_model_key(s_leaf) == base_key:
            # Found 'uncut' sibling matching our base -> we are the split variant
            cross = False
            s_den = _extract_scale_den_from_name(s_leaf)
            if allow_cross_scale and cur_den and s_den and s_den != cur_den:
                cross = True
            return (current_segmentation or 'split', cross)
    # Fallback: check cousins under grandparent (parallel subfolders like '.../foo' vs '.../foo uncut')
    gp = _parent_dir(parent)
    if gp and allow_cross_scale:
        try:
            cousins = _query_by_prefix(gp)
        except Exception:
            cousins = []
        for s in cousins:
            s_leaf = _leaf_name(getattr(s, 'rel_path', '') or '')
            s_toks = [t for t in SPLIT_CHARS.split(s_leaf.lower()) if t]
            if 'uncut' not in s_toks:
                continue
            if _normalize_model_key(s_leaf) == base_key:
                return (current_segmentation or 'split', True)
    return (current_segmentation, False)


def classify_tokens(tokens: Iterable[str], designer_map: dict[str, str], franchise_map: dict[str, str] | None = None, character_map: dict[str, str] | None = None,
                    intended_use_map: Optional[Dict[str, set]] = None, general_faction_map: Optional[Dict[str, set]] = None,
                    designer_phrases: Optional[list[tuple[list[str], str]]] = None):
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
        "intended_use_bucket": None,
    }

    # Ensure we have a list for co-occurrence checks
    token_list = list(tokens)

    # Minimal bigram expansion to catch two-word character aliases like 'poison ivy'
    # and their snake_case variants 'poison_ivy'. Prefer matches on these longer
    # forms before considering shorter ambiguous tokens like 'ivy'.
    def _expand_with_bigrams(toks: list[str]) -> list[str]:
        out = set(toks)
        for i in range(len(toks) - 1):
            a, b = toks[i], toks[i+1]
            if not a or not b:
                continue
            # Only combine alphabetic tokens to reduce noise
            if a.isalnum() and b.isalnum():
                out.add(f"{a}_{b}")
                out.add(f"{a} {b}")
        return list(out)

    alias_token_list = _expand_with_bigrams(token_list)
    # Track lineage candidates with their positional index to bias towards
    # deeper path segments (tokens closer to the file/final folder appear
    # later in the token list produced by tokenize()).
    lineage_candidates: list[tuple[int, str]] = []
    # Conservative tabletop detection: require tabletop hint tokens AND no
    # stronger evidence tokens (designer/franchise/character). This avoids
    # treating artist/collection labels like "minis" or store names as
    # tabletop context when explicit franchise/character/designer tokens are
    # present.
    has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
    # Evaluate character evidence with gating to avoid counting weak aliases like '002'
    def _has_franchise_alias(tokens: list[str]) -> bool:
        return bool(franchise_map and any(t in franchise_map for t in tokens))

    def _is_valid_character_token(tok: str) -> bool:
        if not (character_map and tok in character_map):
            return False
        # Suppress extremely short/numeric codes unless there is supporting franchise evidence
        if _short_or_numeric(tok) and not _has_franchise_alias(token_list):
            return False
        # Suppress ambiguous aliases unless there is supporting franchise evidence
        if tok in AMBIGUOUS_ALIASES and not _has_franchise_alias(token_list):
            return False
        return True

    has_stronger_context = False
    if designer_map and any(t in designer_map for t in token_list):
        has_stronger_context = True
    if franchise_map and any(t in franchise_map for t in alias_token_list):
        has_stronger_context = True
    if any(_is_valid_character_token(t) for t in alias_token_list):
        has_stronger_context = True
    is_tabletop = has_tabletop_hint and not has_stronger_context

    # Pre-pass: prefer multi-token character aliases present in alias_token_list
    # (e.g., 'poison_ivy' from tokens ['poison','ivy']). Choose the longest match first.
    if character_map and not inferred.get("character_hint"):
        candidates = [t for t in alias_token_list if t in character_map]
        if candidates:
            # sort by length desc to prefer longer, more specific aliases
            for cand in sorted(candidates, key=lambda s: (-len(s), s)):
                # gating: same as below
                if _short_or_numeric(cand) and not _has_franchise_alias(alias_token_list):
                    continue
                if cand in AMBIGUOUS_ALIASES and not _has_franchise_alias(alias_token_list):
                    continue
                inferred["character_hint"] = cand
                inferred["character_name"] = character_map[cand]
                inferred.setdefault("normalization_warnings", [])
                if "character_without_context" not in inferred["normalization_warnings"]:
                    inferred["normalization_warnings"].append("character_without_context")
                break

    # Optional: intended_use from tokenmap.md (conservative, single bucket; conflict -> warning)
    if intended_use_map:
        hits: List[str] = []
        for bucket, toks in intended_use_map.items():
            if any(t in toks for t in token_list):
                hits.append(bucket)
        if len(hits) == 1:
            inferred["intended_use_bucket"] = hits[0]
        elif len(hits) > 1:
            inferred.setdefault("normalization_warnings", [])
            if "intended_use_conflict" not in inferred["normalization_warnings"]:
                inferred["normalization_warnings"].append("intended_use_conflict")
    # Multi-token designer alias detection from designers_tokenmap.md phrases
    if not inferred["designer"] and designer_phrases:
        n = len(token_list)
        # Prefer longer phrases first to avoid small matches shadowing longer ones
        for phrase, canon in sorted(designer_phrases, key=lambda pc: -len(pc[0])):
            L = len(phrase)
            if L == 0 or L > n:
                continue
            for i in range(0, n - L + 1):
                if token_list[i:i+L] == phrase:
                    if canon not in DESIGNER_IGNORE:
                        inferred["designer"] = canon
                    break
            if inferred["designer"]:
                break

    for idx, tok in enumerate(token_list):
        dom = classify_token(tok)
        # Designer: prefer canonical mapping via DB alias map
        if not inferred["designer"] and tok in designer_map:
            cand = designer_map[tok]
            if cand not in DESIGNER_IGNORE:
                inferred["designer"] = cand
            continue
        # Direct domain matches from tokenmap small parse
        if dom == "lineage_family":
            # Defer picking until after the loop so we can choose the deepest
            # (last) occurrence, reducing false positives from generic top-level
            # collection names like "goblin" or similar umbrella labels.
            lineage_candidates.append((idx, tok))
            # do not continue; other domain checks may still apply to the same token
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
        # General faction buckets (optional, from tokenmap.md), only when tabletop context is likely
        if general_faction_map and is_tabletop and not inferred.get("faction_general"):
            for bucket, toks in general_faction_map.items():
                if tok in toks:
                    inferred["faction_general"] = bucket
                    # Do not set any codex/system here; this is a coarse bucket
                    break
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
            # Only accept reasonable character aliases; ignore short/numeric or ambiguous
            # ones unless there is franchise evidence present in the same token list.
            if _short_or_numeric(tok) and not _has_franchise_alias(alias_token_list):
                # too weak on its own
                continue
            if tok in AMBIGUOUS_ALIASES and not _has_franchise_alias(alias_token_list):
                # ambiguous without support
                continue
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

    # Additional segmentation hints not covered by classify_token domain mapping
    if not inferred.get("segmentation"):
        lower_tokens = set(token_list)
        # Merged indicators first (avoid misclassifying 'non split version' as split)
        if ("uncutversion" in lower_tokens) or ("uncut" in lower_tokens and "version" in lower_tokens):
            inferred["segmentation"] = "merged"
        elif ("nonsplitversion" in lower_tokens) or (("non" in lower_tokens or "no" in lower_tokens) and "split" in lower_tokens and "version" in lower_tokens):
            inferred["segmentation"] = "merged"
        elif ("unsplit" in lower_tokens) or ("non_split_version" in lower_tokens):
            inferred["segmentation"] = "merged"
        # Split indicators
        elif ("cutversion" in lower_tokens) or ("cut" in lower_tokens and "version" in lower_tokens):
            inferred["segmentation"] = "split"
        else:
            SYN_SPLIT = {"sectioned", "separated", "segmented", "sliced", "slice"}
            if lower_tokens.intersection(SYN_SPLIT):
                inferred["segmentation"] = "split"
            elif ("splitversion" in lower_tokens) or ("split" in lower_tokens and "version" in lower_tokens):
                inferred["segmentation"] = "split"
            elif ("cut" in lower_tokens and "parts" in lower_tokens) or \
                 ("separate" in lower_tokens and "parts" in lower_tokens) or \
                 ("separated" in lower_tokens and "parts" in lower_tokens) or \
                 ("split" in lower_tokens and "parts" in lower_tokens):
                inferred["segmentation"] = "split"
            else:
                # Tertiary: tokens with cut as a boundary word (foo-cut, cut-bar, foo_cut, cut_bar)
                # Avoid matching 'uncut' and avoid freeform substrings like 'haircut'
                for t in token_list:
                    lt = t.lower()
                    if lt == "uncut":
                        continue
                    if lt == "cut" or lt.endswith("-cut") or lt.endswith("_cut") or lt.startswith("cut-") or lt.startswith("cut_"):
                        inferred["segmentation"] = "split"
                        break

    # Additional support-state hints (for concatenated or variant-specific forms)
    if not inferred.get("support_state"):
        has_presupported = False
        has_supported = False
        has_unsupported = False
        # token-level checks to catch joined forms like 'presupportedstl' or 'presupportedhairfront'
        for t in token_list:
            lt = t.lower()
            if lt in {"unsupported", "no_supports", "no_support", "nosupports", "nosupport", "clean"}:
                has_unsupported = True
            # explicit supported
            if lt == "supported" or lt.startswith("supported_") or lt.startswith("supported-"):
                has_supported = True
            # presupported appears as prefixes in many filenames
            if lt == "presupported" or lt.startswith("presupported") or lt.startswith("pre-supported") or lt.startswith("pre_supported"):
                has_presupported = True
        # Also handle cases where 'pre' and 'supported' are separate tokens
        lower_set = set(token_list)
        if ("pre" in lower_set and "supported" in lower_set) or ("pre" in lower_set and any(tok.startswith("supported") for tok in lower_set)):
            has_presupported = True
        # Resolve precedence and set inferred state
        if has_presupported and has_unsupported:
            inferred["support_state"] = "presupported"
            inferred.setdefault("normalization_warnings", [])
            if "support_state_conflict" not in inferred["normalization_warnings"]:
                inferred["normalization_warnings"].append("support_state_conflict")
        elif has_presupported:
            inferred["support_state"] = "presupported"
        elif has_supported:
            inferred["support_state"] = "supported"
        elif has_unsupported:
            inferred["support_state"] = "unsupported"

    # Secondary scale detection pass: handle split tokens like
    # "1-6 scale" -> ["1", "6", "scale"] and "1-6scale" -> ["1", "6scale"].
    # Only run if not already detected by direct token matches.
    if not inferred.get("scale_ratio_den"):
        n = len(token_list)
        # Helper to parse a denominator from a token like "6" or "6scale"
        def _parse_den_from_token(t: str) -> Optional[int]:
            m = re.match(r"^([0-9]{1,3})(?:scale)?$", t)
            if not m:
                return None
            try:
                return int(m.group(1))
            except Exception:
                return None

        # Pattern A: 1, <den>[scale]? [, 'scale'] (requires presence of '1' token, often removed by tokenizer; best effort)
        for i in range(0, n - 1):
            if token_list[i] != "1":
                continue
            nxt = token_list[i + 1]
            den = _parse_den_from_token(nxt)
            nxt2 = token_list[i + 2] if (i + 2) < n else None
            has_scale_neighbor = (isinstance(nxt, str) and nxt.endswith("scale")) or (nxt2 == "scale")
            if den and has_scale_neighbor:
                # Accept only common/suspect denominators to avoid false positives
                if den in ALLOWED_DENOMS or den in {5, 8, 11}:
                    inferred["scale_ratio_den"] = den
                    break

        # Pattern B: 'scale', '1', <den> or simply 'scale', <den> (when '1' was dropped by tokenizer)
        if not inferred.get("scale_ratio_den"):
            for i in range(0, n - 1):
                if token_list[i] == "scale":
                    # Prefer two- or three-digit neighbor as denominator
                    neighbor = token_list[i + 1] if (i + 1) < n else None
                    if neighbor and re.fullmatch(r"[0-9]{2,3}", neighbor):
                        den = int(neighbor)
                        if den in ALLOWED_DENOMS or den in {5, 8, 11}:
                            inferred["scale_ratio_den"] = den
                            break
                    # Consider '1' then two/three-digit as well
                    if (i + 2) < n and token_list[i + 1] == "1":
                        neighbor2 = token_list[i + 2]
                        if neighbor2 and re.fullmatch(r"[0-9]{2,3}", neighbor2):
                            den = int(neighbor2)
                            if den in ALLOWED_DENOMS or den in {5, 8, 11}:
                                inferred["scale_ratio_den"] = den
                                break

        # Pattern C: standalone '<den>scale' token (e.g., '6scale', '9scale')
        if not inferred.get("scale_ratio_den"):
            for t in token_list:
                m = re.fullmatch(r"([0-9]{1,3})scale", t)
                if m:
                    try:
                        den = int(m.group(1))
                    except Exception:
                        den = None
                    if den and (den in ALLOWED_DENOMS or den in {5, 8, 11}):
                        inferred["scale_ratio_den"] = den
                        break

    # Heuristic: if no explicit lineage was found, use strong thematic hints near the tail (last ~8 tokens)
    if not inferred["lineage_family"]:
        tail = token_list[-8:] if len(token_list) >= 8 else token_list
        tail_set = set(tail)
        rat_strong = any(t in tail_set for t in RAT_STRONG)
        rat_sub = any(('rat' in t) for t in tail)
        # Count weak rat cues allowing substring matches for select morphemes
        # to catch names like "darktail" and "gnawnine" that often appear as single tokens.
        def _has_weak_sub(t: str) -> bool:
            # require meaningful substrings to reduce false positives like "detail";
            # trim trailing punctuation when checking suffixes
            t2 = re.sub(r"[^a-z0-9]+$", "", t)
            return (
                (t2.endswith('tail') or t2.endswith('tails')) or
                ('gnaw' in t2) or ('scratch' in t2) or ('whisk' in t2) or ('fang' in t2) or ('claw' in t2)
            )
        rat_weak_count = sum(1 for t in tail if (t in RAT_WEAK) or _has_weak_sub(t))
        # Adjacent-pair detection: if two adjacent tail tokens together form a strong rat cue
        # (e.g., "gnawnine" next to "darktail"), prefer ratfolk.
        rat_adjacent_pair = False
        if len(tail) >= 2:
            for i in range(len(tail)-1):
                a, b = tail[i], tail[i+1]
                if (_has_weak_sub(a) and _has_weak_sub(b)) or ((a in RAT_WEAK) and _has_weak_sub(b)) or (_has_weak_sub(a) and (b in RAT_WEAK)):
                    rat_adjacent_pair = True
                    break
        undead_hit = any(t in tail_set for t in UNDEAD_HINTS)
        # Prefer ratfolk when strong or adjacent weak cues exist near the tail.
        # Adjacent weak-pair is decisive even if generic undead words appear elsewhere in the path.
        if (rat_strong or rat_sub or rat_adjacent_pair):
            inferred["lineage_family"] = "ratfolk"
        elif not rat_strong and not rat_sub and rat_weak_count >= 2:
            # multiple weak cues plus a 'rat' token somewhere else in the path
            # previously required a separate 'rat' substring elsewhere; relax to allow tail-driven pairs
            inferred["lineage_family"] = "ratfolk"
        elif undead_hit and not (rat_strong or rat_sub or rat_adjacent_pair):
            inferred["lineage_family"] = "undead"

    # After scanning tokens, if we saw lineage candidates, prefer the deepest
    # one (largest positional index). This biases towards folder names closer
    # to the actual model files or the filename itself, which are typically
    # more specific than generic top-level collection labels.
    if not inferred["lineage_family"] and lineage_candidates:
        # Apply context-based suppression for ambiguous 'ork' usage like
        # "primaris killing ork" (Ork is object). If Space Marine hints are
        # present, or an action verb immediately precedes the 'ork' token, do
        # not assign 'ork' unless we also have Ork-specific subject hints.
        token_set = set(token_list)
        filtered_candidates: list[tuple[int, str]] = []
        suppressed = False
        for idx, tok in lineage_candidates:
            if tok in ORX_EQUIV:
                has_sm_context = any(h in token_set for h in SPACE_MARINE_HINTS)
                local_prev = {token_list[i] for i in range(max(0, idx-2), idx)}
                has_action_context = any(v in local_prev for v in ACTION_VERBS)
                has_ork_support = any(h in token_set for h in ORK_SUBJECT_HINTS)
                if (has_sm_context or has_action_context) and not has_ork_support:
                    suppressed = True
                    continue
            filtered_candidates.append((idx, tok))
        # Replace candidates with filtered list; if suppression removed all
        # candidates, leave the list empty to avoid assigning a misleading
        # lineage from fallback.
        if filtered_candidates:
            lineage_candidates = filtered_candidates
        elif suppressed:
            lineage_candidates = []
        if suppressed:
            inferred.setdefault("normalization_warnings", [])
            if "lineage_ambiguous_vs_context" not in inferred["normalization_warnings"]:
                inferred["normalization_warnings"].append("lineage_ambiguous_vs_context")
        # If multiple candidates, choose the deepest (largest index)
        if len(lineage_candidates) > 1:
            _, chosen = max(lineage_candidates, key=lambda it: it[0])
            inferred["lineage_family"] = chosen
        elif len(lineage_candidates) == 1:
            idx, only_tok = lineage_candidates[0]
            # Heuristic: if the only lineage token is very early in the token
            # sequence (likely from a top-level umbrella folder), and there are
            # many tokens overall, treat this as weak evidence and avoid
            # assignment to reduce false positives such as
            #   "goblin mayhem and holy angels/.../actual_non_goblin_files.stl"
            many_tokens = len(token_list) >= 8
            if idx <= 2 and many_tokens:
                inferred.setdefault("normalization_warnings", [])
                if "lineage_weak_top_level" not in inferred["normalization_warnings"]:
                    inferred["normalization_warnings"].append("lineage_weak_top_level")
            else:
                inferred["lineage_family"] = only_tok
            # else: no candidates remain; leave lineage unset with warnings

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
    # Intended use bucket (from tokenmap, gated)
    set_if_empty("intended_use_bucket", inferred.get("intended_use_bucket"))
    # General faction (coarse), distinct from franchise-derived signals
    set_if_empty("faction_general", inferred.get("faction_general"))
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
    # token locale tagging (guarded for older DBs)
    try:
        if inferred.get("token_locale") and (getattr(variant, 'token_locale', None) in (None, "")):
            variant.token_locale = inferred.get("token_locale")
            changed["token_locale"] = inferred.get("token_locale")
    except Exception:
        pass

    return changed


def diff_updates_for_variant(variant: Variant, inferred: dict, force: bool = False) -> dict:
    """Compute what would change if we applied inferred fields to the variant,
    without mutating the SQLAlchemy object. Mirrors apply_updates_to_variant's logic.
    """
    changed = {}

    def would_set(field, value):
        cur = getattr(variant, field)
        return (value not in (None, [], {}) and ((cur in (None, "", [], {})) or force) and cur != value)

    # Simple fields that are only set when empty
    if would_set("raw_path_tokens", inferred.get("residual_tokens") or []):
        changed["raw_path_tokens"] = inferred.get("residual_tokens") or []
    if would_set("residual_tokens", inferred.get("residual_tokens") or []):
        changed["residual_tokens"] = inferred.get("residual_tokens") or []
    if would_set("token_version", inferred.get("token_version")):
        changed["token_version"] = inferred.get("token_version")
    if would_set("designer", inferred.get("designer")):
        changed["designer"] = inferred.get("designer")
        # designer_confidence follows designer
        if would_set("designer_confidence", "high"):
            changed.setdefault("designer_confidence", "high")
    if would_set("franchise", inferred.get("franchise")):
        changed["franchise"] = inferred.get("franchise")
    if would_set("lineage_family", inferred.get("lineage_family")):
        changed["lineage_family"] = inferred.get("lineage_family")

    # Merge list fields conservatively
    if inferred.get("franchise_hints"):
        cur_hints = variant.franchise_hints or []
        merged = list(dict.fromkeys(cur_hints + inferred["franchise_hints"]))
        if merged != cur_hints:
            changed["franchise_hints"] = merged

    if inferred.get("character_name"):
        if would_set("character_name", inferred.get("character_name")):
            changed["character_name"] = inferred.get("character_name")
        hint = inferred.get("character_hint")
        if hint:
            cur_aliases = variant.character_aliases or []
            new_aliases = [hint] if not cur_aliases else list(dict.fromkeys(cur_aliases + [hint]))
            if new_aliases != cur_aliases:
                changed["character_aliases"] = new_aliases

    # Other single-valued fields
    for fld in ("segmentation","internal_volume","support_state","part_pack_type","has_bust_variant",
                "scale_ratio_den","height_mm","pc_candidate_flag","intended_use_bucket","faction_general","content_flag"):
        val = inferred.get(fld)
        if would_set(fld, val):
            changed[fld] = val

    # normalization warnings merge
    if inferred.get("normalization_warnings"):
        curw = variant.normalization_warnings or []
        neww = list(curw)
        for w in inferred.get("normalization_warnings"):
            if w not in neww:
                neww.append(w)
        if neww != curw:
            changed["normalization_warnings"] = neww
    try:
        if inferred.get("token_locale"):
            if would_set("token_locale", inferred.get("token_locale")):
                changed["token_locale"] = inferred.get("token_locale")
    except Exception:
        pass

    return changed


def process_variants(batch_size: int, apply: bool, only_missing: bool, force: bool, tokenmap_path: Optional[str] = None,
                     use_intended_use: bool = False, use_general_faction: bool = False, out: Optional[str] = None,
                     include_fields: Optional[list[str]] = None, exclude_fields: Optional[list[str]] = None,
                     print_summary: bool = False, ids: Optional[list[int]] = None,
                     use_franchise_preferences: bool = True,
                     default_tabletop_when_system: bool = True,
                     limit: int = 0):
    # Use repository root (two levels up from scripts/30_normalize_match)
    root = PROJECT_ROOT
    # try to load tokenmap to set token version & domain sets
    tm_path = Path(tokenmap_path) if tokenmap_path else (root / 'vocab' / 'tokenmap.md')
    if tm_path.exists():
        _stats = load_tokenmap(tm_path)
        token_map_version = getattr(sys.modules.get('scripts.quick_scan'), 'TOKENMAP_VERSION', None)
    else:
        token_map_version = None
    intended_use_map = parse_tokenmap_intended_use(tm_path) if (tm_path.exists() and use_intended_use) else None
    general_faction_map = parse_tokenmap_general_faction(tm_path) if (tm_path.exists() and use_general_faction) else None
    # Load designers from JSON (preferred) and fallback to MD phrases
    designers_json = (root / 'vocab' / 'designers_tokenmap.json')
    designer_alias_override: dict[str, str] = {}
    designer_specialization: dict[str, str] = {}
    designer_phrases: list[tuple[list[str], str]] = []
    if designers_json.exists():
        alias_map_json, phrases_json, specialization = load_designers_json(designers_json)
        designer_alias_override = alias_map_json
        designer_phrases = phrases_json
        designer_specialization = specialization
    else:
        designers_path = (root / 'vocab' / 'designers_tokenmap.md')
        designer_phrases = parse_designers_aliases(designers_path) if designers_path.exists() else []

    # Load franchise preferences (optional, enabled by default)
    franchise_pref_phrases: list[tuple[list[str], str]] = []
    franchise_pref_default: dict[str, str] = {}
    fp_json = (root / 'vocab' / 'franchise_preferences.json')
    if use_franchise_preferences and fp_json.exists():
        franchise_pref_phrases, franchise_pref_default = load_franchise_preferences(fp_json)

    # Normalize filters
    include_set = set([f.strip() for f in (include_fields or []) if f.strip()])
    exclude_set = set([f.strip() for f in (exclude_fields or []) if f.strip()])

    print(f"Using database: {DB_URL}")
    with get_session() as session:
        designer_map = build_designer_alias_map(session)
        # If JSON provided aliases, overlay them (prefer explicit JSON over DB)
        if designer_alias_override:
            designer_map = {**designer_map, **designer_alias_override}
        franchise_map = build_franchise_alias_map(session)
        character_map = build_character_alias_map(session)

        # Build base query: only variants with at least one file (simple heuristic)
        q = session.query(Variant).join(File).distinct()
        if ids:
            q = q.filter(Variant.id.in_(ids))
        if only_missing:
            q = q.filter(Variant.token_version.is_(None))
        total = q.count()
        print(f"Found {total} variants to examine (only_missing={only_missing}).")
        offset = 0
        processed = 0
        proposed_updates = []
        field_counts: dict[str, int] = {}
        while True:
            rows = q.limit(batch_size).offset(offset).all()
            if not rows:
                break
            # Enforce optional processing limit
            if limit and processed >= limit:
                break
            if limit and processed + len(rows) > limit:
                rows = rows[: max(0, limit - processed)]
            for v in rows:
                tokens = tokens_from_variant(session, v)
                inferred = classify_tokens(tokens, designer_map, franchise_map, character_map,
                                           intended_use_map=intended_use_map,
                                           general_faction_map=general_faction_map,
                                           designer_phrases=designer_phrases)
                # Lightweight token locale tagging (no English backfill here)
                loc = _detect_token_locale(list(tokens))
                if loc:
                    inferred['token_locale'] = loc
                # Sibling-aware segmentation inference
                new_seg, cross_flag = infer_segmentation_from_siblings(session, v, inferred.get('segmentation'))
                inferred['segmentation'] = new_seg
                if cross_flag:
                    inferred.setdefault('normalization_warnings', [])
                    if 'segmentation_inferred_cross_scale' not in inferred['normalization_warnings']:
                        inferred['normalization_warnings'].append('segmentation_inferred_cross_scale')
                # If a designer specialization is defined and we inferred designer, set intended_use conservatively
                d = inferred.get('designer')
                if d and (not inferred.get('intended_use_bucket')) and d in designer_specialization:
                    inferred['intended_use_bucket'] = designer_specialization[d]
                # If still unset, use franchise preferences by phrase detection in tokens
                if (not inferred.get('intended_use_bucket')) and franchise_pref_phrases:
                    tlist = list(tokens)
                    n = len(tlist)
                    hit_canon: Optional[str] = None
                    for phrase, canon in franchise_pref_phrases:
                        L = len(phrase)
                        if L == 0 or L > n:
                            continue
                        for i in range(0, n - L + 1):
                            if tlist[i:i+L] == phrase:
                                hit_canon = canon
                                break
                        if hit_canon:
                            break
                    if hit_canon and hit_canon in franchise_pref_default:
                        inferred['intended_use_bucket'] = franchise_pref_default[hit_canon]
                # Final fallback: if this variant is clearly a tabletop unit (has a game system or codex faction
                # already assigned by other matchers), default intended_use_bucket to 'tabletop_intent' unless disabled.
                if default_tabletop_when_system and (not inferred.get('intended_use_bucket')):
                    if getattr(v, 'game_system', None) or getattr(v, 'codex_faction', None) or getattr(v, 'faction_general', None):
                        inferred['intended_use_bucket'] = 'tabletop_intent'
                inferred["token_version"] = token_map_version
                # IMPORTANT: do not mutate DB objects during preview; compute a diff instead
                changed = diff_updates_for_variant(v, inferred, force=force)
                if changed:
                    if include_set:
                        visible = {k: val for k, val in changed.items() if k in include_set}
                    else:
                        visible = {k: val for k, val in changed.items() if k not in exclude_set}
                    if visible:
                        proposed_updates.append({"variant_id": v.id, "rel_path": v.rel_path, "changes": visible})
                        for k in visible.keys():
                            field_counts[k] = field_counts.get(k, 0) + 1
            processed += len(rows)
            offset += batch_size
        print(f"Proposed updates for {len(proposed_updates)} variants (dry-run={not apply}).")
        if print_summary and field_counts:
            print("Field change summary:")
            for k, cnt in sorted(field_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"  {k}: {cnt}")
        # Print a small sample
        for s in proposed_updates[:10]:
            print(json.dumps(s, indent=2))
        # Optional JSON export in dry-run
        if out:
            try:
                out_path = Path(out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "apply": bool(apply),
                    "total_examined": total,
                    "proposals_count": len(proposed_updates),
                    "proposals": proposed_updates,
                    "field_summary": field_counts,
                    "db_url": DB_URL,
                }
                out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
                print(f"Wrote JSON export to: {out_path}")
            except Exception as e:
                print(f"[warn] failed to write --out JSON: {e}")
        if apply and proposed_updates:
            # commit in batches to limit transaction size
            print("Applying updates to DB...")
            offset = 0
            processed_apply = 0
            total_applied = 0
            while True:
                rows = q.limit(batch_size).offset(offset).all()
                if not rows: break
                if limit and processed_apply >= limit:
                    break
                if limit and processed_apply + len(rows) > limit:
                    rows = rows[: max(0, limit - processed_apply)]
                any_changed = False
                for v in rows:
                    tokens = tokens_from_variant(session, v)
                    inferred = classify_tokens(tokens, designer_map, franchise_map, character_map,
                                               intended_use_map=intended_use_map,
                                               general_faction_map=general_faction_map,
                                               designer_phrases=designer_phrases)
                    loc = _detect_token_locale(list(tokens))
                    if loc:
                        inferred['token_locale'] = loc
                    new_seg, cross_flag = infer_segmentation_from_siblings(session, v, inferred.get('segmentation'))
                    inferred['segmentation'] = new_seg
                    if cross_flag:
                        inferred.setdefault('normalization_warnings', [])
                        if 'segmentation_inferred_cross_scale' not in inferred['normalization_warnings']:
                            inferred['normalization_warnings'].append('segmentation_inferred_cross_scale')
                    d = inferred.get('designer')
                    if d and (not inferred.get('intended_use_bucket')) and d in designer_specialization:
                        inferred['intended_use_bucket'] = designer_specialization[d]
                    if (not inferred.get('intended_use_bucket')) and franchise_pref_phrases:
                        tlist = list(tokens)
                        n = len(tlist)
                        hit_canon: Optional[str] = None
                        for phrase, canon in franchise_pref_phrases:
                            L = len(phrase)
                            if L == 0 or L > n:
                                continue
                            for i in range(0, n - L + 1):
                                if tlist[i:i+L] == phrase:
                                    hit_canon = canon
                                    break
                            if hit_canon:
                                break
                        if hit_canon and hit_canon in franchise_pref_default:
                            inferred['intended_use_bucket'] = franchise_pref_default[hit_canon]
                    # Final fallback: default tabletop when system/faction present
                    if default_tabletop_when_system and (not inferred.get('intended_use_bucket')):
                        if getattr(v, 'game_system', None) or getattr(v, 'codex_faction', None) or getattr(v, 'faction_general', None):
                            inferred['intended_use_bucket'] = 'tabletop_intent'
                    inferred["token_version"] = token_map_version
                    changed = apply_updates_to_variant(v, inferred, session, force=force)
                    if changed:
                        any_changed = True
                        total_applied += 1
                if any_changed:
                    session.commit()
                processed_apply += len(rows)
                offset += batch_size
            print(f"Apply complete. Variants updated: {total_applied}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Normalize Variant+File metadata from path tokens")
    ap.add_argument('--batch', type=int, default=200, help='Variants per DB batch')
    ap.add_argument('--apply', action='store_true', help='Write inferred metadata to DB (default: dry-run)')
    ap.add_argument('--only-missing', action='store_true', help='Only process variants lacking token_version')
    ap.add_argument('--force', action='store_true', help='Overwrite existing fields (use with care)')
    ap.add_argument('--tokenmap', help='Path to tokenmap.md (defaults to vocab/tokenmap.md)')
    ap.add_argument('--use-intended-use', action='store_true', help='Enable intended_use_bucket inference from tokenmap.md')
    ap.add_argument('--use-general-faction', action='store_true', help='Enable general faction bucket inference from tokenmap.md when tabletop context detected')
    ap.add_argument('--out', help='Write dry-run proposals to this JSON file')
    ap.add_argument('--include-fields', help='Comma-separated list of fields to include in proposals (reporting only)')
    ap.add_argument('--exclude-fields', help='Comma-separated list of fields to exclude from proposals (reporting only)')
    ap.add_argument('--print-summary', action='store_true', help='Print a summary of change counts by field')
    ap.add_argument('--ids', help='Comma-separated list of Variant IDs to process (scoped run)')
    ap.add_argument('--no-franchise-preferences', action='store_true', help='Disable intended-use inference from franchise_preferences.json')
    ap.add_argument('--no-default-tabletop-when-system', dest='default_tabletop_when_system', action='store_false',
                    help="Do not default intended_use_bucket to 'tabletop_intent' when game_system or codex_faction is present")
    ap.add_argument('--limit', type=int, default=0, help='Maximum number of variants to process (0 = no limit)')
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    include_fields = [s for s in (args.include_fields.split(',') if args.include_fields else [])]
    exclude_fields = [s for s in (args.exclude_fields.split(',') if args.exclude_fields else [])]
    ids = [int(s) for s in args.ids.split(',')] if getattr(args, 'ids', None) else None
    process_variants(batch_size=args.batch, apply=args.apply, only_missing=args.only_missing, force=args.force,
                     tokenmap_path=args.tokenmap, use_intended_use=args.use_intended_use,
                     use_general_faction=args.use_general_faction, out=args.out,
                     include_fields=include_fields, exclude_fields=exclude_fields,
                     print_summary=args.print_summary, ids=ids,
                     use_franchise_preferences=(not args.no_franchise_preferences),
                     default_tabletop_when_system=getattr(args, 'default_tabletop_when_system', True),
                     limit=max(0, int(getattr(args, 'limit', 0) or 0)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

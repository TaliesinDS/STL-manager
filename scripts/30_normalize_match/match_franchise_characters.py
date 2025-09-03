#!/usr/bin/env python3
"""Match Variants to franchises and characters defined in `vocab/franchises/*.json`.

Conservative by default: runs in dry-run and prints proposed updates. Use
`--apply` to write changes to the DB. Respects tabletop hints and will not
assign franchises for tabletop-like variants.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple, List

# scripts/30_normalize_match/* -> repo root is two levels up
ROOT = Path(__file__).resolve().parents[2]
FR_DIR = ROOT / 'vocab' / 'franchises'
OC_WHITELIST_PATH = ROOT / 'vocab' / 'oc_whitelist.txt'

import sys
# Ensure project root is on sys.path so `from db...` imports work
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant

# Reuse helper functions from normalize_inventory
from scripts.normalize_inventory import tokens_from_variant, apply_updates_to_variant, TABLETOP_HINTS
from scripts.quick_scan import classify_token
from scripts.lib.alias_rules import (
    AMBIGUOUS_ALIASES,
    is_short_or_numeric as shared_short_or_numeric,
    has_supporting_franchise_tokens as shared_has_support,
)
try:
    # Use STOPWORDS to avoid forming bigrams across common words when available
    from scripts.quick_scan import STOPWORDS as QS_STOPWORDS
except Exception:
    QS_STOPWORDS = set()

# Optional: word frequency for English/Dutch common-word filtering
try:
    from wordfreq import zipf_frequency as _zipf
except Exception:
    _zipf = None

# --- Token expansion helpers (camelCase splitting, glued segmentation, n-grams) ---
import re as _re

_CAMEL_SPLIT_RE = _re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")

def split_mixed(token: str) -> list[str]:
    parts = _re.split(_CAMEL_SPLIT_RE, token)
    out = []
    for p in parts:
        p = (p or '').strip().lower()
        if len(p) >= 2:
            out.append(p)
    return out or ([token] if token else [])

def segment_with_vocab(token: str, vocab: set[str]) -> list[str]:
    s = (token or '').lower()
    if not s.isalpha() or len(s) < 6:  # only try glued lowercase words of reasonable length
        return [token]
    i, out = 0, []
    while i < len(s):
        j = len(s)
        found = None
        while j > i:
            cand = s[i:j]
            if cand in vocab:
                found = cand
                break
            j -= 1
        if not found:
            return [token]  # abort if we can't segment cleanly
        out.append(found)
        i = j
    return out if out else [token]

def expand_with_bigrams(tokens: list[str], stopwords: set[str]) -> list[str]:
    toks = [t for t in tokens if t]
    expanded = set(toks)
    for i in range(len(toks) - 1):
        a, b = toks[i], toks[i+1]
        if a in stopwords or b in stopwords:
            continue
        # Generate a few common join forms
        for j in (" ", "_", ""):
            combo = f"{a}{j}{b}"
            if 2 <= len(combo) <= 40:
                expanded.add(combo)
    return list(expanded)


def choose_best_franchise(
    token_list: list[str],
    fam: Dict[str, str],
    cam: Dict[str, Tuple[str, str]],
    f_tokens: Dict[str, Dict[str, set]],
) -> tuple[str | None, str | None, float]:
    """Score candidate franchises from token evidence and return (franchise, character, score).

    Scoring heuristics (conservative):
    - Character alias evidence outranks franchise alias evidence.
    - Longer aliases and multi-token joins (e.g., 'poison_ivy') beat short names like 'ivy'.
    - Strong signals from the franchise manifest add weight; weak adds small weight.
    - Ambiguous or short/numeric aliases are only considered when there is supporting evidence.
    """
    candidates: Dict[str, Dict[str, object]] = {}

    def _add_score(fr: str, inc: float, char: str | None = None) -> None:
        row = candidates.setdefault(fr, {"score": 0.0, "char": None})
        row["score"] = float(row["score"]) + inc
        if char and row.get("char") is None:
            row["char"] = char

    # Evaluate character aliases first
    for t in token_list:
        if t in cam:
            fr, ch = cam[t]
            # Ambiguity/short gating: require supporting tokens for weak evidence
            if t in AMBIGUOUS_ALIASES or shared_short_or_numeric(t):
                if not shared_has_support(fr, token_list, fam, f_tokens, exclude_token=t):
                    continue
            # base score for character alias
            score = 4.0
            # bonus for multi-token alias forms and length (specificity)
            if ("_" in t) or (" " in t):
                score += 3.0
            score += min(len(t), 30) / 12.0  # small length bias
            # strong signal boost if listed as strong token for franchise
            if t in (f_tokens.get(fr, {}).get("strong", set()) or set()):
                score += 2.0
            # ambiguous penalty (still allowed when support exists)
            if t in AMBIGUOUS_ALIASES:
                score -= 1.0
            _add_score(fr, score, ch)

    # Franchise alias evidence (lower weight)
    for t in token_list:
        if t in fam:
            fr = fam[t]
            if t in (f_tokens.get(fr, {}).get("stop", set()) or set()):
                continue
            score = 1.0
            if t in (f_tokens.get(fr, {}).get("strong", set()) or set()):
                score += 2.0
            elif t in (f_tokens.get(fr, {}).get("weak", set()) or set()):
                score += 0.5
            if ("_" in t) or (" " in t):
                score += 0.5
            _add_score(fr, score)

    # Pick best above a minimal threshold
    best_fr: str | None = None
    best_char: str | None = None
    best_score = 0.0
    for fr, row in candidates.items():
        sc = float(row.get("score", 0.0))
        if sc > best_score:
            best_fr = fr
            best_char = row.get("char") or None  # type: ignore[assignment]
            best_score = sc
    # require decisive evidence
    threshold = 4.0
    if best_score >= threshold:
        return best_fr, best_char, best_score
    return None, None, 0.0


# AMBIGUOUS_ALIASES now imported from scripts.lib.alias_rules

# Tokens that should not be considered as names even if they look alphabetic
NAME_BLOCKLIST = {
    "nsfw", "sfw", "fullbody", "supported", "presupported", "support", "stl",
    "files", "models", "model", "print", "prints", "mini", "miniature", "miniatures",
    "terrain", "scenery", "base", "bases", "v", "v1", "v2", "ver", "version"
}

PROVIDER_WORDS = {
    "dm", "stash", "dmstash", "heroesinfinite", "patreon", "myminifactory", "cults3d",
    "store", "sample", "samplestore", "supported", "presupported", "unsupported",
    "presupports", "stl", "stls", "lys", "lychee", "ctb", "cbddlp",
    "files", "models", "campaign", "release", "releases", "bonus", "extras",
    "nsfw", "sfw", "fullbody", "pack", "set", "parts", "component", "components"
}

MONTH_WORDS = {"january","february","march","april","may","june","july","august","september","october","november","december"}

GENERIC_OC_BLOCKLIST = {
    "warrior", "dragon", "chariot", "druid", "hero", "heroine", "archer", "ranger", "rangers",
    "hands", "helmets", "helmet", "weapons", "weapon", "combined", "bases", "base", "proxy",
    "female", "male", "girl", "boy", "woman", "man", "soldier", "soldiers", "unit", "units",
    # extra generic/system/domain words we saw in proposals
    "bodies", "body", "machine", "regiment", "goblin", "scan", "accessories", "empire", "human",
    "spells", "throne", "standard", "king", "crew", "captain", "musician", "bearer", "dogs"
}

# Lightweight fantasy-like name detector
_FANTASY_SUFFIXES = {"iel","wen","wyn","nor","lin","lil","riel","dil","mir","ril","vel","nel","rel","thor","dor","lor","ion","ian"}

def _load_oc_whitelist(path: Path) -> set[str]:
    wl: set[str] = set()
    try:
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                wl.add(s.lower())
    except Exception:
        pass
    return wl

OC_WHITELIST = _load_oc_whitelist(OC_WHITELIST_PATH)

def is_fantasy_like_name(word: str) -> bool:
    w = (word or "").strip().lower()
    if not w.isalpha():
        return False
    if len(w) < 5 or len(w) > 16:
        return False
    # must contain at least one vowel
    if not any(ch in "aeiou" for ch in w):
        return False
    # avoid triple letters
    import re as _re
    if _re.search(r"([a-z])\1\1", w):
        return False
    # frequency filter when available: reject common English/Dutch words
    if _zipf is not None:
        try:
            z_en = _zipf(w, "en")
        except Exception:
            z_en = -10.0
        try:
            z_nl = _zipf(w, "nl")
        except Exception:
            z_nl = -10.0
        # lower is rarer; typical real words are > 3.5. Accept if very rare in both.
        if (z_en is not None and z_en >= 2.5) or (z_nl is not None and z_nl >= 2.5):
            return False
    # whitelist overrides
    if w in OC_WHITELIST:
        return True
    # simple suffix hint (expanded slightly for coverage)
    extra_suffixes = {"enil","ina","fel","lus","amin","neal"}
    if any(w.endswith(suf) for suf in (_FANTASY_SUFFIXES | extra_suffixes)):
        return True
    # allow uncommon bigrams like 'gw', 'yn', 'ae', 'wy'
    uncommon = ["gw","yn","ae","wy","vh","yr","qe"]
    if any(bg in w for bg in uncommon):
        return True
    # fallback: if no freq info, do not accept unless suffix/uncommon matched earlier
    return False

def infer_oc_from_path(rel_path: str, reserved: set[str], fantasy_filter: bool = False) -> tuple[str|None, str|None]:
    """Infer an original character name from the last folder of rel_path.

    Rules:
    - Use last path component; split on '-', '_', and spaces.
    - Keep 1–2 alphabetic words (3–20 chars) not in reserved/blocklists/providers.
    - Require result length 1 or 2 words; else abstain.
    - Return lowercase underscore canonical and a prettified alias (space-joined with original casing best-effort).
    """
    try:
        tail = Path(rel_path).name
    except Exception:
        tail = rel_path or ""
    # Replace separators with space
    import re as _re
    cleaned = _re.sub(r"[\-_]+", " ", tail)
    # Skip if the last folder contains any digits (likely a collection/month/etc.)
    if _re.search(r"\d", cleaned):
        return None, None
    parts_raw = [p for p in cleaned.split() if p]
    # Filter parts
    parts: list[str] = []
    for p in parts_raw:
        pl = p.lower()
        if not pl.isalpha():
            continue
        if pl in NAME_BLOCKLIST or pl in PROVIDER_WORDS or pl in reserved:
            continue
        if not (3 <= len(pl) <= 20):
            continue
        parts.append(pl)
    if not parts:
        return None, None
    # Abort if parts include months or generic words
    if any(w in MONTH_WORDS for w in parts):
        return None, None
    if any(w in GENERIC_OC_BLOCKLIST for w in parts):
        return None, None
    # Prefer first two
    if len(parts) > 2:
        # too many words -> likely not a clean OC folder name
        return None, None
    if len(parts) == 2:
        canon_two = f"{parts[0]}_{parts[1]}"
        # whitelist full canonical two-word OC name
        if canon_two in OC_WHITELIST:
            alias = f"{parts[0].capitalize()} {parts[1].capitalize()}"
            return canon_two, alias
        if fantasy_filter and (not is_fantasy_like_name(parts[0]) or not is_fantasy_like_name(parts[1])):
            return None, None
        canonical = f"{parts[0]}_{parts[1]}"
        alias = f"{parts[0].capitalize()} {parts[1].capitalize()}"
        return canonical, alias
    # single word
    if len(parts) == 1 and len(parts[0]) >= 4:
        # whitelist single
        if parts[0] in OC_WHITELIST:
            canonical = parts[0]
            alias = parts[0].capitalize()
            return canonical, alias
        if fantasy_filter and not is_fantasy_like_name(parts[0]):
            return None, None
        canonical = parts[0]
        alias = parts[0].capitalize()
        return canonical, alias
    return None, None

def load_franchise_maps(fr_dir: Path) -> Tuple[Dict[str, str], Dict[str, Tuple[str, str]], Dict[str, Dict[str, set]]]:
    """Return (franchise_alias_map, character_alias_map, franchise_tokens).

    - franchise_alias_map: alias(lower) -> franchise_key
    - character_alias_map: alias(lower) -> (franchise_key, character_canonical)
    - franchise_tokens: franchise_key -> {'strong': set(...), 'weak': set(...)}
    """
    fam: Dict[str, str] = {}
    cam: Dict[str, Tuple[str, str]] = {}
    f_tokens: Dict[str, Dict[str, set]] = {}
    for p in sorted(fr_dir.glob('*.json')):
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        franchise_key = j.get('franchise') or p.stem
        # tokens (strong/weak/stop signals) at franchise level
        tokens_block = j.get('tokens') or {}
        strong = set((t or '').strip().lower() for t in (tokens_block.get('strong_signals') or []))
        weak = set((t or '').strip().lower() for t in (tokens_block.get('weak_signals') or []))
        stop = set((t or '').strip().lower() for t in (tokens_block.get('stop_conflicts') or []))
        f_tokens[franchise_key] = {'strong': strong, 'weak': weak, 'stop': stop}

        # franchise aliases (exclude those explicitly marked as stop_conflicts)
        for a in (j.get('aliases') or []):
            alias = str(a).strip().lower()
            if alias and (alias not in stop):
                fam[alias] = franchise_key

        # characters
        for c in (j.get('characters') or []):
            canon = c.get('canonical')
            aliases = []
            if canon:
                aliases.append(canon)
            aliases.extend(c.get('aliases') or [])
            for a in aliases:
                if not a:
                    continue
                cam[str(a).strip().lower()] = (franchise_key, canon)

    # Merge standalone characters_tokenmap.md aliases (improves recall)
    chars_map_path = ROOT / 'vocab' / 'characters_tokenmap.md'
    from_path_aliases = parse_characters_tokenmap(chars_map_path)
    for alias, canonical in from_path_aliases.items():
        # Only add if not already present from franchise manifests
        if alias not in cam:
            # No franchise association for these entries (None), canonical set
            cam[alias] = (None, canonical)

    # Merge tokenmap.md aliases into franchise maps when group key matches
    tokenmap_path = ROOT / 'vocab' / 'tokenmap.md'
    tmap = parse_tokenmap_aliases(tokenmap_path)
    for group, aliases in tmap.items():
        gkey = group.strip().lower()
        if gkey in f_tokens:
            # add aliases to franchise alias map and to weak tokens set
            for a in aliases:
                fam.setdefault(a, gkey)
                f_tokens[gkey]['weak'].add(a)

    return fam, cam, f_tokens



def parse_characters_tokenmap(path: Path) -> Dict[str, str]:
    """Parse a simple characters_tokenmap.md file and return alias->canonical mapping.

    The file format is a lightweight YAML-like block with a top-level `characters:`
    followed by entries like:

    characters:
      ahko:
        - "ahko"
        - "ahkoqueen"

    We return a dict mapping each alias (lowercased) -> canonical (string).
    """
    out: Dict[str, str] = {}
    if not path.exists():
        return out
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    in_chars = False
    cur_key = None
    for ln in lines:
        stripped = ln.strip()
        if not in_chars:
            if stripped.startswith('characters:'):
                in_chars = True
            continue
        # inside characters block
        if not stripped:
            cur_key = None
            continue
        # detect a new canonical key (e.g., 'ahko:')
        if stripped.endswith(':') and not stripped.startswith('-'):
            cur_key = stripped[:-1].strip().lower()
            # add canonical as its own alias
            if cur_key:
                out[cur_key] = cur_key
            continue
        # detect list item: - "alias"
        if stripped.startswith('-') and cur_key:
            item = stripped.lstrip('-').strip()
            # remove surrounding quotes if present
            if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            if item:
                out[item.strip().lower()] = cur_key
            continue
        # stop if we reach a top-level header or block that's not indented
        if not ln.startswith(' ') and not ln.startswith('\t'):
            break
    return out


def parse_tokenmap_aliases(path: Path) -> Dict[str, List[str]]:
    """Parse `vocab/tokenmap.md` for simple alias lists and return group->aliases.

    Heuristic parser: finds entries of the form:
      group_key: ["alias1", "alias2", ...]
    and also handles a YAML-like block where a line ends with ':' and the following
    indented lines start with '-' entries. Returns a mapping {group_key: [aliases...]}.
    """
    out: Dict[str, List[str]] = {}
    if not path.exists():
        return out
    text = path.read_text(encoding='utf-8')
    # 1) bracketed lists on single lines
    import re
    br_re = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*:\s*\[(.*?)\]\s*$", re.M)
    for m in br_re.finditer(text):
        key = m.group(1).strip()
        list_part = m.group(2)
        # split by comma and strip quotes/spaces
        items = [it.strip().strip('"\'') for it in list_part.split(',') if it.strip()]
        out.setdefault(key, [])
        for it in items:
            if it:
                out[key].append(it.lower())

    # 2) indented hyphen lists following a 'key:' line
    lines = text.splitlines()
    cur = None
    for ln in lines:
        if not ln.strip():
            cur = None
            continue
        if ln.strip().endswith(':') and not ln.lstrip().startswith('-'):
            cur = ln.strip()[:-1].strip()
            continue
        if cur and ln.lstrip().startswith('-'):
            item = ln.lstrip().lstrip('-').strip()
            if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            if item:
                out.setdefault(cur, []).append(item.lower())
            continue
        # stop hyphen-list if we reach a non-indented, non-hyphen line
        if cur and not ln.startswith(' ') and not ln.startswith('\t'):
            cur = None

    return out


def process(apply: bool, batch: int, out: str | None = None, infer_oc: bool = False, infer_oc_fantasy: bool = False, limit: int = 0):
    fam, cam, f_tokens = load_franchise_maps(FR_DIR)
    # Precompute a combined vocabulary set once to avoid rebuilding it per variant
    base_vocab_set = set(fam.keys()) | set(cam.keys())
    for _fk, _tk in f_tokens.items():
        base_vocab_set |= (_tk.get('strong', set()) or set()) | (_tk.get('weak', set()) or set())
    proposals = []
    with get_session() as session:
        # Only consider variants that currently have no franchise. Avoid join/distinct here,
        # as it can be very expensive on large DBs. We'll quickly skip variants without files in the loop.
        q = session.query(Variant).filter(Variant.franchise.is_(None))
        try:
            total = q.count()
        except Exception:
            total = None
        if total is not None:
            print(f"Found {total} candidate variants (franchise is NULL).")
        else:
            print("Scanning candidate variants (franchise is NULL)...")
        offset = 0
        processed = 0
        while True:
            rows = q.limit(batch).offset(offset).all()
            if not rows:
                break
            # Enforce optional processing limit
            if limit and processed >= limit:
                break
            if limit and processed + len(rows) > limit:
                rows = rows[: max(0, limit - processed)]
            for v in rows:
                # Skip variants with no files/documents quickly (join avoided above for perf)
                try:
                    if not getattr(v, 'files', None):
                        processed += 1
                        continue
                except Exception:
                    pass
                # Prefer english_tokens when present to align with English vocab
                try:
                    eng = getattr(v, 'english_tokens', None)
                except Exception:
                    eng = None
                tokens = list(eng) if (isinstance(eng, list) and eng) else tokens_from_variant(session, v)
                if not tokens:
                    continue
                # Build vocab set for optional segmentation
                # Note: these maps are already lowercased aliases
                vocab_set = base_vocab_set

                # 1) split camelCase/alpha-digit
                split_tokens = []
                for t in tokens:
                    ts = split_mixed(t)
                    split_tokens.extend(ts)
                # 2) try vocab-driven segmentation for glued lowercase tokens
                segmented = []
                for t in split_tokens:
                    seg = segment_with_vocab(t, vocab_set)
                    segmented.extend(seg)
                # 3) bigrams
                token_list = expand_with_bigrams(segmented, QS_STOPWORDS)
                # Tabletop context gate: only treat as tabletop when explicit tabletop
                # hints are present AND there is no stronger franchise/character alias
                # evidence. This prevents blocking when we clearly have a known IP
                # (e.g., queens_blade: 'menace').
                has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
                # Treat ambiguous/stop aliases as insufficient evidence on their own
                def _is_valid_fr_alias(tok: str) -> bool:
                    if tok not in fam:
                        return False
                    frk = fam[tok]
                    if tok in (f_tokens.get(frk, {}).get('stop', set()) or set()):
                        return False
                    return True
                has_alias_evidence = any(_is_valid_fr_alias(t) for t in token_list) or any((t in cam) and (t not in AMBIGUOUS_ALIASES) for t in token_list)
                is_tabletop_ctx = has_tabletop_hint and not has_alias_evidence

                # Try a scoring pass to resolve collisions (prefers specific character forms)
                best_fr, best_char, best_score = choose_best_franchise(token_list, fam, cam, f_tokens)

                inferred = {
                    'franchise': None,
                    'character_hint': None,
                    'character_name': None,
                    'faction_hint': None,
                    'franchise_hints': [],
                    'normalization_warnings': [],
                    'token_version': None,
                }

                # count franchise alias matches
                alias_count = sum(1 for t in token_list if t in fam)
                has_char_any = any(t in cam for t in token_list)
                has_char_strong = False

                def short_or_numeric(tok: str) -> bool:
                    return shared_short_or_numeric(tok)

                def has_supporting_fr_tokens(fr_key: str, exclude_token: str | None = None) -> bool:
                    return shared_has_support(fr_key, token_list, fam, f_tokens, exclude_token=exclude_token)

                # Prefer scoring-derived decision when not tabletop-blocked
                if best_fr and not is_tabletop_ctx:
                    inferred['franchise'] = best_fr
                    if best_char:
                        inferred['character_name'] = best_char
                        inferred['character_hint'] = best_char

                # Prefer character matches that include canonical franchise
                # If a character alias is found, prefer to use it but treat very short
                # or numeric aliases as weak unless the franchise explicitly lists
                # the alias as a strong signal.
                for t in token_list:
                    if t in cam:
                        fr, canon = cam[t]
                        # If alias is ambiguous (e.g., 'angel') and lacks any
                        # explicit supporting franchise evidence, skip.
                        if t in AMBIGUOUS_ALIASES:
                            if (not fr) or (not has_supporting_fr_tokens(fr, exclude_token=t)):
                                continue
                        # If alias is short/numeric and we are in tabletop/faction context,
                        # ignore entirely to avoid false positives (e.g., '002', '2b').
                        if short_or_numeric(t) and is_tabletop_ctx:
                            continue
                        # If alias is short/numeric and lacks any explicit franchise tokens,
                        # treat as too weak to even set character.
                        if short_or_numeric(t) and (not fr or not has_supporting_fr_tokens(fr, exclude_token=t)):
                            continue
                        # record the hint token and canonical character name
                        inferred['character_hint'] = t
                        inferred['character_name'] = canon
                        # Determine strength for potential franchise assignment
                        f_tok = f_tokens.get(fr, {'strong': set(), 'weak': set()})
                        # Ambiguous aliases should not be considered strong purely by length
                        is_strong = (t in f_tok.get('strong', set())) or ((len(t) > 2 and not t.isdigit()) and (t not in AMBIGUOUS_ALIASES))
                        has_char_strong = has_char_strong or is_strong
                        if is_tabletop_ctx:
                            inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                        else:
                            if is_strong:
                                inferred['franchise'] = fr
                            else:
                                inferred.setdefault('normalization_warnings', []).append('character_alias_weak')
                        break

                # If no character-derived franchise, try franchise tokens
                if not inferred['franchise']:
                    for t in token_list:
                        if t in fam:
                            candidate_fr = fam[t]
                            f_tok = f_tokens.get(candidate_fr, {'strong': set(), 'weak': set()})
                            # Skip aliases explicitly marked as stop/conflicts for that franchise
                            if t in (f_tok.get('stop', set()) or set()):
                                continue
                            # Consider strong only when:
                            #  - token is explicitly a strong signal, OR
                            #  - we already have strong character evidence for this franchise, OR
                            #  - there is other supporting franchise evidence besides this token
                            def _has_support_for(fr_key: str, exclude_token: str | None = None) -> bool:
                                sigs = (f_tokens.get(fr_key, {}).get('strong', set()) or set()) | (f_tokens.get(fr_key, {}).get('weak', set()) or set())
                                for tt in token_list:
                                    if exclude_token and tt == exclude_token:
                                        continue
                                    if tt in sigs:
                                        return True
                                    if tt in fam and fam[tt] == fr_key and tt not in (f_tokens.get(fr_key, {}).get('stop', set()) or set()):
                                        return True
                                return False
                            strong = (t in f_tok.get('strong', set())) or has_char_strong or _has_support_for(candidate_fr, exclude_token=t)
                            if is_tabletop_ctx:
                                # Tabletop: do not populate faction from franchise evidence; keep as franchise hint only
                                inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                                if t not in (f_tok.get('stop', set()) or set()):
                                    if t not in inferred['franchise_hints']:
                                        inferred['franchise_hints'].append(t)
                                break
                            if strong:
                                # For non-tabletop strong matches, set franchise but
                                # do not populate a general faction hint.
                                inferred['franchise'] = candidate_fr
                                break
                            else:
                                # record as franchise hint only (avoid populating faction from franchise tokens)
                                if t not in (f_tok.get('stop', set()) or set()):
                                    if t not in inferred['franchise_hints']:
                                        inferred['franchise_hints'].append(t)
                                inferred.setdefault('normalization_warnings', []).append('faction_without_system')
                                break

                # If still no franchise and no character set, infer OC from path (strict) when enabled and not tabletop context
                if infer_oc and not inferred['character_name'] and not is_tabletop_ctx:
                    reserved = set(fam.keys()) | set(cam.keys())
                    for _fk, _tk in f_tokens.items():
                        reserved |= (_tk.get('strong', set()) or set()) | (_tk.get('weak', set()) or set()) | (_tk.get('stop', set()) or set())
                    reserved |= set(TABLETOP_HINTS) | set(QS_STOPWORDS)
                    cname, alias = infer_oc_from_path(v.rel_path or "", reserved, fantasy_filter=infer_oc_fantasy)
                    if cname:
                        inferred['character_name'] = cname
                        inferred['character_hint'] = alias
                        inferred.setdefault('normalization_warnings', []).append('original_character_inferred')

                # Set token_version from tokenmap if available (reuse normalize behavior)
                # We don't have load_tokenmap here; leave token_version None so other scripts set it.

                changed = apply_updates_to_variant(v, inferred, session, force=False)
                if changed:
                    proposals.append({'variant_id': v.id, 'rel_path': v.rel_path, 'changes': changed})
                processed += 1
            offset += batch

        print(f"Proposed updates for {len(proposals)} variants (dry-run={not apply}).")
        for p in proposals[:20]:
            print(json.dumps(p, indent=2))

        # Summary (dry-run): counts and top distributions
        try:
            total_props = len(proposals)
            with_franchise = sum(1 for p in proposals if 'franchise' in (p.get('changes') or {}))
            with_character = sum(1 for p in proposals if 'character_name' in (p.get('changes') or {}))
            with_aliases = sum(1 for p in proposals if 'character_aliases' in (p.get('changes') or {}))
            with_faction_hint = sum(1 for p in proposals if 'faction_general' in (p.get('changes') or {}))

            # Top franchises proposed
            from collections import Counter
            fr_counter = Counter((p['changes'].get('franchise') for p in proposals if p.get('changes') and p['changes'].get('franchise')))
            ch_counter = Counter((p['changes'].get('character_name') for p in proposals if p.get('changes') and p['changes'].get('character_name')))

            print("\n--- Summary ---")
            print(f"Total proposals: {total_props}")
            print(f"  • with franchise: {with_franchise}")
            print(f"  • with character_name: {with_character}")
            print(f"  • with character_aliases added: {with_aliases}")
            print(f"  • with faction_general hint: {with_faction_hint}")
            if fr_counter:
                top_fr = fr_counter.most_common(10)
                print("Top franchises:")
                for k, v in top_fr:
                    print(f"  - {k}: {v}")
            if ch_counter:
                top_ch = ch_counter.most_common(10)
                print("Top characters:")
                for k, v in top_ch:
                    print(f"  - {k}: {v}")

            # Optional: write JSON export when --out is provided
            if out:
                payload = {
                    "apply": bool(apply),
                    "total_candidates": total,
                    "summary": {
                        "total_proposals": total_props,
                        "with_franchise": with_franchise,
                        "with_character_name": with_character,
                        "with_character_aliases": with_aliases,
                        "with_faction_general_hint": with_faction_hint,
                        "top_franchises": dict(fr_counter.most_common(50)),
                        "top_characters": dict(ch_counter.most_common(50)),
                    },
                    "proposals": proposals,
                }
                # Ensure parent directory exists
                out_path = Path(out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
                print(f"\nWrote JSON export to: {out_path}")
        except Exception:
            # Keep the script resilient even if summary calculation fails
            pass

        # Important: building proposals above uses apply_updates_to_variant,
        # which mutates ORM objects in-memory. To ensure the apply phase
        # detects and commits real changes, roll back any in-memory changes
        # before proceeding with writes.
        try:
            session.rollback()
        except Exception:
            pass

    if apply and proposals:
            print('Applying updates to DB...')
            # Close the current session to avoid identity map contamination
            try:
                session.close()
            except Exception:
                pass
            # Re-run to apply in a fresh session
            with get_session() as write_sess:
                q_apply = write_sess.query(Variant).join(Variant.files).distinct().filter(Variant.franchise.is_(None))
                offset = 0
                processed_apply = 0
                while True:
                    rows = q_apply.limit(batch).offset(offset).all()
                    if not rows:
                        break
                    if limit and processed_apply >= limit:
                        break
                    if limit and processed_apply + len(rows) > limit:
                        rows = rows[: max(0, limit - processed_apply)]
                    any_changed = False
                    for v in rows:
                        try:
                            eng = getattr(v, 'english_tokens', None)
                        except Exception:
                            eng = None
                        tokens = list(eng) if (isinstance(eng, list) and eng) else tokens_from_variant(write_sess, v)
                        if not tokens:
                            continue
                        vocab_set = base_vocab_set

                        split_tokens = []
                        for t in tokens:
                            split_tokens.extend(split_mixed(t))
                        segmented = []
                        for t in split_tokens:
                            segmented.extend(segment_with_vocab(t, vocab_set))
                        token_list = expand_with_bigrams(segmented, QS_STOPWORDS)
                        has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
                        def _is_valid_fr_alias(tok: str) -> bool:
                            if tok not in fam:
                                return False
                            frk = fam[tok]
                            if tok in (f_tokens.get(frk, {}).get('stop', set()) or set()):
                                return False
                            return True
                        has_alias_evidence = any(_is_valid_fr_alias(t) for t in token_list) or any((t in cam) and (t not in AMBIGUOUS_ALIASES) for t in token_list)
                        is_tabletop_ctx = has_tabletop_hint and not has_alias_evidence

                        inferred = {
                            'franchise': None,
                            'character_hint': None,
                            'character_name': None,
                            'faction_hint': None,
                            'franchise_hints': [],
                            'normalization_warnings': [],
                            'token_version': None,
                        }
                        alias_count = sum(1 for t in token_list if t in fam)
                        has_char_strong = False

                        def short_or_numeric(tok: str) -> bool:
                            return shared_short_or_numeric(tok)

                        def has_supporting_fr_tokens(fr_key: str, exclude_token: str | None = None) -> bool:
                            return shared_has_support(fr_key, token_list, fam, f_tokens, exclude_token=exclude_token)

                        for t in token_list:
                            if t in cam:
                                fr, canon = cam[t]
                                # Skip ambiguous alias unless supporting franchise evidence exists
                                if t in AMBIGUOUS_ALIASES:
                                    if (not fr) or (not has_supporting_fr_tokens(fr, exclude_token=t)):
                                        continue
                                if short_or_numeric(t) and is_tabletop_ctx:
                                    continue
                                if short_or_numeric(t) and (not fr or not has_supporting_fr_tokens(fr, exclude_token=t)):
                                    continue
                                inferred['character_hint'] = t
                                inferred['character_name'] = canon
                                f_tok = f_tokens.get(fr, {'strong': set(), 'weak': set()})
                                is_strong = (t in f_tok.get('strong', set())) or ((len(t) > 2 and not t.isdigit()) and (t not in AMBIGUOUS_ALIASES))
                                has_char_strong = has_char_strong or is_strong
                                if is_tabletop_ctx:
                                    inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                                else:
                                    if is_strong:
                                        inferred['franchise'] = fr
                                    else:
                                        inferred.setdefault('normalization_warnings', []).append('character_alias_weak')
                                break

                        if not inferred['franchise']:
                            for t in token_list:
                                if t in fam:
                                    candidate_fr = fam[t]
                                    f_tok = f_tokens.get(candidate_fr, {'strong': set(), 'weak': set()})
                                    if t in (f_tok.get('stop', set()) or set()):
                                        continue
                                    def _has_support_for(fr_key: str, exclude_token: str | None = None) -> bool:
                                        sigs = (f_tokens.get(fr_key, {}).get('strong', set()) or set()) | (f_tokens.get(fr_key, {}).get('weak', set()) or set())
                                        for tt in token_list:
                                            if exclude_token and tt == exclude_token:
                                                continue
                                            if tt in sigs:
                                                return True
                                            if tt in fam and fam[tt] == fr_key and tt not in (f_tokens.get(fr_key, {}).get('stop', set()) or set()):
                                                return True
                                        return False
                                    strong = (t in f_tok.get('strong', set())) or has_char_strong or _has_support_for(candidate_fr, exclude_token=t)
                                    if is_tabletop_ctx:
                                        inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                                        if t not in (f_tok.get('stop', set()) or set()):
                                            if t not in inferred['franchise_hints']:
                                                inferred['franchise_hints'].append(t)
                                        break
                                    if strong:
                                        inferred['franchise'] = candidate_fr
                                        break
                                    else:
                                        # record as franchise hint only
                                        inferred.setdefault('normalization_warnings', []).append('faction_without_system')
                                        if t not in (f_tok.get('stop', set()) or set()):
                                            if t not in inferred['franchise_hints']:
                                                inferred['franchise_hints'].append(t)
                                        break

                        # If still no franchise and no character set, infer OC from path (strict) when enabled and not tabletop context
                        if infer_oc and not inferred['character_name'] and not is_tabletop_ctx:
                            reserved = set(fam.keys()) | set(cam.keys())
                            for _fk, _tk in f_tokens.items():
                                reserved |= (_tk.get('strong', set()) or set()) | (_tk.get('weak', set()) or set()) | (_tk.get('stop', set()) or set())
                            reserved |= set(TABLETOP_HINTS) | set(QS_STOPWORDS)
                            cname, alias = infer_oc_from_path(v.rel_path or "", reserved, fantasy_filter=infer_oc_fantasy)
                            if cname:
                                inferred['character_name'] = cname
                                inferred['character_hint'] = alias
                                inferred.setdefault('normalization_warnings', []).append('original_character_inferred')

                        changed = apply_updates_to_variant(v, inferred, write_sess, force=False)
                        if changed:
                            any_changed = True
                        processed_apply += 1
                    if any_changed:
                        write_sess.commit()
                    offset += batch
            print('Apply complete.')


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Match variants to franchise & characters from franchise manifests')
    ap.add_argument('--batch', type=int, default=200)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', type=str, help='Write dry-run proposals + summary to this JSON file')
    ap.add_argument('--infer-oc', action='store_true', help='Enable strict original-character inference from path folders (opt-in)')
    ap.add_argument('--infer-oc-fantasy', action='store_true', help='When inferring OC, only accept names that look fantasy-like (rarity/suffix heuristics)')
    ap.add_argument('--limit', type=int, default=0, help='Maximum number of variants to process (0 = no limit)')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    process(apply=args.apply, batch=args.batch, out=args.out, infer_oc=args.infer_oc, infer_oc_fantasy=args.infer_oc_fantasy, limit=max(0, int(getattr(args, 'limit', 0) or 0)))


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))

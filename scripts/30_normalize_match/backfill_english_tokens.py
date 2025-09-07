#!/usr/bin/env python3
"""Backfill Variant.english_tokens using curated YAML glossaries and romanization.

Dry-run by default; use --apply to write changes. Reports to --out JSON path.

Strategy:
 1) Detect token_locale (best-effort) if missing, using ASCII/CJK heuristics.
 2) Build a mapping table from vocab/i18n/*.yaml: generic.yaml + warhammer.yaml
 3) For each variant, construct a normalized token stream from raw_path_tokens or tokens_from_variant
 4) Longest-phrase-first replacement from the mapping; fallback to romanization for unknowns

This script is deliberately conservative and idempotent.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session, DB_URL  # type: ignore
from sqlalchemy import inspect as _sa_inspect  # type: ignore
import sqlalchemy as sa  # type: ignore
from db.models import Variant  # type: ignore
try:
    from db.models import Collection  # type: ignore
except Exception:  # pragma: no cover
    Collection = None  # type: ignore
from scripts.quick_scan import SPLIT_CHARS  # type: ignore
# Import via compatibility shim to avoid dotted path with numeric segment
from scripts.normalize_inventory import tokens_from_variant  # type: ignore

try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # PyYAML not available

# Optional ruamel.yaml (preferred if available)
try:
    from ruamel.yaml import YAML  # type: ignore
    _RU_YAML: Optional[object]
    _ru_yaml = YAML(typ='safe')
except Exception:
    _ru_yaml = None  # type: ignore

try:
    from unidecode import unidecode  # type: ignore
except Exception:
    # Fallback: strip diacritics via NFKD decomposition
    def unidecode(s: str) -> str:
        try:
            import unicodedata as _ud
            return ''.join(c for c in _ud.normalize('NFKD', s or '') if not _ud.combining(c))
        except Exception:
            return s or ''


@dataclass
class Glossary:
    # map phrase (lower, NFKC-ish) -> English replacement
    map: Dict[str, str]
    # phrases sorted by token length desc for longest-first matching
    phrases: List[List[str]]
    # language-specific key sets for locale refinement
    ja_keys: set[str]
    zh_keys: set[str]


def norm_text(s: str) -> str:
    try:
        import unicodedata as _ud
        s = _ud.normalize('NFKC', s or '')
    except Exception:
        s = s or ''
    return s.lower().strip()


def detect_locale_from_tokens(tokens: List[str]) -> Optional[str]:
    if not tokens:
        return None
    # If all ASCII, assume English
    if all(all(ord(c) < 128 for c in t) for t in tokens):
        return 'en'
    # Check for CJK scripts quickly
    def has_range(t: str, start: int, end: int) -> bool:
        return any(start <= ord(c) <= end for c in t)
    any_hira = any(has_range(t, 0x3040, 0x309F) for t in tokens)  # Hiragana
    any_kata = any(has_range(t, 0x30A0, 0x30FF) for t in tokens)  # Katakana
    if any_hira or any_kata:
        return 'ja'
    any_cjk = any(has_range(t, 0x4E00, 0x9FFF) for t in tokens)  # CJK Unified Ideographs
    if any_cjk:
        return 'zh'
    # Fallback: if contains extended Latin with diacritics, leave None (we'll still map common terms)
    return None


def load_glossaries() -> Glossary:
    """Load i18n glossaries using proper YAML parsing.

    Supports structures:
      - languages: <lang>: { mappings: { key: value, ... }, other_flat_keys: value }
      - top-level flat entries: key: value
    """
    vocab_dir = ROOT / 'vocab' / 'i18n'
    files = [vocab_dir / 'generic.yaml', vocab_dir / 'warhammer.yaml']
    mapping: Dict[str, str] = {}
    ja_keys: set[str] = set()
    zh_keys: set[str] = set()

    def add_entry(k: str, v: str) -> None:
        k2 = norm_text(str(k))
        v2 = str(v).strip()
        if not k2 or not v2:
            return
        mapping[k2] = v2

    for fp in files:
        if not fp.exists():
            continue
        data = None
        try:
            text = fp.read_text(encoding='utf-8')
            if _ru_yaml is not None:
                data = _ru_yaml.load(text)
            elif yaml is not None:
                data = yaml.safe_load(text)
        except Exception:
            data = None
        # Fallback to naive line parser if YAML unavailable/broken
        if data is None:
            text = fp.read_text(encoding='utf-8')
            for ln in text.splitlines():
                s = ln.strip()
                if not s or s.startswith('#') or s.startswith('languages:'):
                    continue
                m = re.match(r'^"?(?P<k>[^":]+)"?\s*:\s*(?P<v>.+?)\s*$', s)
                if m:
                    add_entry(m.group('k'), m.group('v'))
            continue

        # Properly parsed YAML
        if isinstance(data, dict):
            # 1) Top-level flat entries
            for k, v in list(data.items()):
                if k == 'languages':
                    continue
                if isinstance(v, (str, int, float)):
                    add_entry(k, v)
            # 2) languages.*
            langs = data.get('languages') if isinstance(data.get('languages'), dict) else None
            if isinstance(langs, dict):
                for lang_key, node in langs.items():
                    if not isinstance(node, dict):
                        # Some repos may put direct flat entries under languages
                        if isinstance(node, (str, int, float)):
                            add_entry(lang_key, node)
                        continue
                    # 2a) Mappings block
                    mapp = node.get('mappings')
                    if isinstance(mapp, dict):
                        for k, v in mapp.items():
                            if isinstance(v, (str, int, float)):
                                add_entry(k, v)
                                key_norm = norm_text(str(k))
                                if lang_key == 'ja':
                                    ja_keys.add(key_norm)
                                elif lang_key == 'zh':
                                    zh_keys.add(key_norm)
                    # 2b) Any other flat entries directly under the language node (mis-indented convenience keys)
                    for k, v in node.items():
                        if k == 'mappings':
                            continue
                        if isinstance(v, (str, int, float)):
                            add_entry(k, v)
                            key_norm2 = norm_text(str(k))
                            if lang_key == 'ja':
                                ja_keys.add(key_norm2)
                            elif lang_key == 'zh':
                                zh_keys.add(key_norm2)

    # Build phrases sorted by length desc
    phrases: List[List[str]] = []
    for key in mapping.keys():
        toks = [t for t in SPLIT_CHARS.split(key) if t]
        if toks:
            phrases.append(toks)
    phrases.sort(key=lambda ts: -len(ts))
    return Glossary(map=mapping, phrases=phrases, ja_keys=ja_keys, zh_keys=zh_keys)


def translate_tokens(tokens: List[str], glos: Glossary) -> List[str]:
    # Longest-phrase-first match over the token list
    out: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        matched = False
        # Limit phrase length to reasonable (up to 5 tokens)
        max_L = min(5, n - i)
        for L in range(max_L, 0, -1):
            phrase = tokens[i:i+L]
            key = ' '.join(phrase)
            if key in glos.map:
                out.append(glos.map[key])
                i += L
                matched = True
                break
            # also try underscore-joined form
            key2 = '_'.join(phrase)
            if key2 in glos.map:
                out.append(glos.map[key2])
                i += L
                matched = True
                break
        if not matched:
            # fallback: romanize single token if it contains non-ASCII
            t = tokens[i]
            # Spanish left/right abbreviations commonly concatenated in filenames
            tl = t.lower()
            if 'pierna' in tl:
                if ('izq' in tl) or ('izqda' in tl) or ('izqdo' in tl) or ('izquierda' in tl):
                    out.append('left leg'); i += 1; continue
                if ('drch' in tl) or ('der' in tl) or ('derecha' in tl) or ('derecho' in tl):
                    out.append('right leg'); i += 1; continue
            if 'brazo' in tl:
                if ('izq' in tl) or ('izqda' in tl) or ('izqdo' in tl) or ('izquierda' in tl):
                    out.append('left arm'); i += 1; continue
                if ('drch' in tl) or ('der' in tl) or ('derecha' in tl) or ('derecho' in tl):
                    out.append('right arm'); i += 1; continue
            # Try partial CJK phrase match inside the token (e.g., "内裤掀起1" contains "内裤" and "掀起")
            # Only for non-ASCII tokens to avoid false positives.
            if any(ord(c) > 127 for c in t):
                replaced = False
                # Prefer longer keys first to capture multi-char phrases
                for key, val in glos.map.items():
                    # skip ASCII-only keys to reduce noise
                    if all(ord(c) < 128 for c in key):
                        continue
                    if key and key in t:
                        out.append(val)
                        replaced = True
                        break
                if not replaced:
                    out.append(unidecode(t))
            else:
                out.append(t)
            i += 1
    # De-duplicate while preserving order
    dedup: List[str] = []
    seen = set()
    for t in out:
        tt = t.strip().lower()
        if tt and tt not in seen:
            seen.add(tt)
            dedup.append(tt)
    return dedup


def _split_words(s: str) -> List[str]:
    """Split a candidate label into words: separators + simple CamelCase boundaries."""
    if not s:
        return []
    s2 = s.replace('-', ' ').replace('_', ' ').replace('.', ' ').replace('\\', '/').split('/')[-1]
    parts: List[str] = []
    buf = ''
    for ch in s2:
        if ch.isalnum():
            # Split CamelCase: boundary when new uppercase follows lowercase
            if buf and ch.isupper() and (buf[-1].islower()):
                parts.append(buf)
                buf = ch
            else:
                buf += ch
        else:
            if buf:
                parts.append(buf)
                buf = ''
    if buf:
        parts.append(buf)
    # Split embedded digits boundaries a1B -> a 1 B
    out: List[str] = []
    for p in parts:
        cur = ''
        for i, c in enumerate(p):
            if i and ((c.isdigit() and cur and cur[-1].isalpha()) or (c.isalpha() and cur and cur[-1].isdigit())):
                out.append(cur)
                cur = c
            else:
                cur += c
        if cur:
            out.append(cur)
    return [w for w in out if w]


_BANNED_WORDS = {
    # Generic packaging/modifiers
    'supported','unsupported','presupported','pre','pre-supported','fixed','repair','repaired','test','sample','store','bundle','pack','set','parts','part','kit','stl','stls','obj','3mf','lychee','chitubox','cbddlp','step','fbx','blend','zip','lys','docs','info','images','renders','render','preview','infomodel','infoprint','printinfo','buildplate','builplate','zbrushztool','dm','stash','release','special','height',
    # Directions/anatomy often noise for variant label (move to inspector/drawer)
    'left','right','l','r','arm','leg','torso','head','body','backpack','cloak','weapon','sword','axe','shield','helmet','helm','cape','base','round','square','oval','mm','inch','in',
    # Common size/version tokens
    'v','v1','v2','v3','alt','alt1','alt2','alt3','ver','ver1','ver2','ver3','mk','mk1','mk2','mk3',
    # Generic descriptors that shouldn't headline labels
    'scale','uncut','cut','merged','merge','split','hollow','hollowed','solid','version','pose','poses'
}

# Generic bucket-like variant names that benefit from unit prefixing
_GENERIC_VARIANT_NAMES = {
    'bodies','body','heads','head','arms','arm','legs','leg','torsos','torso',
    'weapons','weapon','bits','accessories','poses','pose','helmets','helmet',
    'cloaks','cloak','shields','shield','spears','spear','swords','sword','backpacks','backpack'
}


def _clean_words(words: List[str]) -> List[str]:
    out: List[str] = []
    allow_short = {'of','to','in','vs','on','cg'}
    for w in words:
        wl = w.lower()
        # Drop pure numbers and mm sizes (e.g., 32, 32mm, 60x35)
        if wl.isdigit():
            continue
        if wl.endswith('mm') and wl[:-2].isdigit():
            continue
        if 'x' in wl:
            a, _, b = wl.partition('x')
            if a.isdigit() and b.isdigit():
                continue
        if wl in _BANNED_WORDS:
            continue
        # drop stray 1-2 letter alpha tokens (e.g., leftovers from id splits)
        if wl.isalpha() and len(wl) <= 2 and wl not in allow_short:
            continue
        # strip leading/trailing punctuation/noise
        wl = wl.strip('_-. ')
        if not wl:
            continue
        out.append(wl)
    return out


def _title_case(words: List[str]) -> str:
    if not words:
        return ''
    small = {'of','the','and','or','a','an','to','in','on'}
    acronyms = {'cg','opr','op','stl','obj','fbx','lys','cbddlp','3mf','nsfw','sfw'}
    out: List[str] = []
    for i, w in enumerate(words):
        if i and w in small:
            out.append(w)
        else:
            # Preserve known acronyms in uppercase (e.g., CG)
            if w in acronyms:
                out.append(w.upper())
            else:
                out.append(w[:1].upper() + w[1:])
    return ' '.join(out)


def _pretty_name(s: str) -> str:
    # Title-case designer or brand strings split on common separators
    parts = _clean_words(_split_words(s))
    return _title_case(parts)


def _candidate_from_eng_tokens(tokens: Optional[List[str]]) -> str:
    """Pick a strong display candidate from english_tokens, ignoring generic/unit noise.

    Conservative: return first non-generic token like 'garmokh'/'orae'.
    """
    if not tokens:
        return ''
    words = [str(t).strip().lower() for t in tokens if isinstance(t, str) and str(t).strip()]
    words = _clean_words(words)
    noise = set().union(
        _PACKAGING_SEGMENTS,
        {'freeguild','marshal','relic','envoy','general','on','and','the','of','base','full','square','stl','supported','unsupported'}
    )
    for w in words:
        if w not in noise:
            return _title_case([w])
    return ''


def _strip_noise_tokens(words: List[str]) -> List[str]:
    noise = set().union(
        _PACKAGING_SEGMENTS,
        {'base','full','square','round','oval','the','of','and','on','by'}
    )
    # Preserve a leading 'the' when followed by at least one non-noise token (e.g., 'The Wretch')
    if words and words[0] == 'the':
        tail = [w for w in words[1:] if w not in noise]
        if tail:
            return ['the'] + tail
        return tail
    return [w for w in words if w not in noise]


_PACKAGING_SEGMENTS = {
    'supported','unsupported','presupported','lys','lychee','stl','stls','32mm','75mm','32','75','cg','nsfw','sfw',
}

# Non-specific container folder names; if a segment is exactly one of these, prefer named children
_CONTAINER_SEGMENTS = {
    'characters','character','heroes','lone heroes','units','unit','troops','infantry','cavalry','combined','bundle','set','sets','kit','kits','folders','collection','collections','misc','various','others','assortment','lone','heroes'
}


def _best_named_segment_from_path(relp: str) -> str:
    p = (relp or '').replace('\\', '/').strip('/')
    if not p:
        return ''
    segs = [s for s in p.split('/') if s]
    # skip archive file segments
    def is_packaging(seg: str) -> bool:
        s = seg.strip().lower()
        base = s.rsplit('.', 1)[0]
        if s.endswith(('.zip','.rar','.7z','.7zip')):
            return True
        if base in _PACKAGING_SEGMENTS:
            return True
        # Any segment containing 'support' (captures supported/unsupported, even with typos)
        if ('support' in s) and (' - ' not in seg):
            return True
        # exact packaging folder names
        if s in {'.ds_store','__macosx','supported','unsupported','stl','stls','lys','lychee'}:
            return True
        # pure numbers or mm sizes
        if s.isdigit() or (s.endswith('mm') and s[:-2].isdigit()):
            return True
        return False
    def looks_like_name(tokens: List[str]) -> bool:
        if not tokens:
            return False
        generic = set().union(_GENERIC_VARIANT_NAMES, _BANNED_WORDS)
        # At least one non-generic alpha token
        return any(t.isalpha() and t not in generic for t in tokens)

    def score(seg: str, idx: int) -> int:
        s = seg.strip()
        if is_packaging(s):
            return -999
        toks = _clean_words(_split_words(s))
        if not toks:
            return -999
        sc = 0
        if '-' in s:
            sc += 3
            # Extra boost for explicit brand - model style labels
            if re.search(r'\s-\s', s):
                sc += 6
        # prefer explicit mount/rider connector phrases
        if re.search(r'\bon\b', s, flags=re.I):
            sc += 4
        # prefer comma-separated proper names (e.g., "Allard, Mercia King")
        if ',' in s and re.search(r'[A-Za-z]', s):
            sc += 5
        # slight boost for numeric ordering prefixes like '17.'
        if re.match(r'^\s*\d+[\.-]?\s*', s):
            sc += 2
        # boost for segments with multiple capitalized tokens (proper-name-ish)
        caps = re.findall(r'\b([A-Z][a-z]+|[A-Z]{2,})\b', s)
        small = {'Of','The','And','Or','A','An','To','In','On'}
        cap_count = sum(1 for t in caps if t not in small)
        if cap_count >= 2:
            sc += 3
        # honorific/title hints
        if re.search(r'\b(sir|lord|lady|king|queen|marshal|captain|general)\b', s, flags=re.I):
            sc += 2
        if re.search(r'[a-zA-Z]', s):
            sc += 2
        # reward moderate-length names; don't penalize 5-6 word names
        if 1 <= len(toks) <= 6:
            sc += 2
        elif 7 <= len(toks) <= 9:
            sc += 1
        # penalize brand/month folders
        if any(t in _MONTHS for t in [t.title() for t in toks]):
            sc -= 2
        if any(t in {'dm','stash','release'} for t in toks):
            sc -= 2
        # penalize generic container segments
        if s.strip().lower() in _CONTAINER_SEGMENTS:
            sc -= 20
        # boost leaf that looks like a proper name (e.g., Blagomir The Silent)
        if idx == len(segs) - 1 and looks_like_name(toks):
            sc += 8
        # if this segment is hyphen-delimited and the rightmost component looks like a name, boost
        if '-' in s:
            parts = [p.strip() for p in re.split(r'\s*-\s*', s) if p.strip()]
            if parts:
                lastp = parts[-1]
                toksp = _clean_words(_split_words(lastp))
                if looks_like_name(toksp):
                    sc += 4
        # if parent is a container and this looks like a name, boost strongly
        if idx > 0:
            parent = segs[idx-1].strip().lower()
            if parent in _CONTAINER_SEGMENTS and looks_like_name(toks):
                sc += 10
        # prefer deeper segments
        sc += idx * 2
        return sc
    best = ''
    best_score = -1000
    for i, seg in enumerate(segs):
        sc = score(seg, i)
        # On ties, prefer later (deeper) segments
        if sc >= best_score:
            best_score = sc
            best = seg
    if not best:
        return ''
    cleaned = re.sub(r'\s*-\s*(supported|unsupported)\s*$', '', best, flags=re.I)
    return cleaned


_MONTHS = {m.lower() for m in (
    'January','February','March','April','May','June','July','August','September','October','November','December',
    'Jan','Feb','Mar','Apr','Jun','Jul','Aug','Sep','Sept','Oct','Nov','Dec'
)}

def _looks_like_proper_name(label: str) -> bool:
    s = (label or '').strip()
    if not s:
        return False
    # Comma-separated names are likely proper: e.g., "Allard, Mercia King"
    if ',' in s and re.search(r'[A-Za-z]', s):
        return True
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return False
    small = {'of','the','and','or','a','an','to','in','on'}
    cap_count = sum(1 for t in toks if t[:1].isupper() and t.lower() not in small)
    return cap_count >= 2


def _choose_collection_name(v_obj, coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None) -> str:
    # Prefer explicit theme; fallback to original label
    parts: List[str] = []
    try:
        theme = (getattr(v_obj, 'collection_theme', None) or '').strip()
    except Exception:
        theme = ''
    # If a collection lookup is provided and collection_id is numeric, prefer DB theme/label
    if coll_meta is not None:
        try:
            cid_raw = getattr(v_obj, 'collection_id', None)
            if cid_raw is not None:
                # handle string ids that are digits
                if isinstance(cid_raw, str) and cid_raw.isdigit():
                    cid = int(cid_raw)
                elif isinstance(cid_raw, int):
                    cid = cid_raw
                else:
                    cid = None
                if isinstance(cid, int) and cid in coll_meta:
                    meta = coll_meta[cid]
                    # theme preferred, else original_label
                    nm = (meta.get('theme') or meta.get('original_label') or '').strip()
                    if nm:
                        return _title_case(_clean_words(_split_words(nm)))
        except Exception:
            pass
    try:
        orig = (getattr(v_obj, 'collection_original_label', None) or '').strip()
    except Exception:
        orig = ''
    # If theme looks substantive (multi-word), prefer it; otherwise parse from original label
    if theme and (len(theme) >= 6) and (' ' in theme):
        return _title_case(_clean_words(_split_words(theme)))
    txt = orig
    if not txt:
        return ''
    # Drop leading brand in parentheses, e.g., (DM Stash)
    txt = re.sub(r'^\([^)]*\)\s*', '', txt).strip()
    # Split on hyphens and take the last human segment
    parts = [t.strip() for t in re.split(r'[-–—]+', txt) if t.strip()]
    cand = ''
    for t in reversed(parts):
        if re.search(r'[a-zA-Z]', t):
            cand = t
            break
    if not cand:
        cand = txt
    return _title_case(_clean_words(_split_words(cand)))


def _choose_thing_name(v_obj, glos: Glossary, eng_tokens: Optional[List[str]], coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None) -> str:
    # 1) Character name (if present)
    try:
        char = (getattr(v_obj, 'character_name', None) or '').strip()
    except Exception:
        char = ''
    if char:
        return _title_case(_clean_words(_split_words(char)))
    # Helper to compare names after cleaning
    def _norm(s: str) -> str:
        return ' '.join(_clean_words(_split_words(s)))
    # Attempt to derive a variant label from rel_path/filename first
    try:
        relp = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp = ''
    # Early: if any path segment contains a comma-separated proper name, preserve it verbatim
    if relp:
        _segs_preserve = [s for s in relp.replace('\\','/').split('/') if s]
        for s in reversed(_segs_preserve):
            s_stripped = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
            if (',' in s_stripped) and re.search(r'[A-Za-z]', s_stripped):
                # Preserve verbatim (minus ordering prefix) to keep commas and small words
                return s_stripped
    seg = _best_named_segment_from_path(relp)
    variant_label = ''
    if seg:
        # Preserve comma-separated proper names, e.g., "17. Allard, Mercia King" -> "Allard, Mercia King"
        seg_pres = re.sub(r'^\s*\d+[\.-]?\s*', '', seg).strip()
        if ',' in seg_pres and re.search(r'[A-Za-z]', seg_pres):
            # Preserve original punctuation and articles
            return seg_pres
        # If segment contains hyphen-delimited components, prefer the rightmost 'model name' part
        parts_h = [p.strip() for p in re.split(r'\s*-\s*', seg) if p.strip()]
        if len(parts_h) >= 2:
            # Determine collection name to drop if present
            coll_name = _choose_collection_name(v_obj, coll_meta)
            coll_norm = _norm(coll_name) if coll_name else ''
            def is_brand(p: str) -> bool:
                pn = _norm(p)
                if pn in {'cast n play','castnplay','dm stash','dm'}:
                    return True
                # Heuristic: vendor-like keywords
                toksb = set(_clean_words(_split_words(pn)))
                brand_hits = {'studio','studios','3d','miniature','miniatures','atelier','workshop','forge','labs','lab','models','model','printing','print','prints','patreon'}
                return bool(toksb & brand_hits)
            # Choose rightmost non-brand part as the core pick
            candidates = [p for p in parts_h if not is_brand(p) and (_norm(p) != coll_norm)]
            pick = candidates[-1] if candidates else parts_h[-1]
            words_p = _clean_words(_split_words(pick))
            mapped_p = translate_tokens(words_p, glos) if words_p else []
            label_core = _title_case((mapped_p or words_p)[:8]) if (mapped_p or words_p) else ''
            # Optionally include a meaningful left prefix if present and not a brand
            prefix_label = ''
            if len(parts_h) >= 2:
                # Find the left neighbor of the chosen pick within parts_h
                try:
                    idx_pick = parts_h.index(pick)
                except ValueError:
                    idx_pick = len(parts_h) - 1
                if idx_pick > 0:
                    left = parts_h[idx_pick - 1]
                    if left and (not is_brand(left)) and (_norm(left) != coll_norm):
                        words_l = _clean_words(_split_words(left))
                        mapped_l = translate_tokens(words_l, glos) if words_l else []
                        prefix_label = _title_case((mapped_l or words_l)[:6]) if (mapped_l or words_l) else ''
            if label_core and not variant_label:
                variant_label = f"{prefix_label} - {label_core}".strip(' -') if prefix_label else label_core
        if not variant_label:
            words = _clean_words(_split_words(seg))
            mapped = translate_tokens(words, glos) if words else []
            if mapped or words:
                # If this looks like a multi-word name (>=2 tokens), keep more tokens
                base = mapped or words
                keep_n = 8 if len(base) >= 2 else 5
                variant_label = _title_case(base[:keep_n])
        # Guard: if variant_label collapsed to a single token but the chosen segment
        # contains a clear two-word proper name, rebuild from the first two tokens.
        v_words = _clean_words(_split_words(variant_label))
        if variant_label and len(v_words) == 1:
            seg_words = _clean_words(_split_words(seg))
            seg_mapped = translate_tokens(seg_words, glos) if seg_words else []
            seg_base = seg_mapped or seg_words
            # Require at least two alpha tokens to avoid adding generic buckets
            if len([t for t in seg_base if t.isalpha()]) >= 2:
                variant_label = _title_case(seg_base[:2])
    try:
        fname = getattr(v_obj, 'filename', None) or ''
    except Exception:
        fname = ''
    if fname:
        stem = fname.rsplit('.', 1)[0]
        words2 = _clean_words(_split_words(stem))
        mapped2 = translate_tokens(words2, glos) if words2 else []
        if mapped2 and not variant_label:
            variant_label = _title_case(mapped2[:5])
    # Fetch codex unit name for comparison/fallback
    try:
        unit = (getattr(v_obj, 'codex_unit_name', None) or '').strip()
    except Exception:
        unit = ''
    unit_label = _title_case(_clean_words(_split_words(unit))) if unit else ''
    # If we have a variant label and it's not effectively the same as the unit, prefer the variant label
    if variant_label:
        # If the variant label merely equals the unit folder name (the second path segment), try to refine
        try:
            relp_seg = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp_seg = ''
        pseg = relp_seg.replace('\\', '/').strip('/')
        segs_var = [s for s in pseg.split('/') if s]
        unit_folder_norm = ''
        if len(segs_var) >= 2:
            unit_folder_norm = _norm(segs_var[1])
        if unit_folder_norm and (_norm(variant_label) == unit_folder_norm):
            last_u = segs_var[-1]
            if last_u.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs_var) >= 2:
                last_u = segs_var[-2]
            m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
            if m_name:
                core = m_name.group(1)
                w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                cand_core = _title_case(w_core[:2]) if w_core else ''
                if cand_core and (_norm(cand_core) != unit_folder_norm):
                    return cand_core
            w3 = _strip_noise_tokens(_clean_words(_split_words(last_u)))
            m3 = translate_tokens(w3, glos) if w3 else []
            base3 = m3 or w3
            cand3 = _title_case(base3[:8]) if base3 else ''
            if cand3 and (_norm(cand3) != unit_folder_norm):
                return cand3
            # Only consider an english-tokens fallback for explicit STL supported/unsupported patterns
            lower_last = last_u.lower()
            if ('stl' in lower_last) or ('supported' in lower_last) or ('unsupported' in lower_last):
                cand_tok0 = _candidate_from_eng_tokens(eng_tokens)
                if cand_tok0 and (_norm(cand_tok0) != unit_folder_norm):
                    return cand_tok0
        if unit_label and (_norm(variant_label) == _norm(unit_label)):
            # Try to derive a more specific name from deeper path segments
            try:
                relp_u = getattr(v_obj, 'rel_path', '') or ''
            except Exception:
                relp_u = ''
            pu = relp_u.replace('\\', '/').strip('/')
            segs_u = [s for s in pu.split('/') if s]
            if segs_u:
                last_u = segs_u[-1]
                if last_u.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs_u) >= 2:
                    last_u = segs_u[-2]
                # Special-case: patterns like 'STL_Garmokh_Supported' or 'STL_Orae_Unsupported'
                m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
                if m_name:
                    core = m_name.group(1)
                    w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                    cand_core = _title_case(w_core[:2]) if w_core else ''
                    if cand_core and (_norm(cand_core) != _norm(unit_label)):
                        return cand_core
                # Generic: derive from last segment words
                w3 = _strip_noise_tokens(_clean_words(_split_words(last_u)))
                m3 = translate_tokens(w3, glos) if w3 else []
                base3 = m3 or w3
                cand3 = _title_case(base3[:8]) if base3 else ''
                if cand3 and (_norm(cand3) != _norm(unit_label)):
                    return cand3
            # Last resort: pick a strong proper token from english_tokens (e.g., Garmokh/Orae)
            # Only allow this in explicit STL supported/unsupported contexts to avoid shortening proper names
            last_u2 = segs_u[-1] if segs_u else ''
            low2 = (last_u2 or '').lower()
            if ('stl' in low2) or ('supported' in low2) or ('unsupported' in low2):
                cand_tok = _candidate_from_eng_tokens(eng_tokens)
                if cand_tok and (_norm(cand_tok) != _norm(unit_label)):
                    return cand_tok
            return unit_label
        return variant_label
    # If no variant label, fall back to unit name when present
    if unit_label:
        return unit_label
    # 4) Fallback to english tokens
    toks = [str(t).strip() for t in (eng_tokens or []) if isinstance(t, str) and str(t).strip()]
    toks = _clean_words(toks)[:5]
    return _title_case(toks)


def build_ui_display(v_obj, glos: Glossary, eng_tokens: Optional[List[str]] = None, coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None) -> str:
    """Build a semantic display name using character/unit, collection, and designer context.

    Examples:
      - Catwoman by Azerama
      - Guardians of the Fey: Erimilia
      - Guardians of the Fey: Bonded Souls
      - Guardians of the Fey: September (for monthly collection releases)
    """
    collection = _choose_collection_name(v_obj, coll_meta)
    # Earliest guard: if any rel_path segment contains a comma-separated proper name, preserve it verbatim
    try:
        relp0 = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp0 = ''
    if relp0:
        segs0 = [s for s in relp0.replace('\\','/').split('/') if s]
        for s in reversed(segs0):
            s_clean = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
            if (',' in s_clean) and re.search(r'[A-Za-z]', s_clean):
                # Return immediately with collection prefix if applicable
                if collection and (' '.join(_clean_words(_split_words(s_clean))) != ' '.join(_clean_words(_split_words(collection)))):
                    return f"{collection}: {s_clean}"
                return s_clean
    thing = _choose_thing_name(v_obj, glos, eng_tokens, coll_meta)
    # Strong preservation: if any path segment contains a comma-separated proper name,
    # use it directly as the 'thing' to keep commas and small words (e.g., 'Ushoran, Mortarch of Delusion').
    try:
        relp_comm = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp_comm = ''
    if relp_comm:
        segs_comm = [s for s in relp_comm.replace('\\','/').split('/') if s]
        for s in reversed(segs_comm):
            s2 = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
            if (',' in s2) and re.search(r'[A-Za-z]', s2):
                thing = s2
                break
    # Strong hint: if deepest path segment starts with an ordering number like '6. Foo Bar', prefer that label
    try:
        relp_num = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp_num = ''
    if relp_num:
        pnum = relp_num.replace('\\', '/').strip('/')
        segsnum = [s for s in pnum.split('/') if s]
        if segsnum:
            lastnum = segsnum[-1]
            if lastnum.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segsnum) >= 2:
                lastnum = segsnum[-2]
            m = re.match(r'^\s*\d+[\.-]?\s*(.+)$', lastnum)
            if m:
                raw = m.group(1).strip()
                wn = _clean_words(_split_words(raw))
                mn = translate_tokens(wn, glos) if wn else []
                candn = _title_case((mn or wn)[:8]) if (mn or wn) else ''
                def _normx(s: str) -> str:
                    return ' '.join(_clean_words(_split_words(s or '')))
                if candn and ((_normx(candn) != _normx(collection))):
                    thing = candn
    # If nothing derived yet, attempt to build from deepest path segment
    if not thing:
        try:
            relp = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp = ''
        p0 = relp.replace('\\', '/').strip('/')
        segs0 = [s for s in p0.split('/') if s]
        if segs0:
            last0 = segs0[-1]
            if last0.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs0) >= 2:
                last0 = segs0[-2]
            w0 = _strip_noise_tokens(_clean_words(_split_words(last0)))
            m0 = translate_tokens(w0, glos) if w0 else []
            base0 = m0 or w0
            if base0:
                thing = _title_case(base0[:8])
    # If we have a collection and the variant's deepest segment follows a brand - collection - model pattern,
    # recompute 'thing' from the last hyphen part to avoid duplicates like "Hidden Crypt: Cast Play Hidden Crypt Undying".
    if collection:
        try:
            relp = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp = ''
        p = relp.replace('\\', '/').strip('/')
        segs = [s for s in p.split('/') if s]
        if segs:
            last = segs[-1]
            # If last is packaging, consider previous
            if last.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs) >= 2:
                last = segs[-2]
            if ' - ' in last or '-' in last:
                parts_h = [x.strip() for x in re.split(r'\s*-\s*', last) if x.strip()]
                if len(parts_h) >= 2:
                    def _norm(s: str) -> str:
                        return ' '.join(_clean_words(_split_words(s)))
                    coll_norm = _norm(collection)
                    def is_brand(s: str) -> bool:
                        sn = _norm(s)
                        return sn in {'cast n play','castnplay','dm stash','dm'}
                    cands = [x for x in parts_h if not is_brand(x) and (_norm(x) != coll_norm)]
                    pick = cands[-1] if cands else parts_h[-1]
                    w = _strip_noise_tokens(_clean_words(_split_words(pick)))
                    mapped = translate_tokens(w, glos) if w else []
                    if mapped:
                        thing = _title_case(mapped[:5])
            # If chosen thing still collapses to the collection/unit, attempt to rebuild from the deepest segment
            try:
                unit_chk = (getattr(v_obj, 'codex_unit_name', None) or '').strip()
            except Exception:
                unit_chk = ''
            def _norm2(s: str) -> str:
                return ' '.join(_clean_words(_split_words(s or '')))
            if thing and ((_norm2(thing) == _norm2(collection)) or (unit_chk and _norm2(thing) == _norm2(unit_chk))):
                w2 = _strip_noise_tokens(_clean_words(_split_words(last)))
                mapped2 = translate_tokens(w2, glos) if w2 else []
                if mapped2 or w2:
                    # Keep more tokens for descriptive phrases
                    base2 = mapped2 or w2
                    thing2 = _title_case(base2[:8])
                    if thing2 and (_norm2(thing2) != _norm2(collection)):
                        thing = thing2
    # If the variant label is a generic bucket (e.g., Bodies), prefix with unit name if available
    try:
        unit_raw = (getattr(v_obj, 'codex_unit_name', None) or '').strip()
    except Exception:
        unit_raw = ''
    unit_label = _title_case(_clean_words(_split_words(unit_raw))) if unit_raw else ''
    # If the deepest path segment is a generic bucket (Bodies/Helmets/etc.) and the current
    # chosen label omits it (e.g., equals the collection or another folder), include the bucket
    # as a suffix using Unit or Collection as the prefix for clarity.
    try:
        relp_last = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp_last = ''
    if relp_last:
        p_last = relp_last.replace('\\', '/').strip('/')
        segs_last = [s for s in p_last.split('/') if s]
        if segs_last:
            last_seg = segs_last[-1]
            if last_seg.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs_last) >= 2:
                last_seg = segs_last[-2]
            toks_last = _strip_noise_tokens(_clean_words(_split_words(last_seg)))
            # Treat 1-3 token segments entirely within the generic bucket set as a bucket suffix
            if toks_last and (all(t in _GENERIC_VARIANT_NAMES for t in toks_last)):
                bucket = _title_case(toks_last[:6])
                def _norm_b(s: str) -> str:
                    return ' '.join(_clean_words(_split_words(s or '')))
                # Only add when bucket not already part of the chosen label
                if bucket and (not thing or bucket.lower() not in (thing or '').lower()):
                    if unit_label:
                        thing = f"{unit_label}: {bucket}"
                    elif collection:
                        thing = f"{collection}: {bucket}"
                    else:
                        thing = bucket
    # If the derived thing collapses to the unit label, try to rebuild from path last segment
    if thing and unit_label:
        def _norm_u(s: str) -> str:
            return ' '.join(_clean_words(_split_words(s or '')))
        if _norm_u(thing) == _norm_u(unit_label):
            try:
                relp_u = getattr(v_obj, 'rel_path', '') or ''
            except Exception:
                relp_u = ''
            p_u = relp_u.replace('\\', '/').strip('/')
            segs_u = [s for s in p_u.split('/') if s]
            if segs_u:
                last_u = segs_u[-1]
                if last_u.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segs_u) >= 2:
                    last_u = segs_u[-2]
                # Special-case: segments like 'STL_Garmokh_Supported' -> 'Garmokh'
                m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
                if m_name:
                    core = m_name.group(1)
                    w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                    cand_core = _title_case(w_core[:2]) if w_core else ''
                    if cand_core and (_norm_u(cand_core) != _norm_u(unit_label)):
                        thing = cand_core
                if not thing or _norm_u(thing) == _norm_u(unit_label):
                    # Fallback: derive from split words of last segment
                    w_u = _strip_noise_tokens(_clean_words(_split_words(last_u)))
                    m_u = translate_tokens(w_u, glos) if w_u else []
                    base_u = m_u or w_u
                    cand = _title_case(base_u[:8]) if base_u else ''
                    if cand and (_norm_u(cand) != _norm_u(unit_label)):
                        thing = cand
            # If still equal to unit, consider english_tokens only for STL supported/unsupported patterns
            if _norm_u(thing) == _norm_u(unit_label):
                last_u2 = segs_u[-1] if segs_u else ''
                low2 = (last_u2 or '').lower()
                if ('stl' in low2) or ('supported' in low2) or ('unsupported' in low2):
                    cand2 = _candidate_from_eng_tokens(eng_tokens)
                    if cand2 and (_norm_u(cand2) != _norm_u(unit_label)):
                        thing = cand2
    # If no unit label but 'thing' equals the unit folder name (2nd segment), try a conservative token candidate
    if thing and not unit_label:
        try:
            relp_f = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp_f = ''
        pf = relp_f.replace('\\', '/').strip('/')
        segsf = [s for s in pf.split('/') if s]
        if len(segsf) >= 2:
            unit_folder = segsf[1]
            def _norm_f(s: str) -> str:
                return ' '.join(_clean_words(_split_words(s or '')))
            if _norm_f(thing) == _norm_f(unit_folder):
                # Prefer specific core name from STL folder pattern; avoid generic fallbacks otherwise
                lastf = segsf[-1]
                if lastf.strip().lower() in {'supported','unsupported','stl','stls','lys','lychee'} and len(segsf) >= 2:
                    lastf = segsf[-2]
                m_namef = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', lastf)
                if m_namef:
                    coref = m_namef.group(1)
                    w_coref = _strip_noise_tokens(_clean_words(_split_words(coref)))
                    cand_coref = _title_case(w_coref[:2]) if w_coref else ''
                    if cand_coref and (_norm_f(cand_coref) != _norm_f(unit_folder)):
                        thing = cand_coref
                if _norm_f(thing) == _norm_f(unit_folder):
                    lowf = (lastf or '').lower()
                    if ('stl' in lowf) or ('supported' in lowf) or ('unsupported' in lowf):
                        cand_tok2 = _candidate_from_eng_tokens(eng_tokens)
                        if cand_tok2 and (_norm_f(cand_tok2) != _norm_f(unit_folder)):
                            thing = cand_tok2
    if thing and unit_label:
        thing_norm = thing.strip().lower()
        if thing_norm in _GENERIC_VARIANT_NAMES:
            thing = f"{unit_label}: {thing}"
        else:
            toks_thing = _clean_words(_split_words(thing_norm))
            if toks_thing and all(t in _GENERIC_VARIANT_NAMES for t in toks_thing):
                thing = f"{unit_label}: {thing}"

    try:
        designer_raw = (getattr(v_obj, 'designer', None) or '').strip()
    except Exception:
        designer_raw = ''
    designer = _pretty_name(designer_raw) if designer_raw else ''

    # If the derived thing is a month-only token and we have collection, keep as month label under collection
    if thing and thing.lower() in _MONTHS and collection:
        return f"{collection}: {thing}"

    # Prefer collection: thing when collection is present and thing is non-empty
    # This ensures items keep their collection prefix instead of returning only the proper name.
    def _norm_disp(s: str) -> str:
        return ' '.join(_clean_words(_split_words(s or '')))
    if collection and thing:
        if _norm_disp(thing) != _norm_disp(collection):
            return f"{collection}: {thing}"
        # If equal, just return the collection
        return collection

    # Preserve comma-separated proper names verbatim at the end as well
    if thing and (',' in thing):
        return thing

    # If no collection context, allow returning a proper name directly
    if thing and _looks_like_proper_name(thing):
        return thing

    # Otherwise prefer thing by designer (e.g., Catwoman by Azerama)
    if thing and designer:
        return f"{thing} by {designer}"

    # Fallbacks
    if thing:
        return thing
    if collection:
        return collection
    # last resort: designer-only (not ideal, but better than empty)
    if designer:
        return designer
    return ''
    # 1) From rel_path last segment
    try:
        relp = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp = ''
    words = _split_words(relp)
    words = _clean_words(words)
    # Map phrases of up to 3 tokens via glossary
    if words:
        # translate_tokens expects a token list and replaces phrases; we restrict to our words
        mapped = translate_tokens(words, glos) or words
        # Keep first 5 words to avoid dumps
        mapped = mapped[:5]
        name = _title_case(mapped)
        if name:
            return name
    # 2) From filename stem
    try:
        fname = getattr(v_obj, 'filename', None) or ''
    except Exception:
        fname = ''
    if fname:
        stem = fname.rsplit('.', 1)[0]
        words2 = _clean_words(_split_words(stem))
        if words2:
            mapped2 = translate_tokens(words2, glos) or words2
            mapped2 = mapped2[:5]
            name2 = _title_case(mapped2)
            if name2:
                return name2
    # 3) Fallback: english_tokens (first few)
    toks = [str(t).strip() for t in (eng_tokens or []) if isinstance(t, str) and str(t).strip()]
    toks = _clean_words(toks)[:5]
    return _title_case(toks)


def run(batch: int, limit: int, ids: Optional[List[int]], apply: bool, out: Optional[str], force: bool, materialize_ui: bool, tabletop_only: bool = False) -> None:
    glos = load_glossaries()
    proposals: List[Dict[str, object]] = []
    changed_count = 0
    examined = 0
    with get_session() as session:
        # Report actual bound DB URL (may differ from imported DB_URL if reconfigured at runtime)
        try:
            print(f"Using database: {str(session.bind.url)}")
        except Exception:
            print(f"Using database: {DB_URL}")
        # (collection metadata lookup will be built after variants are loaded)
        # Ensure schema exists (ephemeral test DBs): create ORM tables if variant table is missing
        try:
            insp0 = _sa_inspect(session.bind)
            tables = set(insp0.get_table_names())
            if 'variant' not in tables:
                try:
                    if str(ROOT) not in sys.path:
                        sys.path.insert(0, str(ROOT))
                    from db.models import Base as _Base  # type: ignore
                    _Base.metadata.create_all(bind=session.bind)
                    # refresh inspector after DDL
                    insp0 = _sa_inspect(session.bind)
                except Exception:
                    pass
        except Exception:
            pass
        # Determine available columns to avoid selecting missing ones
        try:
            insp = _sa_inspect(session.bind)
            tables_now = set(insp.get_table_names())
            if 'variant' not in tables_now:
                # Last-ditch: create schema and refresh inspector
                try:
                    from db.models import Base as _Base  # type: ignore
                    _Base.metadata.create_all(bind=session.bind)
                    insp = _sa_inspect(session.bind)
                except Exception:
                    pass
            vcols = {c['name'] for c in insp.get_columns('variant')} if 'variant' in set(insp.get_table_names()) else set()
        except Exception:
            vcols = set()
        # Build an ORM query for Variants and fetch eagerly to avoid driver quirks
        from sqlalchemy.orm import load_only as _load_only  # type: ignore
        load_cols = [Variant.id, Variant.rel_path, Variant.filename]
        if 'raw_path_tokens' in vcols:
            load_cols.append(Variant.raw_path_tokens)
        if 'english_tokens' in vcols:
            load_cols.append(Variant.english_tokens)
        if 'codex_unit_name' in vcols:
            load_cols.append(Variant.codex_unit_name)
        if 'token_locale' in vcols:
            load_cols.append(Variant.token_locale)
        if 'ui_display_en' in vcols:
            load_cols.append(Variant.ui_display_en)
        q = session.query(Variant).options(_load_only(*load_cols))
        if tabletop_only:
            try:
                q = q.filter(sa.or_(Variant.codex_unit_name.isnot(None), Variant.units.any(), Variant.game_system.isnot(None)))
            except Exception:
                # Fallback: codex_unit_name presence only
                q = q.filter(Variant.codex_unit_name.isnot(None))
        if ids:
            q = q.filter(Variant.id.in_(ids))
        if limit and limit > 0:
            q = q.limit(limit)
        try:
            variants = q.all()
        except Exception as e:
            # If table still missing, try to create and retry once
            try:
                import sqlalchemy as _sa  # type: ignore
                from sqlalchemy.exc import OperationalError as _OpErr  # type: ignore
            except Exception:
                _OpErr = Exception  # type: ignore
            if isinstance(e, _OpErr):
                try:
                    from db.models import Base as _Base2  # type: ignore
                    _Base2.metadata.create_all(bind=session.bind)
                    variants = q.all()
                except Exception:
                    raise
            else:
                raise
        # Build optional collection metadata lookup if table/model is available
        coll_lookup: Optional[Dict[int, Dict[str, Optional[str]]]] = None
        if Collection is not None:
            try:
                coll_ids: List[int] = []
                seen_ids: set[int] = set()
                for v in variants:
                    cid_raw = getattr(v, 'collection_id', None)
                    if isinstance(cid_raw, int):
                        cid = cid_raw
                    elif isinstance(cid_raw, str) and cid_raw.isdigit():
                        cid = int(cid_raw)
                    else:
                        cid = None
                    if isinstance(cid, int) and cid not in seen_ids:
                        seen_ids.add(cid)
                        coll_ids.append(cid)
                if coll_ids:
                    rows = session.query(Collection).filter(Collection.id.in_(coll_ids)).all()
                    coll_lookup = {r.id: {'theme': getattr(r, 'theme', None), 'original_label': getattr(r, 'original_label', None)} for r in rows}
            except Exception:
                coll_lookup = None
        total = len(variants)
        print(f"Found {total} variants to process (force={force}).")
        processed_since_commit = 0
        for v in variants:
            examined += 1
            # Base tokens: use stored raw_path_tokens if present; else derive on the fly
            # Build tokens from both stored raw_path_tokens and a live derivation
            stored: List[str] = []
            try:
                if 'raw_path_tokens' in vcols:
                    stored = [t for t in (getattr(v, 'raw_path_tokens', []) or []) if isinstance(t, str) and t]
            except Exception:
                stored = []
            derived: List[str] = []
            try:
                derived = tokens_from_variant(session, v)
            except Exception:
                derived = []
            toks_raw = stored + [t for t in derived if t not in set(stored)]
            toks = [norm_text(t) for t in toks_raw if t]
            # Filter out root folder tokens like 'sample_store' (and its split tokens)
            try:
                relp = (getattr(v, 'rel_path', '') or '')
            except Exception:
                relp = ''
            rp = relp.replace('\\', '/').lstrip('./').lower()
            if rp.startswith('sample_store/') or rp == 'sample_store':
                toks = [t for t in toks if t not in {'sample', 'store', 'sample_store'}]
            # token_locale may not exist in DB; getattr is safe
            loc: Optional[str]
            if 'token_locale' in vcols:
                loc = getattr(v, 'token_locale', None) or detect_locale_from_tokens(toks)
            else:
                loc = detect_locale_from_tokens(toks)

            # Refine locale for CJK by preferring Japanese if phrase/token keys match JA glossary
            if loc in (None, 'zh'):
                # Build candidate phrases from tokens (up to length 3 for speed)
                n = len(toks)
                found_ja = False
                found_zh = False
                for L in range(min(3, n), 0, -1):
                    for i in range(0, n - L + 1):
                        phrase = ' '.join(toks[i:i+L])
                        if phrase in glos.ja_keys:
                            found_ja = True
                        if phrase in glos.zh_keys:
                            found_zh = True
                    # Early exit if both found at this length
                    if found_ja and found_zh:
                        break
                # Prefer zh if any zh-specific phrase was present; else ja if present
                if found_zh:
                    loc = 'zh'
                elif found_ja:
                    loc = 'ja'
            eng = translate_tokens(toks, glos) if toks else []
            prop: Dict[str, object] = {"variant_id": v.id, "rel_path": v.rel_path, "changes": {}}
            changes = {}
            if ('token_locale' in vcols) and loc and (getattr(v, 'token_locale', None) in (None, '')):
                changes['token_locale'] = loc
            existing_eng = getattr(v, 'english_tokens', None) if ('english_tokens' in vcols) else None
            if eng and (force or not (existing_eng or [])):
                if 'english_tokens' in vcols:
                    changes['english_tokens'] = eng
            # Optional: materialize UI display when requested and when we either plan to write english_tokens
            # or already have them populated
            if materialize_ui and 'ui_display_en' in vcols:
                try:
                    cur_ui = getattr(v, 'ui_display_en', None)
                except Exception:
                    cur_ui = None
                # Build display from rel_path/filename; fallback to (new or existing) english tokens
                ui_tokens = eng if ('english_tokens' in changes) else (existing_eng or [])
                ui_val = build_ui_display(v, glos, ui_tokens, coll_meta=coll_lookup)
                if ui_val and (force or not (cur_ui or '')):
                    changes['ui_display_en'] = ui_val
            if changes:
                prop['changes'] = changes
                proposals.append(prop)
                if apply:
                    if ('token_locale' in changes) and ('token_locale' in vcols):
                        v.token_locale = changes['token_locale']
                    if ('english_tokens' in changes) and ('english_tokens' in vcols):
                        v.english_tokens = changes['english_tokens']
                    if ('ui_display_en' in changes) and ('ui_display_en' in vcols):
                        try:
                            v.ui_display_en = changes['ui_display_en']  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    changed_count += 1
            if apply:
                processed_since_commit += 1
                if processed_since_commit >= batch:
                    session.commit()
                    processed_since_commit = 0
        if apply and processed_since_commit > 0:
            session.commit()

    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'apply': bool(apply),
            'force': bool(force),
            'total_examined': examined,
            'total_variants': total,
            'proposals': proposals,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Wrote JSON report to: {out_path}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Backfill english_tokens for Variants using vocab/i18n glossaries')
    ap.add_argument('--db-url', type=str, help='Override DB URL (e.g., sqlite:///./data/stl_manager_v1.db)')
    ap.add_argument('--batch', type=int, default=200)
    ap.add_argument('--limit', type=int, default=0, help='Process at most N variants (0 = all)')
    ap.add_argument('--ids', type=str, help='Comma-separated Variant IDs')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--force', action='store_true', help='Recompute even when english_tokens already present')
    ap.add_argument('--out', type=str, help='Write JSON report to this path')
    ap.add_argument('--materialize-ui', dest='materialize_ui', action='store_true', help='Also populate ui_display_en using english_tokens')
    ap.add_argument('--tabletop-only', action='store_true', help='Process only variants linked to tabletop units or with codex/game_system info')
    return ap.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    # Reconfigure DB session when --db-url provided (Windows-friendly)
    if args.db_url:
        try:
            import db.session as _dbs
            # Use shared helper to ensure NullPool and PRAGMA are applied
            if hasattr(_dbs, 'reconfigure'):
                _dbs.reconfigure(args.db_url)
            else:
                # Backward-compatible fallback
                from sqlalchemy import create_engine as _ce
                from sqlalchemy.orm import sessionmaker as _sm, Session as _S
                try:
                    _dbs.engine.dispose()
                except Exception:
                    pass
                _dbs.DB_URL = args.db_url
                _dbs.engine = _ce(args.db_url, future=True)
                _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
        except Exception as e:
            print(f"Failed to reconfigure DB session for URL {args.db_url}: {e}", file=sys.stderr)
            return 2
    ids = [int(s) for s in args.ids.split(',')] if args.ids else None
    run(batch=args.batch, limit=args.limit, ids=ids, apply=args.apply, out=args.out, force=args.force, materialize_ui=bool(getattr(args, 'materialize_ui', False)), tabletop_only=bool(getattr(args, 'tabletop_only', False)))
    return 0


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))

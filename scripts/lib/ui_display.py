"""UI display-name builders extracted from backfill_english_tokens.

Functions here transform variant metadata (rel_path, codex_unit_name,
collection labels, etc.) into a human-friendly ``ui_display_en`` string.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _get_translate_tokens():
    """Lazy-load translate_tokens from backfill_english_tokens (numeric-prefix package)."""
    _mod_name = "scripts._backfill_english_tokens"
    if _mod_name in sys.modules:
        return sys.modules[_mod_name].translate_tokens
    _impl = Path(__file__).resolve().parents[1] / "30_normalize_match" / "backfill_english_tokens.py"
    spec = importlib.util.spec_from_file_location(_mod_name, str(_impl))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.translate_tokens


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BANNED_WORDS = {
    # Generic packaging/modifiers
    'supported', 'unsupported', 'presupported', 'pre', 'pre-supported', 'fixed',
    'repair', 'repaired', 'test', 'sample', 'store', 'bundle', 'pack', 'set',
    'parts', 'part', 'kit', 'stl', 'stls', 'obj', '3mf', 'lychee', 'chitubox',
    'cbddlp', 'step', 'fbx', 'blend', 'zip', 'lys', 'docs', 'info', 'images',
    'renders', 'render', 'preview', 'infomodel', 'infoprint', 'printinfo',
    'buildplate', 'builplate', 'zbrushztool', 'dm', 'stash', 'release', 'special',
    'height',
    # Directions/anatomy often noise for variant label
    'left', 'right', 'l', 'r', 'arm', 'leg', 'torso', 'head', 'body', 'backpack',
    'cloak', 'weapon', 'sword', 'axe', 'shield', 'helmet', 'helm', 'cape', 'base',
    'round', 'square', 'oval', 'mm', 'inch', 'in',
    # Common size/version tokens
    'v', 'v1', 'v2', 'v3', 'alt', 'alt1', 'alt2', 'alt3', 'ver', 'ver1', 'ver2',
    'ver3', 'mk', 'mk1', 'mk2', 'mk3',
    # Generic descriptors that shouldn't headline labels
    'scale', 'uncut', 'cut', 'merged', 'merge', 'split', 'hollow', 'hollowed',
    'solid', 'version', 'pose', 'poses',
}

_GENERIC_VARIANT_NAMES = {
    'bodies', 'body', 'heads', 'head', 'arms', 'arm', 'legs', 'leg', 'torsos',
    'torso', 'weapons', 'weapon', 'bits', 'accessories', 'poses', 'pose',
    'helmets', 'helmet', 'cloaks', 'cloak', 'shields', 'shield', 'spears',
    'spear', 'swords', 'sword', 'backpacks', 'backpack', 'hand', 'hands',
    'flamer', 'flamers',
}

_BUCKET_CONNECTORS = {"and", "&", "with"}
_BUCKET_PACKAGING = {"presupported", "supported", "unsupported"}

_PACKAGING_SEGMENTS = {
    'supported', 'unsupported', 'presupported', 'lys', 'lychee', 'stl', 'stls',
    '32mm', '75mm', '32', '75', 'cg', 'nsfw', 'sfw',
}

_CONTAINER_SEGMENTS = {
    'characters', 'character', 'heroes', 'lone heroes', 'units', 'unit', 'troops',
    'infantry', 'cavalry', 'combined', 'bundle', 'set', 'sets', 'kit', 'kits',
    'folders', 'collection', 'collections', 'misc', 'various', 'others',
    'assortment', 'lone',
}

_MONTHS = {m.lower() for m in (
    'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December',
    'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Sept', 'Oct',
    'Nov', 'Dec',
)}

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _norm_label(s: str) -> str:
    """Normalize a label for comparison — lowercase, clean, joined by spaces."""
    return ' '.join(_clean_words(_split_words(s or '')))


def _split_words(s: str) -> List[str]:
    """Split a candidate label into words: separators + simple CamelCase boundaries."""
    if not s:
        return []
    s2 = s.replace('-', ' ').replace('_', ' ').replace('.', ' ').replace('\\', '/').split('/')[-1]
    parts: List[str] = []
    buf = ''
    for ch in s2:
        if ch.isalnum():
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


def _is_bucket_phrase(toks: List[str]) -> bool:
    nouns = 0
    for t in toks:
        if t in _GENERIC_VARIANT_NAMES:
            nouns += 1
            continue
        if (t in _BUCKET_CONNECTORS) or (t in _BUCKET_PACKAGING):
            continue
        return False
    return nouns >= 1


def _clean_words(words: List[str]) -> List[str]:
    out: List[str] = []
    allow_short = {'of', 'to', 'in', 'vs', 'on', 'cg'}
    for w in words:
        wl = w.lower()
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
        if wl.isalpha() and len(wl) <= 2 and wl not in allow_short:
            continue
        wl = wl.strip('_-. ')
        if not wl:
            continue
        out.append(wl)
    return out


def _title_case(words: List[str]) -> str:
    if not words:
        return ''
    small = {'of', 'the', 'and', 'or', 'a', 'an', 'to', 'in', 'on'}
    acronyms = {'cg', 'opr', 'op', 'stl', 'obj', 'fbx', 'lys', 'cbddlp', '3mf', 'nsfw', 'sfw'}
    out: List[str] = []
    for i, w in enumerate(words):
        if i and w in small:
            out.append(w)
        else:
            if w in acronyms:
                out.append(w.upper())
            else:
                out.append(w[:1].upper() + w[1:])
    return ' '.join(out)


def _pretty_name(s: str) -> str:
    parts = _clean_words(_split_words(s))
    return _title_case(parts)


def _candidate_from_eng_tokens(tokens: Optional[List[str]]) -> str:
    """Pick a strong display candidate from english_tokens, ignoring generic/unit noise."""
    if not tokens:
        return ''
    words = [str(t).strip().lower() for t in tokens if isinstance(t, str) and str(t).strip()]
    words = _clean_words(words)
    noise = set().union(
        _PACKAGING_SEGMENTS,
        {'freeguild', 'marshal', 'relic', 'envoy', 'general', 'on', 'and', 'the', 'of',
         'base', 'full', 'square', 'stl', 'supported', 'unsupported'},
    )
    for w in words:
        if w not in noise:
            return _title_case([w])
    return ''


def _strip_noise_tokens(words: List[str]) -> List[str]:
    noise = set().union(
        _PACKAGING_SEGMENTS,
        {'base', 'full', 'square', 'round', 'oval', 'the', 'of', 'and', 'on', 'by'},
    )
    if words and words[0] == 'the':
        tail = [w for w in words[1:] if w not in noise]
        if tail:
            return ['the'] + tail
        return tail
    return [w for w in words if w not in noise]


def _is_packaging_segment(seg: str) -> bool:
    s = (seg or '').strip().lower()
    if not s:
        return False
    base = s.rsplit('.', 1)[0]
    if base in _PACKAGING_SEGMENTS:
        return True
    if 'support' in s and ' - ' not in seg:
        return True
    if re.fullmatch(r'(supported|unsupported)\s+stl(s)?', s):
        return True
    if re.fullmatch(r'stl(s)?', s):
        return True
    if s.endswith('mm') and s[:-2].isdigit():
        return True
    if s in {'.ds_store', '__macosx'}:
        return True
    return False


def _best_named_segment_from_path(relp: str) -> str:
    p = (relp or '').replace('\\', '/').strip('/')
    if not p:
        return ''
    segs = [s for s in p.split('/') if s]

    def is_packaging(seg: str) -> bool:
        s = seg.strip().lower()
        base = s.rsplit('.', 1)[0]
        if s.endswith(('.zip', '.rar', '.7z', '.7zip')):
            return True
        if base in _PACKAGING_SEGMENTS:
            return True
        if ('support' in s) and (' - ' not in seg):
            return True
        if s in {'.ds_store', '__macosx', 'supported', 'unsupported', 'stl', 'stls', 'lys', 'lychee'}:
            return True
        if s.isdigit() or (s.endswith('mm') and s[:-2].isdigit()):
            return True
        return False

    def looks_like_name(tokens: List[str]) -> bool:
        if not tokens:
            return False
        generic = set().union(_GENERIC_VARIANT_NAMES, _BANNED_WORDS)
        return any(t.isalpha() and t not in generic for t in tokens)

    def score(seg: str, idx: int) -> int:
        s = seg.strip().lower()
        if is_packaging(seg):
            return -100
        toks = _clean_words(_split_words(seg))
        sc = 0
        if looks_like_name(toks):
            sc += 5
        if '-' in seg:
            sc += 2
        if 1 <= len(toks) <= 6:
            sc += 2
        elif 7 <= len(toks) <= 9:
            sc += 1
        if any(t in _MONTHS for t in toks):
            sc -= 2
        if any(t in {'dm', 'stash', 'release'} for t in toks):
            sc -= 2
        if s in _CONTAINER_SEGMENTS:
            sc -= 20
        if idx == len(segs) - 1 and looks_like_name(toks):
            sc += 8
        if '-' in seg:
            parts = [p.strip() for p in re.split(r'\s*-\s*', seg) if p.strip()]
            if parts:
                lastp = parts[-1]
                toksp = _clean_words(_split_words(lastp))
                if looks_like_name(toksp):
                    sc += 4
        if idx > 0:
            parent = segs[idx - 1].strip().lower()
            if parent in _CONTAINER_SEGMENTS and looks_like_name(toks):
                sc += 10
        sc += idx * 2
        return sc

    best = ''
    best_score = -1000
    for i, seg in enumerate(segs):
        sc = score(seg, i)
        if sc >= best_score:
            best_score = sc
            best = seg
    if not best:
        return ''
    cleaned = re.sub(r'\s*-\s*(supported|unsupported)\s*$', '', best, flags=re.I)
    return cleaned


def _looks_like_proper_name(label: str) -> bool:
    s = (label or '').strip()
    if not s:
        return False
    if ',' in s and re.search(r'[A-Za-z]', s):
        return True
    toks = [t for t in s.split() if t]
    if len(toks) < 2:
        return False
    small = {'of', 'the', 'and', 'or', 'a', 'an', 'to', 'in', 'on'}
    cap_count = sum(1 for t in toks if t[:1].isupper() and t.lower() not in small)
    return cap_count >= 2


# ---------------------------------------------------------------------------
# Mid-level helpers
# ---------------------------------------------------------------------------


def _choose_collection_name(v_obj, coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None) -> str:
    try:
        theme = (getattr(v_obj, 'collection_theme', None) or '').strip()
    except Exception:
        theme = ''
    if coll_meta is not None:
        try:
            cid_raw = getattr(v_obj, 'collection_id', None)
            if cid_raw is not None:
                if isinstance(cid_raw, str) and cid_raw.isdigit():
                    cid = int(cid_raw)
                elif isinstance(cid_raw, int):
                    cid = cid_raw
                else:
                    cid = None
                if isinstance(cid, int) and cid in coll_meta:
                    meta = coll_meta[cid]
                    nm = (meta.get('theme') or meta.get('original_label') or '').strip()
                    if nm:
                        return _title_case(_clean_words(_split_words(nm)))
        except Exception:
            pass
    try:
        orig = (getattr(v_obj, 'collection_original_label', None) or '').strip()
    except Exception:
        orig = ''
    if theme and (len(theme) >= 6) and (' ' in theme):
        return _title_case(_clean_words(_split_words(theme)))
    txt = orig
    if not txt:
        return ''
    txt = re.sub(r'^\([^)]*\)\s*', '', txt).strip()
    parts = [t.strip() for t in re.split(r'[-\u2013\u2014]+', txt) if t.strip()]
    cand = ''
    for t in reversed(parts):
        if re.search(r'[a-zA-Z]', t):
            cand = t
            break
    if not cand:
        cand = txt
    return _title_case(_clean_words(_split_words(cand)))


def _choose_thing_name(
    v_obj,
    glos: object,
    eng_tokens: Optional[List[str]],
    coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None,
    *,
    _translate: object = None,
) -> str:
    """Derive the best human-readable thing name for a variant.

    Parameters
    ----------
    _translate : callable, optional
        Translation function with signature ``(tokens, glos) -> list[str]``.
        Defaults to ``translate_tokens`` from backfill_english_tokens.
    """
    if _translate is None:
        _translate = _get_translate_tokens()

    # 1) Character name (if present)
    try:
        char = (getattr(v_obj, 'character_name', None) or '').strip()
    except Exception:
        char = ''
    if char:
        return _title_case(_clean_words(_split_words(char)))

    try:
        relp = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp = ''
    # Early: comma-separated proper name in path
    if relp:
        _segs_preserve = [s for s in relp.replace('\\', '/').split('/') if s]
        for s in reversed(_segs_preserve):
            s_stripped = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
            if (',' in s_stripped) and re.search(r'[A-Za-z]', s_stripped):
                return s_stripped

    seg = _best_named_segment_from_path(relp)
    variant_label = ''
    if seg:
        seg_pres = re.sub(r'^\s*\d+[\.-]?\s*', '', seg).strip()
        if ',' in seg_pres and re.search(r'[A-Za-z]', seg_pres):
            return seg_pres
        parts_h = [p.strip() for p in re.split(r'\s*-\s*', seg) if p.strip()]
        if len(parts_h) >= 2:
            coll_name = _choose_collection_name(v_obj, coll_meta)
            coll_norm = _norm_label(coll_name) if coll_name else ''

            def is_brand(p: str) -> bool:
                pn = _norm_label(p)
                if pn in {'cast n play', 'castnplay', 'dm stash', 'dm'}:
                    return True
                toksb = set(_clean_words(_split_words(pn)))
                brand_hits = {
                    'studio', 'studios', '3d', 'miniature', 'miniatures', 'atelier',
                    'workshop', 'forge', 'labs', 'lab', 'models', 'model', 'printing',
                    'print', 'prints', 'patreon',
                }
                return bool(toksb & brand_hits)

            candidates = [p for p in parts_h if not is_brand(p) and (_norm_label(p) != coll_norm)]
            pick = candidates[-1] if candidates else parts_h[-1]
            words_p = _clean_words(_split_words(pick))
            mapped_p = _translate(words_p, glos) if words_p else []
            label_core = _title_case((mapped_p or words_p)[:8]) if (mapped_p or words_p) else ''
            prefix_label = ''
            if len(parts_h) >= 2:
                try:
                    idx_pick = parts_h.index(pick)
                except ValueError:
                    idx_pick = len(parts_h) - 1
                if idx_pick > 0:
                    left = parts_h[idx_pick - 1]
                    if left and (not is_brand(left)) and (_norm_label(left) != coll_norm):
                        words_l = _clean_words(_split_words(left))
                        mapped_l = _translate(words_l, glos) if words_l else []
                        prefix_label = _title_case((mapped_l or words_l)[:6]) if (mapped_l or words_l) else ''
            if label_core and not variant_label:
                variant_label = f"{prefix_label} - {label_core}".strip(' -') if prefix_label else label_core
        if not variant_label:
            words = _clean_words(_split_words(seg))
            mapped = _translate(words, glos) if words else []
            if mapped or words:
                base = mapped or words
                keep_n = 8 if len(base) >= 2 else 5
                variant_label = _title_case(base[:keep_n])
        # Prefer deepest non-packaging composite segment
        try:
            relp_deep = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp_deep = ''
        if relp_deep:
            segs_deep = [s for s in relp_deep.replace('\\', '/').split('/') if s]
            if segs_deep:
                lastd = segs_deep[-1]
                if lastd.strip().lower() in {'supported', 'unsupported', 'stl', 'stls', 'lys', 'lychee'} and len(segs_deep) >= 2:
                    lastd = segs_deep[-2]
                if lastd and (lastd != seg):
                    wd = _clean_words(_split_words(lastd))
                    composite = ('on' in {t.lower() for t in wd}) or (sum(1 for t in wd if any(c.isalpha() for c in t)) >= 3)
                    if composite:
                        md = _translate(wd, glos) if wd else []
                        base_d = md or wd
                        cand_d = _title_case(base_d[:8]) if base_d else ''
                        if cand_d:
                            variant_label = cand_d
        # Guard: single-token label rebuild
        v_words = _clean_words(_split_words(variant_label))
        if variant_label and len(v_words) == 1:
            seg_words = _clean_words(_split_words(seg))
            seg_mapped = _translate(seg_words, glos) if seg_words else []
            seg_base = seg_mapped or seg_words
            if len([t for t in seg_base if t.isalpha()]) >= 2:
                variant_label = _title_case(seg_base[:2])

    try:
        fname = getattr(v_obj, 'filename', None) or ''
    except Exception:
        fname = ''
    if fname:
        stem = fname.rsplit('.', 1)[0]
        words2 = _clean_words(_split_words(stem))
        mapped2 = _translate(words2, glos) if words2 else []
        if mapped2 and not variant_label:
            variant_label = _title_case(mapped2[:5])

    try:
        unit = (getattr(v_obj, 'codex_unit_name', None) or '').strip()
    except Exception:
        unit = ''
    unit_label = _title_case(_clean_words(_split_words(unit))) if unit else ''

    if variant_label:
        try:
            relp_seg = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp_seg = ''
        pseg = relp_seg.replace('\\', '/').strip('/')
        segs_var = [s for s in pseg.split('/') if s]
        unit_folder_norm = ''
        if len(segs_var) >= 2:
            unit_folder_norm = _norm_label(segs_var[1])
        if unit_folder_norm and (_norm_label(variant_label) == unit_folder_norm):
            last_u = segs_var[-1]
            if last_u.strip().lower() in {'supported', 'unsupported', 'stl', 'stls', 'lys', 'lychee'} and len(segs_var) >= 2:
                last_u = segs_var[-2]
            m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
            if m_name:
                core = m_name.group(1)
                w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                cand_core = _title_case(w_core[:2]) if w_core else ''
                if cand_core and (_norm_label(cand_core) != unit_folder_norm):
                    return cand_core
            w3 = _strip_noise_tokens(_clean_words(_split_words(last_u)))
            m3 = _translate(w3, glos) if w3 else []
            base3 = m3 or w3
            cand3 = _title_case(base3[:8]) if base3 else ''
            if cand3 and (_norm_label(cand3) != unit_folder_norm):
                return cand3
            lower_last = last_u.lower()
            if ('stl' in lower_last) or ('supported' in lower_last) or ('unsupported' in lower_last):
                cand_tok0 = _candidate_from_eng_tokens(eng_tokens)
                if cand_tok0 and (_norm_label(cand_tok0) != unit_folder_norm):
                    return cand_tok0
        if unit_label and (_norm_label(variant_label) == _norm_label(unit_label)):
            try:
                relp_u = getattr(v_obj, 'rel_path', '') or ''
            except Exception:
                relp_u = ''
            pu = relp_u.replace('\\', '/').strip('/')
            _segs_u = [s for s in pu.split('/') if s]
            if _segs_u:
                last_u = _segs_u[-1]
                if last_u.strip().lower() in {'supported', 'unsupported', 'stl', 'stls', 'lys', 'lychee'} and len(_segs_u) >= 2:
                    last_u = _segs_u[-2]
                m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
                if m_name:
                    core = m_name.group(1)
                    w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                    cand_core = _title_case(w_core[:2]) if w_core else ''
                    if cand_core and (_norm_label(cand_core) != _norm_label(unit_label)):
                        return cand_core
                w3 = _strip_noise_tokens(_clean_words(_split_words(last_u)))
                m3 = _translate(w3, glos) if w3 else []
                base3 = m3 or w3
                cand3 = _title_case(base3[:8]) if base3 else ''
                if cand3 and (_norm_label(cand3) != _norm_label(unit_label)):
                    return cand3
            last_u2 = _segs_u[-1] if _segs_u else ''
            low2 = (last_u2 or '').lower()
            if ('stl' in low2) or ('supported' in low2) or ('unsupported' in low2):
                cand_tok = _candidate_from_eng_tokens(eng_tokens)
                if cand_tok and (_norm_label(cand_tok) != _norm_label(unit_label)):
                    return cand_tok
            return unit_label
        return variant_label

    if unit_label:
        return unit_label

    # Fallback to english tokens
    toks = [str(t).strip() for t in (eng_tokens or []) if isinstance(t, str) and str(t).strip()]
    toks = _clean_words(toks)[:5]
    return _title_case(toks)


def build_ui_display(
    v_obj,
    glos: object,
    eng_tokens: Optional[List[str]] = None,
    coll_meta: Optional[Dict[int, Dict[str, Optional[str]]]] = None,
) -> str:
    """Build a semantic display name using character/unit, collection, and designer context.

    Precedence (stable):
      1) Deepest hyphen brand/collection/model pattern (prefer rightmost non-brand part)
      2) Deepest composite "X on Y" segment (preserve 'on')
      3) Deepest proper-name leaf (>=2 alpha tokens)
      4) Comma-preserve anywhere in path (verbatim)
      5) Fallback to _choose_thing_name and other hints
    """
    translate_tokens = _get_translate_tokens()

    def _translate_keep_dupes(tokens, glos):
        return translate_tokens(tokens, glos, dedup=False)

    collection = _choose_collection_name(v_obj, coll_meta)

    try:
        relp = getattr(v_obj, 'rel_path', '') or ''
    except Exception:
        relp = ''
    segs = [s for s in relp.replace('\\', '/').split('/') if s]
    last = ''
    last_idx = -1
    if segs:
        i = len(segs) - 1
        while i >= 0 and _is_packaging_segment(segs[i]):
            i -= 1
        last = segs[i] if i >= 0 else ''
        last_idx = i

    # 1) Hyphen brand/collection/model pattern at the leaf
    if last and ((' - ' in last) or ('-' in last)):
        parts_h = [x.strip() for x in re.split(r'\s*-\s*', last) if x.strip()]
        if len(parts_h) >= 2:
            coll_norm = _norm_label(collection) if collection else ''

            def is_brand(s: str) -> bool:
                sn = _norm_label(s)
                if sn in {'cast n play', 'castnplay', 'dm stash', 'dm'}:
                    return True
                toksb = set(_clean_words(_split_words(sn)))
                brand_hits = {
                    'studio', 'studios', '3d', 'miniature', 'miniatures', 'atelier',
                    'workshop', 'forge', 'labs', 'lab', 'models', 'model', 'printing',
                    'print', 'prints', 'patreon',
                }
                return bool(toksb & brand_hits)

            cands = [x for x in parts_h if not is_brand(x) and (_norm_label(x) != coll_norm)]
            right = cands[-1] if cands else parts_h[-1]
            pick_text = right
            idx_right = parts_h.index(right) if right in parts_h else -1
            if idx_right > 0:
                left_neighbor = parts_h[idx_right - 1]
                if not is_brand(left_neighbor):
                    right_l = right.lower()
                    if (' the ' in f' {right_l} ') or right_l.startswith('the '):
                        pick_text = f"{left_neighbor}-{right}"
            w = _clean_words(_split_words(pick_text))
            mapped = _translate_keep_dupes(w, glos) if w else []
            thing_h = _title_case((mapped or w)[:10]) if (mapped or w) else ''
            if thing_h and '-' in pick_text:
                parts = thing_h.split(' ')
                if len(parts) >= 2:
                    thing_h = parts[0] + '-' + ' '.join(parts[1:])
            if thing_h:
                if collection and (_norm_label(thing_h) != coll_norm):
                    return f"{collection}: {thing_h}"
                return thing_h

    # 2) Composite "X on Y" leaf
    if last and re.search(r'\bon\b', last, flags=re.I):
        wnp = _clean_words(_split_words(last))
        mnp = translate_tokens(wnp, glos) if wnp else []
        basenp = mnp or wnp
        candnp = _title_case(basenp[:8]) if basenp else ''
        if candnp:
            if collection and (_norm_label(candnp) != _norm_label(collection)):
                return f"{collection}: {candnp}"
            return candnp

    # 3) Deepest proper-name leaf (>=2 alpha tokens) — skip pure generic buckets
    if last:
        wleaf = _clean_words(_split_words(last))
        alpha_count = sum(1 for t in wleaf if any(c.isalpha() for c in t))
        all_bucket = bool(wleaf) and _is_bucket_phrase(wleaf)
        if (alpha_count >= 2) and (not all_bucket):
            mle = _translate_keep_dupes(wleaf, glos) if wleaf else []
            basele = mle or wleaf
            c_le = _title_case(basele[:10]) if basele else ''
            if c_le:
                if collection and (_norm_label(c_le) != _norm_label(collection)):
                    return f"{collection}: {c_le}"
                return c_le

    # 4) Comma-preserve anywhere in path (verbatim)
    for s in reversed(segs):
        s_clean = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
        if (',' in s_clean) and re.search(r'[A-Za-z]', s_clean):
            toks_pres = _clean_words(_split_words(s_clean))
            if toks_pres and all(t in _GENERIC_VARIANT_NAMES for t in toks_pres):
                break
            if collection and (' '.join(_clean_words(_split_words(s_clean))) != ' '.join(_clean_words(_split_words(collection)))):
                return f"{collection}: {s_clean}"
            return s_clean

    # 5) Fallback: derive via helper and hints
    thing = _choose_thing_name(v_obj, glos, eng_tokens, coll_meta, _translate=translate_tokens)

    # Strong preservation: comma-separated proper names override thing
    for s in reversed(segs):
        s2 = re.sub(r'^\s*\d+[\.-]?\s*', '', s).strip()
        if (',' in s2) and re.search(r'[A-Za-z]', s2):
            toks2 = _clean_words(_split_words(s2))
            if toks2 and all(t in _GENERIC_VARIANT_NAMES for t in toks2):
                continue
            thing = s2
            break

    # Hint: numeric ordering like '6. Foo Bar' at the leaf
    if last:
        m = re.match(r'^\s*\d+[\.-]?\s*(.+)$', last)
        if m:
            raw = m.group(1).strip()
            wn = _clean_words(_split_words(raw))
            mn = _translate_keep_dupes(wn, glos) if wn else []
            candn = _title_case((mn or wn)[:10]) if (mn or wn) else ''
            if candn and (not collection or (_norm_label(candn) != _norm_label(collection))):
                thing = candn

    # If nothing derived yet, attempt to build from deepest path segment
    if not thing and last:
        w0 = _strip_noise_tokens(_clean_words(_split_words(last)))
        m0 = _translate_keep_dupes(w0, glos) if w0 else []
        base0 = m0 or w0
        if base0:
            thing = _title_case(base0[:10])

    # If the variant label is a generic bucket, prefix with unit/collection
    try:
        unit_raw = (getattr(v_obj, 'codex_unit_name', None) or '').strip()
    except Exception:
        unit_raw = ''
    unit_label = _title_case(_clean_words(_split_words(unit_raw))) if unit_raw else ''

    if last:
        toks_last = _strip_noise_tokens(_clean_words(_split_words(last)))
        if toks_last and _is_bucket_phrase(toks_last):
            bucket = _title_case(toks_last[:6])
            parent_prefix = ''
            if last_idx > 0:
                j = last_idx - 1
                while j >= 0:
                    cand = segs[j]
                    cand_l = cand.strip().lower()
                    if cand_l in {'sample_store'}:
                        j -= 1; continue
                    if _is_packaging_segment(cand):
                        j -= 1; continue
                    if cand_l in _CONTAINER_SEGMENTS:
                        j -= 1; continue
                    words_p = _clean_words(_split_words(cand))
                    if _is_bucket_phrase(words_p):
                        j -= 1
                        continue
                    parent_prefix = _title_case(words_p[:8]) if words_p else ''
                    if parent_prefix:
                        break
                    j -= 1
            thing_tokens = _clean_words(_split_words(thing or ''))
            is_containerish = False
            if thing:
                if collection and (_norm_label(thing) == _norm_label(collection)):
                    is_containerish = True
                cont_keys = set(_CONTAINER_SEGMENTS)
                if any(t in cont_keys for t in thing_tokens):
                    is_containerish = True
            if bucket:
                if (not thing) or (_norm_label(thing) == _norm_label(bucket)) or is_containerish:
                    if unit_label:
                        thing = f"{unit_label}: {bucket}"
                    elif parent_prefix:
                        thing = f"{parent_prefix}: {bucket}"
                    elif collection:
                        thing = f"{collection}: {bucket}"
                    else:
                        thing = bucket

    # If the derived thing collapses to the unit label, try to rebuild from path last segment
    if thing and unit_label:
        if _norm_label(thing) == _norm_label(unit_label):
            last_u = last
            m_name = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', last_u)
            if m_name:
                core = m_name.group(1)
                w_core = _strip_noise_tokens(_clean_words(_split_words(core)))
                cand_core = _title_case(w_core[:2]) if w_core else ''
                if cand_core and (_norm_label(cand_core) != _norm_label(unit_label)):
                    thing = cand_core
            if not thing or _norm_label(thing) == _norm_label(unit_label):
                w_u = _strip_noise_tokens(_clean_words(_split_words(last_u)))
                m_u = translate_tokens(w_u, glos) if w_u else []
                base_u = m_u or w_u
                cand = _title_case(base_u[:8]) if base_u else ''
                if cand and (_norm_label(cand) != _norm_label(unit_label)):
                    thing = cand
            if _norm_label(thing) == _norm_label(unit_label):
                low2 = (last or '').lower()
                if ('stl' in low2) or ('supported' in low2) or ('unsupported' in low2):
                    cand2 = _candidate_from_eng_tokens(eng_tokens)
                    if cand2 and (_norm_label(cand2) != _norm_label(unit_label)):
                        thing = cand2

    # If no unit label but 'thing' equals the unit folder name (2nd segment), try token candidate
    if thing and not unit_label:
        try:
            relp_f = getattr(v_obj, 'rel_path', '') or ''
        except Exception:
            relp_f = ''
        pf = relp_f.replace('\\', '/').strip('/')
        segsf = [s for s in pf.split('/') if s]
        if len(segsf) >= 2:
            unit_folder = segsf[1]
            if _norm_label(thing) == _norm_label(unit_folder):
                lastf = segsf[-1]
                if lastf.strip().lower() in {'supported', 'unsupported', 'stl', 'stls', 'lys', 'lychee'} and len(segsf) >= 2:
                    lastf = segsf[-2]
                m_namef = re.search(r'(?i)\bstl[_\-\s]+([^_\-\s][^_\-\s]*)[_\-\s]+(supported|unsupported)\b', lastf)
                if m_namef:
                    coref = m_namef.group(1)
                    w_coref = _strip_noise_tokens(_clean_words(_split_words(coref)))
                    cand_coref = _title_case(w_coref[:2]) if w_coref else ''
                    if cand_coref and (_norm_label(cand_coref) != _norm_label(unit_folder)):
                        thing = cand_coref
                if _norm_label(thing) == _norm_label(unit_folder):
                    lowf = (lastf or '').lower()
                    if ('stl' in lowf) or ('supported' in lowf) or ('unsupported' in lowf):
                        cand_tok2 = _candidate_from_eng_tokens(eng_tokens)
                        if cand_tok2 and (_norm_label(cand_tok2) != _norm_label(unit_folder)):
                            thing = cand_tok2

    if thing:
        thing_norm = thing.strip().lower()
        toks_thing = _clean_words(_split_words(thing_norm))
        if _is_bucket_phrase(toks_thing):
            parent_prefix2 = ''
            if last_idx > 0:
                j2 = last_idx - 1
                while j2 >= 0:
                    cand2 = segs[j2]
                    cand2_l = cand2.strip().lower()
                    if cand2_l in {'sample_store'}:
                        j2 -= 1; continue
                    if _is_packaging_segment(cand2):
                        j2 -= 1; continue
                    if cand2_l in _CONTAINER_SEGMENTS:
                        j2 -= 1; continue
                    words_p2 = _clean_words(_split_words(cand2))
                    if _is_bucket_phrase(words_p2):
                        j2 -= 1; continue
                    parent_prefix2 = _title_case(words_p2[:8]) if words_p2 else ''
                    if parent_prefix2:
                        break
                    j2 -= 1
            if unit_label:
                thing = f"{unit_label}: {thing}"
            elif parent_prefix2:
                thing = f"{parent_prefix2}: {thing}"

    try:
        designer_raw = (getattr(v_obj, 'designer', None) or '').strip()
    except Exception:
        designer_raw = ''
    designer = _pretty_name(designer_raw) if designer_raw else ''

    if thing and thing.lower() in _MONTHS and collection:
        return f"{collection}: {thing}"

    if collection and thing:
        if _norm_label(thing) != _norm_label(collection):
            return f"{collection}: {thing}"
        return collection

    if thing and (',' in thing):
        return thing

    if thing and _looks_like_proper_name(thing):
        return thing

    if thing and designer:
        return f"{thing} by {designer}"

    if thing:
        return thing
    if collection:
        return collection
    if designer:
        return designer
    return ''

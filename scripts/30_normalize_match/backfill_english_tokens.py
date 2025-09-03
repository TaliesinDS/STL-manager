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


def build_ui_display(eng_tokens: List[str]) -> str:
    """Build a lightweight English UI display string.

    Keep it deterministic and conservative: join the english_tokens with a single space.
    Values in english_tokens are already normalized to lowercase; proper-noun
    casing can be introduced later if/when we add curated UI labels.
    """
    try:
        toks = [str(t).strip() for t in (eng_tokens or []) if isinstance(t, str) and str(t).strip()]
        return " ".join(toks)
    except Exception:
        return ""


def run(batch: int, limit: int, ids: Optional[List[int]], apply: bool, out: Optional[str], force: bool, materialize_ui: bool) -> None:
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
        if 'token_locale' in vcols:
            load_cols.append(Variant.token_locale)
        if 'ui_display_en' in vcols:
            load_cols.append(Variant.ui_display_en)
        q = session.query(Variant).options(_load_only(*load_cols))
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
                # Choose tokens to display: prefer the newly computed ones if we set them; else existing
                ui_tokens = eng if ('english_tokens' in changes) else (existing_eng or [])
                ui_val = build_ui_display(ui_tokens)
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
    run(batch=args.batch, limit=args.limit, ids=ids, apply=args.apply, out=args.out, force=args.force, materialize_ui=bool(getattr(args, 'materialize_ui', False)))
    return 0


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))

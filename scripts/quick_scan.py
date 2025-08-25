#!/usr/bin/env python3
"""Quick exploratory scan to surface high-frequency tokens & obvious metadata candidates.
Phase: Pre-implementation planning aid (safe: read-only, no archive extraction).
Supports optional dynamic vocab loading from tokenmap (Markdown) via --tokenmap.
If provided, designers / lineage families / faction hints / stopwords are parsed from the map; fallback to embedded defaults on error.

Usage (Windows PowerShell):
    python scripts/quick_scan.py --root D:\path\to\models --limit 100000 --extensions .stl .obj .lys .chitubox \
            --json-out quick_scan_report.json

Outputs (stdout always):
    - Summary counts (files scanned, directories scanned, distinct tokens)
    - Top N tokens (default 100) not already in known vocab domains (designer aliases, lineage family, factions, variant axes, stopwords)
    - Potential scale tokens & suspicious denominators
    - Tokens containing digits (often version, pose, scale, base size) for manual review
    - Simple heuristic suggestions list (printed at end)
Optional JSON (--json-out):
    {
    "scanned_files": int,
        "scanned_archives": int,
        "distinct_tokens": int,
        "top_unknown_tokens": [{"token": str, "count": int}],
        "scale_ratios": [{"token": str, "denominator": int, "count": int, "uncommon": bool}],
        "scale_mm": [{"token": str, "mm": int, "count": int}],
        "numeric_tokens": [{"token": str, "count": int}],
        "suggestions": [str],
    "token_map_version": str | null,
    "ignored_tokens": [{"token": str, "count": int, "reason": str}],
    "domain_summary": {"designer": int, "lineage_family": int, ...},
    "archive_token_sample": [{"token": str, "count": int}]
    }
"""
from __future__ import annotations
import argparse
import pathlib
import re
import sys
import collections
import json

# Embedded default vocab (acts as fallback if tokenmap parse not supplied / fails)
DEFAULT_STOPWORDS = {"the","and","of","for","set","pack","stl","model","models","mini","minis","figure","figures","files","printing","print"}
DEFAULT_DESIGNER_ALIASES = {"ghamak","ghmk","ghamak_studio","rn_estudio","rn-estudio","rnestudio","archvillain","arch_villain","archvillain_games","avg","puppetswar","puppets_war","tinylegend","azerama","hybris","hybris_studio","moxomor","mezgike","momoji","momoji3d","3dmomoji","moonfigures","3dmoonn","funservicestl","pikky","pikky_prints","esm"}
DEFAULT_LINEAGE_FAMILY = {"elf","elves","aelf","aelves","human","humans","man","men","dwarf","dwarves","duardin","orc","orcs","ork","orks","orruk","orruks","undead","skeleton","skeletons","ghoul","ghouls","zombie","zombies","wight","wights","demon","daemon","daemons","demons","goblin","goblins","grot","grots","halfling","halflings","hobbit","hobbits","lizardfolk","lizardman","lizardmen","saurus","dragonborn","draconian","drake","vampire","vampires","vampiric","ratfolk","kobold","kobolds"}
DEFAULT_FACTION_HINTS = {"stormcast","custodes","tau","aeldari","eldar","nurgle","tzeentch","slaanesh","khorne","necron","tyranid","ork","orks","guard","astra","sororitas","votann","skaven","lumineth","seraphon"}
VARIANT_AXES = {"split","parts","part","multi-part","multi_part","onepiece","one_piece","merged","solidpiece","hollow","hollowed","solid","presupported","pre-supported","pre_supported","supported","unsupported","no_supports","clean","bust","base_pack","bases_only","base_set","bits","bitz","accessories"}
SCALE_RATIO_RE = re.compile(r"^1[-_:]?([0-9]{1,3})$")
SCALE_MM_RE = re.compile(r"^([0-9]{2,3})mm$")
ALLOWED_DENOMS = {4,6,7,9,10,12}
ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.cbz', '.cbr'}  # simple set (multi-suffix like .tar.gz not yet handled)

# Runtime vocab (mutable): initialized with defaults, optionally replaced/extended by tokenmap parse
STOPWORDS = set(DEFAULT_STOPWORDS)
DESIGNER_ALIASES = set(DEFAULT_DESIGNER_ALIASES)
LINEAGE_FAMILY = set(DEFAULT_LINEAGE_FAMILY)
FACTION_HINTS = set(DEFAULT_FACTION_HINTS)

SPLIT_CHARS = re.compile(r"[\s_\-]+")
TOKEN_MIN_LEN = 2
TOKENMAP_VERSION: str | None = None
TOKEN_LIST_PATTERN = re.compile(r'^\s*([a-z0-9_]+):\s*\[(.*?)\]\s*$')
DESIGNER_SUFFIXES = ("studio","studios","miniature","miniatures","minis","prints","printing","figures","figure")

def _split_alias_list(raw: str) -> list[str]:
    out = []
    for part in raw.split(','):
        part = part.strip().strip('"\'')
        if part:
            out.append(part)
    return out

def load_tokenmap(tokenmap_path: pathlib.Path) -> dict[str, int] | None:
    """Parse minimal alias sets from tokenmap.md (designers, lineage family_map, factions, stopwords). Returns counts dict or None on failure."""
    global STOPWORDS, DESIGNER_ALIASES, LINEAGE_FAMILY, FACTION_HINTS, TOKENMAP_VERSION
    try:
        text = tokenmap_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:  # pragma: no cover
        print(f"[warn] Failed to read tokenmap: {e}")
        return None
    m_ver = re.search(r'token_map_version:\s*(\d+)', text)
    if m_ver:
        TOKENMAP_VERSION = m_ver.group(1)
    designers_added = lineage_added = factions_added = stopwords_added = 0
    in_designers = False
    in_family_map = False
    in_factions = False
    in_stopwords = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if in_designers: in_designers = False
            if in_family_map: in_family_map = False
            if in_stopwords: in_stopwords = False
        if stripped.startswith('designers:'):
            in_designers = True
            continue
        if 'family_map:' in stripped:
            in_family_map = True
            continue
        if stripped.startswith('factions:'):
            in_factions = True
            continue
        if stripped.startswith('stopwords:'):
            in_stopwords = True
            m_inline = re.search(r'stopwords:\s*\[(.*?)\]', stripped)
            if m_inline:
                for tok in _split_alias_list(m_inline.group(1)):
                    if tok not in STOPWORDS:
                        STOPWORDS.add(tok)
                        stopwords_added += 1
            continue
        m_list = TOKEN_LIST_PATTERN.match(line)
        if m_list:
            key, raw_list = m_list.groups()
            aliases = _split_alias_list(raw_list)
            if in_designers:
                for a in aliases:
                    if a not in DESIGNER_ALIASES:
                        DESIGNER_ALIASES.add(a); designers_added += 1
            elif in_family_map:
                for a in aliases:
                    if a not in LINEAGE_FAMILY:
                        LINEAGE_FAMILY.add(a); lineage_added += 1
            elif in_factions:
                for a in aliases:
                    if a not in FACTION_HINTS:
                        FACTION_HINTS.add(a); factions_added += 1
            continue
    return {'designers_added': designers_added,'lineage_added': lineage_added,'faction_aliases_added': factions_added,'stopwords_added': stopwords_added}

def load_external_designers(designers_path: pathlib.Path) -> int:
    """Load only designers section from external designers_tokenmap.md. Returns count added."""
    global DESIGNER_ALIASES
    try:
        text = designers_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return 0
    in_designers = False
    added = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if in_designers: in_designers = False
        if stripped.startswith('designers:'):
            in_designers = True
            continue
        m_list = TOKEN_LIST_PATTERN.match(line)
        if m_list and in_designers:
            _, raw_list = m_list.groups()
            for a in _split_alias_list(raw_list):
                if a not in DESIGNER_ALIASES:
                    DESIGNER_ALIASES.add(a); added += 1
    return added

def tokenize(path: pathlib.Path) -> list[str]:
    # Tokenize across all path components (directories + final name) so that
    # meaningful names embedded in directory structure (e.g., "Store/Artist - Ryuko Matoi/Model")
    # are not ignored. Preserve original normalization logic per-component.
    s = str(path)
    # Normalize Windows backslashes to forward slashes for consistent splitting
    s = s.replace('\\', '/')
    comps = [c for c in s.split('/') if c]
    tokens: list[str] = []
    for comp in comps:
        # Remove common file extension if present (keep base name)
        if '.' in comp:
            comp = comp.rsplit('.', 1)[0]
        # Lowercase and split on configured separator chars
        raw = comp.lower()
        parts = SPLIT_CHARS.split(raw)
        for p in parts:
            p = p.strip()
            if not p or len(p) < TOKEN_MIN_LEN:
                continue
            # Normalize wrapper punctuation and leading markers to reduce noisy variants
            p = p.strip("()[]{}+")
            # Remove leading '@' (social/source markers) and trailing '+' artifacts
            if p.startswith('@'):
                p = p[1:]
            # Collapse trailing extension remnants in token (e.g., 'unsupported.stl')
            if p.endswith('.stl'):
                p = p[:-4]
            if not p or len(p) < TOKEN_MIN_LEN:
                continue
            tokens.append(p)
    return tokens

def classify_token(tok: str) -> str | None:
    if tok in STOPWORDS: return "stopword"
    if tok in DESIGNER_ALIASES: return "designer"
    if tok in LINEAGE_FAMILY: return "lineage_family"
    if tok in FACTION_HINTS: return "faction_hint"
    if tok in VARIANT_AXES: return "variant_axis"
    if SCALE_RATIO_RE.match(tok): return "scale_ratio"
    if SCALE_MM_RE.match(tok): return "scale_mm"
    return None

def maybe_strip_designer_suffix(tok: str) -> str:
    # Only strip if token longer than suffix+1 and endswith suffix; return stripped if result in designer aliases
    for suf in DESIGNER_SUFFIXES:
        if tok.endswith(suf) and len(tok) > len(suf)+1:
            base = tok[:-len(suf)]
            if base in DESIGNER_ALIASES:
                return base
    return tok

def scan(root: pathlib.Path, limit: int, exts: set[str], unknown_top: int, skip_dirs: bool, ignore_set: set[str], emit_known_summary: bool, include_archives: bool, archive_sample: int, strip_suffixes: bool) -> dict:
    file_count = dir_count = 0
    archive_count = 0
    token_counter: collections.Counter[str] = collections.Counter()
    token_domain: dict[str, str] = {}
    numeric_like: collections.Counter[str] = collections.Counter()
    archive_token_set: set[str] = set()
    token_from_archive: set[str] = set()
    for p in root.rglob('*'):
        if p.is_dir():
            if skip_dirs: continue
            for tok in tokenize(p):
                if strip_suffixes:
                    tok = maybe_strip_designer_suffix(tok)
                domain = classify_token(tok)
                token_counter[tok] += 1
                if domain: token_domain.setdefault(tok, domain)
                if any(c.isdigit() for c in tok): numeric_like[tok] += 1
            dir_count += 1
            continue
        suffix = p.suffix.lower()
        is_archive = suffix in ARCHIVE_EXTS if include_archives else False
        if exts and suffix not in exts and not is_archive:
            continue
        if is_archive:
            archive_count += 1
        file_count += 1
        for tok in tokenize(p):
            if strip_suffixes:
                tok = maybe_strip_designer_suffix(tok)
            domain = classify_token(tok)
            token_counter[tok] += 1
            if domain: token_domain.setdefault(tok, domain)
            if any(c.isdigit() for c in tok): numeric_like[tok] += 1
            if is_archive:
                token_from_archive.add(tok)
        if limit and file_count >= limit: break
    # Build unknown list excluding user ignored tokens
    unknown: list[tuple[str,int]] = []
    for tok, cnt in token_counter.most_common():
        if tok in token_domain:
            continue
        if tok in ignore_set:
            continue
        unknown.append((tok, cnt))
        if len(unknown) >= unknown_top:
            break
    ignored_tokens = [{"token": t, "count": token_counter[t], "reason": "user_ignore"} for t in sorted(ignore_set) if t in token_counter]

    # Archive-only sample (tokens that occur only in archive filenames, not classified, not ignored, not already in top unknown)
    archive_sample_list: list[dict] = []
    if archive_sample > 0 and token_from_archive:
        unknown_tokens_set = {t for t,_ in unknown}
        for tok in token_from_archive:
            if tok in token_domain: continue
            if tok in ignore_set: continue
            if tok in unknown_tokens_set: continue
            # Only include tokens predominantly archive-sourced (heuristic: frequency <=2 or appears only in archives)
            archive_token_set.add(tok)
        # Sort archive-only tokens by count desc then alpha
        sorted_arch = sorted( ((t, token_counter[t]) for t in archive_token_set), key=lambda x: (-x[1], x[0]) )
        for t,c in sorted_arch[:archive_sample]:
            archive_sample_list.append({"token": t, "count": c})
    ratios_raw = [(t, c) for t, c in token_counter.items() if classify_token(t) == "scale_ratio"]
    mms_raw = [(t, c) for t, c in token_counter.items() if classify_token(t) == "scale_mm"]
    ratios = []
    for t, c in sorted(ratios_raw, key=lambda x: -x[1]):
        denom = int(SCALE_RATIO_RE.match(t).group(1))
        ratios.append({"token": t, "denominator": denom, "count": c, "uncommon": denom not in ALLOWED_DENOMS})
    mm_entries = []
    for t, c in sorted(mms_raw, key=lambda x: -x[1]):
        mm = int(SCALE_MM_RE.match(t).group(1))
        mm_entries.append({"token": t, "mm": mm, "count": c})
    numeric_tokens = [{"token": tok, "count": cnt} for tok, cnt in numeric_like.most_common(30)]
    suggestions: list[str] = []
    if unknown: suggestions.append("Review top unknown tokens for new designer aliases, factions, or lineage expansions.")
    if ratios or mm_entries: suggestions.append("Validate scale tokens; add uncommon denominators to suspect list if legitimate.")
    if any(tok.startswith('v') and tok[1:].isdigit() for tok in token_counter): suggestions.append("Detected version-like tokens; ensure version_num extraction pattern covers them.")
    suggestions.append("Consider capturing any high-frequency unknowns appearing across >5% of scanned files.")
    print(f"Scanned files: {file_count}")
    if include_archives and archive_count:
        print(f"  (archives counted among files: {archive_count})")
    if not skip_dirs: print(f"Scanned directories: {dir_count}")
    print(f"Distinct tokens: {len(token_counter)}")
    print("\nTop unknown tokens (potential new vocab):")
    for tok, cnt in unknown: print(f"  {tok}: {cnt}")
    if ignored_tokens:
        print(f"\nIgnored tokens (suppressed so others can surface): {len(ignored_tokens)}")
        for it in ignored_tokens[:15]:
            print(f"  {it['token']}: {it['count']}")
        extra = len(ignored_tokens) - 15
        if extra > 0:
            print(f"  ... (+{extra} more)")
    if ratios or mm_entries:
        print("\nScale tokens:")
        for r in ratios:
            flag = "*" if r["uncommon"] else ""
            print(f"  ratio {r['token']} -> {r['denominator']}{flag} ({r['count']})")
        for m in mm_entries: print(f"  height {m['mm']}mm ({m['count']})")
    print("\nTokens containing digits (top 30):")
    for nt in numeric_tokens: print(f"  {nt['token']}: {nt['count']}")
    print("\nSuggestions:")
    for s in suggestions: print(f"  {s}")
    if archive_sample_list:
        print(f"\nArchive token sample (not in top unknown): {len(archive_sample_list)} shown")
        for a in archive_sample_list[:20]:
            print(f"  {a['token']}: {a['count']}")
    domain_summary = {}
    if emit_known_summary:
        inv: dict[str,int] = collections.Counter(token_domain.values())
        domain_summary = dict(inv)
        if emit_known_summary:
            print("\nKnown domain summary:")
            for k,v in sorted(domain_summary.items()):
                print(f"  {k}: {v}")

    return {
    "scanned_files": file_count,
    "scanned_archives": archive_count if include_archives else 0,
        "scanned_directories": (0 if skip_dirs else dir_count),
        "distinct_tokens": len(token_counter),
        "top_unknown_tokens": [{"token": tok, "count": cnt} for tok, cnt in unknown],
        "scale_ratios": ratios,
        "scale_mm": mm_entries,
        "numeric_tokens": numeric_tokens,
        "suggestions": suggestions,
        "token_map_version": TOKENMAP_VERSION,
        "ignored_tokens": ignored_tokens,
    "domain_summary": domain_summary,
    "archive_token_sample": archive_sample_list,
    }

def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Quick token frequency scan (if --root omitted, uses script directory)")
    ap.add_argument('--root', help='Root directory to scan (defaults to folder containing this script)')
    ap.add_argument('--limit', type=int, default=100000, help='Max files to process (0 = no limit)')
    ap.add_argument('--extensions', nargs='*', default=['.stl', '.obj', '.lys', '.chitubox', '.ctb', '.step'], help='Extensions to include (lowercase)')
    ap.add_argument('--json-out', help='Optional path to write JSON report')
    ap.add_argument('--unknown-top', type=int, default=300, help='How many top unknown tokens to include')
    ap.add_argument('--skip-dirs', action='store_true', help='Skip tokenizing directory names (default includes)')
    ap.add_argument('--tokenmap', help='Path to tokenmap.md to dynamically load vocab (aliases, lineage, factions, stopwords)')
    ap.add_argument('--ignore-file', help='Path to newline-delimited token ignore list (one token per line; # comments allowed)')
    ap.add_argument('--emit-known-summary', action='store_true', help='Include summary counts of classified tokens by domain')
    ap.add_argument('--include-archives', action='store_true', help='Include archive filenames (.zip/.rar/.7z/.cbz/.cbr) without extraction')
    ap.add_argument('--archive-sample', type=int, default=0, help='Show up to N archive-only tokens that did not make top unknown list')
    ap.add_argument('--designers-file', help='Optional external designers_tokenmap.md file to preload designer aliases')
    ap.add_argument('--strip-designer-suffixes', action='store_true', help='Strip common designer suffixes (studio/minis/prints/figures) after alias match to reduce variant noise')
    return ap.parse_args(argv)

def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.root: root = pathlib.Path(args.root)
    else:
        root = pathlib.Path(__file__).resolve().parent
        print(f"[info] --root not provided; using script directory: {root}")
    if not root.exists() or not root.is_dir():
        print(f"Root not found or not directory: {root}", file=sys.stderr); return 2
    exts = {e.lower() for e in args.extensions}
    # Load external designers first (if provided or exists by default name)
    if args.designers_file:
        dpath = pathlib.Path(args.designers_file)
    else:
        # Support relocated vocab files under /vocab (post 2025-08-16 restructure)
        root_dir = pathlib.Path(__file__).resolve().parent.parent
        candidate_new = root_dir / 'vocab' / 'designers_tokenmap.md'
        if candidate_new.exists():
            dpath = candidate_new
        else:
            legacy = root_dir / 'designers_tokenmap.md'
            if legacy.exists():
                print("[warn] using legacy root designers_tokenmap.md; migrate expected under vocab/" )
            dpath = legacy
    if dpath.exists():
        added = load_external_designers(dpath)
        if added:
            print(f"[info] external designers loaded +{added} from {dpath.name}")

    if args.tokenmap:
        tm_path = pathlib.Path(args.tokenmap)
    else:
        # Auto-detect relocated tokenmap in vocab/ first, fallback to root
        root_dir = pathlib.Path(__file__).resolve().parent.parent
        candidate_new = root_dir / 'vocab' / 'tokenmap.md'
        if candidate_new.exists():
            tm_path = candidate_new
        else:
            legacy = root_dir / 'tokenmap.md'
            if legacy.exists():
                print("[warn] using legacy root tokenmap.md; migrate expected under vocab/")
            tm_path = legacy
    if tm_path.exists():
        stats = load_tokenmap(tm_path)
        if stats:
            print(f"[info] tokenmap loaded (version={TOKENMAP_VERSION}) designers+{stats['designers_added']} lineage+{stats['lineage_added']} faction_aliases+{stats['faction_aliases_added']} stopwords+{stats['stopwords_added']} from {tm_path}")
        else:
            print("[warn] tokenmap parse failed; using embedded defaults")
    else:
        print(f"[warn] tokenmap path not found: {tm_path}; using embedded defaults")
    ignore_set: set[str] = set()
    ig_path: pathlib.Path | None = None
    if args.ignore_file:
        ig_path = pathlib.Path(args.ignore_file)
    else:
        # Fallback: look for ignored_tokens.txt alongside script
        candidate = pathlib.Path(__file__).resolve().parent / 'ignored_tokens.txt'
        if candidate.exists():
            ig_path = candidate
            print(f"[info] --ignore-file not provided; using default {ig_path.name}")
    if ig_path:
        if ig_path.exists():
            try:
                for line in ig_path.read_text(encoding='utf-8').splitlines():
                    line = line.strip().lower()
                    if not line or line.startswith('#'): continue
                    ignore_set.add(line)
                print(f"[info] loaded {len(ignore_set)} ignore tokens from {ig_path}")
            except Exception as e:
                print(f"[warn] failed to read ignore file: {e}")
        else:
            print(f"[warn] ignore file not found: {ig_path}")
    report = scan(root, args.limit, exts, args.unknown_top, args.skip_dirs, ignore_set, args.emit_known_summary, args.include_archives, args.archive_sample, args.strip_designer_suffixes)
    if args.json_out: out_path = pathlib.Path(args.json_out)
    else:
        out_path = root / 'quick_scan_report.json'
        print(f"[info] --json-out not provided; defaulting to {out_path}")
    try:
        out_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f"\nJSON report written: {out_path}")
    except Exception as e:  # pragma: no cover
        print(f"Failed to write JSON report: {e}", file=sys.stderr)
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

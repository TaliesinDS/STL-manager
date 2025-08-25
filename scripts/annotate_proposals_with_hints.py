#!/usr/bin/env python3
"""Annotate filtered proposals with `franchise_hints` and `faction_hints`.

Reads a proposals file (one JSON object per line), loads franchise manifests
and tokenmap aliases, inspects the variant's tokens using the project's
tokenizer, and decides which tokens indicate franchise vs faction. It will:

- Add `franchise_hints`: list of canonical franchise keys suggested by tokens
- Add `faction_hints`: list of faction tokens (from tokenmap factions)
- Remove `tabletop_no_franchise` from `normalization_warnings` when the
  variant tokens do not contain any `TABLETOP_HINTS` tokens.

Writes a new output file with updated proposal objects (one JSON per line).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.quick_scan import load_tokenmap, classify_token, tokenize
from pathlib import Path
import json

# Local copy of tabletop hint tokens (kept in sync with normalize_inventory.TABLETOP_HINTS)
TABLETOP_HINTS = {
    "mini", "miniature", "miniatures", "terrain", "scenery", "base",
    "bases", "bust", "miniaturesupports", "support",
    "mm", "scale", "mini_supports", "squad"
}


def load_franchise_maps_local(fr_dir: Path):
    fam = {}
    f_tokens = {}
    if not fr_dir.exists():
        return fam, {}, {}
    for p in sorted(fr_dir.glob('*.json')):
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        franchise_key = j.get('franchise') or p.stem
        for a in (j.get('aliases') or []):
            fam[str(a).strip().lower()] = franchise_key
        tokens_block = j.get('tokens') or {}
        strong = set((t or '').strip().lower() for t in (tokens_block.get('strong_signals') or []))
        weak = set((t or '').strip().lower() for t in (tokens_block.get('weak_signals') or []))
        f_tokens[franchise_key] = {'strong': strong, 'weak': weak}
        # also include the canonical franchise key as an alias
        fam.setdefault(franchise_key.lower(), franchise_key)
    return fam, {}, f_tokens


def load_proposals(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    skipped = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            # ignore malformed lines
            skipped += 1
            continue
        if not isinstance(obj, dict):
            # skip non-dict JSON entries (e.g., stray arrays)
            skipped += 1
            continue
        out.append(obj)
    if skipped:
        print(f'[warn] skipped {skipped} non-dict or malformed lines while loading proposals from {path}')
    return out


def annotate_proposals(proposals: list[dict], session, fam_map, tokenmap_path: Path) -> list[dict]:
    # Load tokenmap small parse to seed classify_token domain sets
    load_tokenmap(tokenmap_path)

    annotated = []
    for idx, p in enumerate(proposals, start=1):
        # Defensive: ensure each proposal is a mapping
        if not isinstance(p, dict):
            print(f"[warn] skipping proposal #{idx}: not a JSON object (type={type(p).__name__})")
            continue
        try:
            # Tokenize from the rel_path first (base tokens). Then include tokens
            # from model files under that directory when they reasonably belong to
            # the same variant (heuristic similar to tokens_from_variant).
            rel = p.get('rel_path') or ''
            toks = []
            base_tokens = []
            try:
                base_tokens = tokenize(Path(rel))
            except Exception:
                base_tokens = []

            seen = set()
            out_tokens = []
            for t in base_tokens:
                if t in seen:
                    continue
                seen.add(t)
                out_tokens.append(t)

            # Now look for model files under the rel_path in the repo workspace
            root = Path(__file__).resolve().parent.parent
            candidate_dir = root / Path(rel)
            MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb'}
            file_tokens_all = []
            if candidate_dir.exists() and candidate_dir.is_dir():
                # walk files under the candidate_dir
                for fp in candidate_dir.rglob('*'):
                    if fp.is_dir():
                        continue
                    ext = fp.suffix.lower()
                    # skip non-model files
                    if ext and ext not in MODEL_EXTS:
                        continue
                    try:
                        f_toks = tokenize(fp)
                    except Exception:
                        f_toks = []
                    if f_toks:
                        file_tokens_all.append((fp, list(f_toks)))

            # Decide whether to include tokens from each file using heuristics:
            # - include if file shares a token with base_tokens
            # - or include if base_tokens empty (fallback)
            for fp, f_toks in file_tokens_all:
                include = False
                if base_tokens:
                    if set(f_toks) & set(base_tokens):
                        include = True
                else:
                    include = True
                if not include:
                    continue
                for t in f_toks:
                    if t in seen:
                        continue
                    seen.add(t)
                    out_tokens.append(t)

            toks = out_tokens

            # Determine tabletop status
            is_tabletop = any(t in TABLETOP_HINTS for t in toks)

            franchise_hints = []
            faction_hints = []

            # For each token, decide where it belongs by consulting franchise map
            # and tokenmap domains.
            for t in toks:
                if t in fam_map:
                    canon = fam_map[t]
                    if canon and canon not in franchise_hints:
                        franchise_hints.append(canon)
                    # a franchise token is not a faction token, continue
                    continue
                dom = classify_token(t)
                if dom == 'faction_hint':
                    if t not in faction_hints:
                        faction_hints.append(t)

            newp = dict(p)
            changes = dict(newp.get('changes') or {})
            if franchise_hints:
                changes['franchise_hints'] = franchise_hints
            if faction_hints:
                changes['faction_hints'] = faction_hints

            # Clean up tabletop_no_franchise if variant tokens show no tabletop hints
            nw = list(changes.get('normalization_warnings') or [])
            if 'tabletop_no_franchise' in nw and not is_tabletop:
                nw = [x for x in nw if x != 'tabletop_no_franchise']
                if nw:
                    changes['normalization_warnings'] = nw
                else:
                    changes.pop('normalization_warnings', None)

            newp['changes'] = changes
            annotated.append(newp)
        except Exception as e:
            # Print diagnostics and continue with other proposals
            try:
                preview = json.dumps(p, ensure_ascii=False)
            except Exception:
                preview = repr(p)
            print(f"[error] failed to annotate proposal #{idx}: {e}")
            print(traceback.format_exc())
            print(f"[error] proposal #{idx} preview: {preview[:400]}")
            continue

    return annotated


def write_proposals(proposals: list[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8') as fh:
        for p in proposals:
            fh.write(json.dumps(p, ensure_ascii=False))
            fh.write('\n')


def parse_args(argv: list[str]):
    ap = argparse.ArgumentParser(description='Annotate filtered proposals with franchise/faction hints')
    ap.add_argument('--in', dest='infile', required=True)
    ap.add_argument('--out', dest='outfile', required=True)
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ip = Path(args.infile)
    op = Path(args.outfile)
    proposals = load_proposals(ip)
    if not proposals:
        print('No proposals to process'); return 0

    root = Path(__file__).resolve().parent.parent
    fam_map, cam, f_tokens = load_franchise_maps_local(root / 'vocab' / 'franchises')
    tokenmap_path = root / 'vocab' / 'tokenmap.md'

    # No DB session required; annotate from rel_path tokens only
    annotated = annotate_proposals(proposals, None, fam_map, tokenmap_path)

    write_proposals(annotated, op)
    print(f'Wrote annotated proposals to {op} (input {ip}, proposals {len(proposals)})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

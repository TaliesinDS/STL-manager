#!/usr/bin/env python3
"""Apply franchise/character vocab matches to Variants (safe: dry-run default).

Usage:
  python scripts/apply_vocab_matches.py --limit 200
  python scripts/apply_vocab_matches.py --limit 200 --apply --batch 50

This script:
  - Builds alias maps for `franchise` and `character` domains from VocabEntry
  - Scans Variants (joined to Files) and finds tokens matching those maps
  - Proposes setting `variant.franchise` or `variant.codex_unit_name` when
    the corresponding DB field is empty
  - Dry-run prints proposals; `--apply` writes changes (commits in batches)

Conservative by default: only writes when target fields are empty; use
`--force` to overwrite.
"""
from __future__ import annotations
import sys
from pathlib import Path
import json
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from scripts.normalize_inventory import (
    tokens_from_variant,
    build_franchise_alias_map,
    build_character_alias_map,
    TABLETOP_HINTS,
)

from pathlib import Path
from typing import Dict, Tuple
import glob

# Global stoplist: tokens here are considered noise and will not be
# treated as franchise signals. Add short/common noisy words like
# 'big' which produced false positives.
GLOBAL_STOP_TOKENS = {"big", "large"}


def load_franchise_token_strengths(fr_dir: Path) -> Dict[str, Tuple[str, str]]:
    """Load franchise JSONs and return a mapping token -> (franchise_key, strength)
    strength is one of 'strong', 'weak', or 'stop'. If a token appears in multiple
    franchises the first encountered mapping is returned.
    """
    token_map: Dict[str, Tuple[str, str]] = {}
    json_files = glob.glob(str(fr_dir / "*.json"))
    for jf in sorted(json_files):
        try:
            j = json.loads(Path(jf).read_text(encoding='utf8'))
        except Exception:
            continue
        key = j.get('franchise') or j.get('key') or Path(jf).stem
        tokens = j.get('tokens', {}) or {}
        # strong_signals
        for s in tokens.get('strong_signals', []) or []:
            tk = s.strip().lower()
            if not tk or tk in GLOBAL_STOP_TOKENS:
                continue
            if tk not in token_map:
                token_map[tk] = (key, 'strong')
        # weak_signals
        for w in tokens.get('weak_signals', []) or []:
            tk = w.strip().lower()
            if not tk or tk in GLOBAL_STOP_TOKENS:
                continue
            if tk not in token_map:
                token_map[tk] = (key, 'weak')
        # stop_conflicts
        for st in tokens.get('stop_conflicts', []) or []:
            tk = st.strip().lower()
            if not tk or tk in GLOBAL_STOP_TOKENS:
                continue
            if tk not in token_map:
                token_map[tk] = (key, 'stop')
    return token_map


def propose_for_variant(session, v, franchise_map, character_map, token_strengths: Dict[str, Tuple[str, str]] | None = None, force=False):
    toks = tokens_from_variant(session, v)
    proposal = {"variant_id": v.id, "rel_path": v.rel_path, "proposed": {}}
    # Franchise (aggregated scoring across tokens)
    if (v.franchise in (None, "") ) or force:
        # Build per-franchise score and track vetoes from 'stop' tokens
        scores: Dict[str, float] = {}
        veto: set[str] = set()
        # weights (tunable)
        WEIGHT_STRONG = 10.0
        WEIGHT_WEAK = 1.0
        WEIGHT_CHARACTER = 8.0
        # normalize tokens and check tabletop hints
        t_clean_list = [t.strip('.,!?:;"\'()[]').lower() for t in toks if t and t.strip('.,!?:;"\'()[]').strip()]
        is_tabletop = any(t in TABLETOP_HINTS for t in t_clean_list)
        for t_clean in t_clean_list:
            if not t_clean:
                continue
            if t_clean in GLOBAL_STOP_TOKENS:
                # skip noisy global stop tokens
                continue
            # character signals
            if character_map and t_clean in character_map:
                # awarding character signal to any franchise tokens present
                # record character boost for all candidate franchises seen later
                # We'll apply character boosts below per-franchise when mapping tokens point to franchises
                pass
            # franchise token strengths
            if token_strengths and t_clean in token_strengths:
                fr_key, strength = token_strengths[t_clean]
                if strength == 'stop':
                    veto.add(fr_key)
                    continue
                if strength == 'strong':
                    scores[fr_key] = scores.get(fr_key, 0.0) + WEIGHT_STRONG
                elif strength == 'weak':
                    scores[fr_key] = scores.get(fr_key, 0.0) + WEIGHT_WEAK
            # fallback: if token maps via franchise_map but not present in token_strengths
            elif t_clean in franchise_map:
                # conservative: treat unknown-strength tokens as weak unless multiple tokens corroborate
                fr_key = franchise_map[t_clean]
                scores[fr_key] = scores.get(fr_key, 0.0) + WEIGHT_WEAK

        # apply character boosts: if any token is a character alias, boost franchises
        for t_clean in t_clean_list:
            if character_map and t_clean in character_map:
                # find franchises that appear in tokens for this variant and boost them
                for other_t in t_clean_list:
                    if other_t in token_strengths:
                        fr_key, _ = token_strengths[other_t]
                        scores[fr_key] = scores.get(fr_key, 0.0) + WEIGHT_CHARACTER
                    elif other_t in franchise_map:
                        fr_key = franchise_map[other_t]
                        scores[fr_key] = scores.get(fr_key, 0.0) + WEIGHT_CHARACTER

        # If tabletop hints are present, prefer franchises that are known tabletop
        # by giving them a small bonus when they appear in scores. We infer tabletop
        # franchises by checking whether 'warhammer' or 'sigmar' or common tabletop keys
        # are substrings of franchise key (conservative heuristic). This prevents
        # weak non-tabletop matches from overriding tabletop signals.
        if is_tabletop and scores:
            for fk in list(scores.keys()):
                if any(k in fk for k in ('warhammer', 'sigmar', 'age_of_sigmar', 'w40k', 'warhammer_40k', 'aos')):
                    scores[fk] = scores.get(fk, 0.0) + (WEIGHT_STRONG / 2.0)

        # Remove vetoed franchises
        for vkey in veto:
            if vkey in scores:
                del scores[vkey]

        # Decide winner: require a minimum margin between top two to avoid noisy weak ties
        winner = None
        if scores:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            top_key, top_score = sorted_scores[0]
            runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
            # require margin
            MARGIN = max(WEIGHT_STRONG * 0.5, 2.0)
            if (top_score - runner_up_score) >= MARGIN and top_score >= WEIGHT_WEAK:
                winner = top_key
        # If this variant appears to be tabletop, only accept a winner if it
        # is plausibly a tabletop franchise (conservative heuristic). This
        # prevents weak non-tabletop matches (e.g., 'big' -> metal_gear_solid)
        # from being applied to tabletop items like scenery/prints.
        if winner and is_tabletop:
            tabletop_like = any(k in winner for k in ('warhammer', 'sigmar', 'age_of_sigmar', 'w40k', 'warhammer_40k', 'aos'))
            if not tabletop_like:
                winner = None
        if winner:
            proposal["proposed"]["franchise"] = winner
            # find a token that maps to winner to record franchise_token
            for t in t_clean_list:
                if t in GLOBAL_STOP_TOKENS:
                    continue
                if token_strengths and t in token_strengths and token_strengths[t][0] == winner:
                    proposal["proposed"]["franchise_token"] = t
                    break
                if t in franchise_map and franchise_map[t] == winner:
                    proposal["proposed"]["franchise_token"] = t
                    break
    # Codex unit / character
    # Character hints: propose setting character_name/character_aliases.
    existing_char = getattr(v, 'character_name', None)
    if (existing_char in (None, "")) or force:
        for t in toks:
            t_clean = t.strip('.,!?:;"\'()[]').lower()
            if not t_clean:
                continue
            if t_clean in character_map:
                proposal["proposed"]["character_name"] = character_map[t_clean]
                proposal["proposed"]["character_aliases"] = [t_clean]
                break
    return proposal


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Apply franchise/character vocab matches to Variants")
    ap.add_argument('--limit', type=int, default=200, help='Max variants to examine')
    ap.add_argument('--batch', type=int, default=50, help='Commit batch size when applying')
    ap.add_argument('--apply', action='store_true', help='Write proposed changes to DB')
    ap.add_argument('--force', action='store_true', help='Overwrite existing fields when applying')
    args = ap.parse_args(argv)

    results = []
    with get_session() as session:
        franchise_map = build_franchise_alias_map(session)
        character_map = build_character_alias_map(session)
        # Load per-franchise token strengths from vocab/franchises JSONs so
        # we can treat weak signals conservatively (e.g., 'sw', 'gate').
        fr_dir = PROJECT_ROOT / 'vocab' / 'franchises'
        token_strengths = load_franchise_token_strengths(fr_dir)

        q = session.query(Variant).join(Variant.files).distinct().limit(args.limit)
        for v in q:
            p = propose_for_variant(session, v, franchise_map, character_map, token_strengths=token_strengths, force=args.force)
            if p.get("proposed"):
                results.append(p)

        print(json.dumps({"dry_run": not args.apply, "count": len(results), "proposals": results[:50]}, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no changes written. Re-run with --apply to commit proposals.")
            return 0

        # Apply proposals in batches
        applied = 0
        to_commit = []
        for p in results:
            v = session.query(Variant).filter_by(id=p["variant_id"]).one_or_none()
            if not v:
                continue
            prop = p.get("proposed", {})
            any_changed = False
            if "franchise" in prop and ((v.franchise in (None, "")) or args.force):
                v.franchise = prop["franchise"]
                any_changed = True
            # Apply character proposals
            if "character_name" in prop and ((getattr(v, 'character_name', None) in (None, "")) or args.force):
                v.character_name = prop["character_name"]
                # set aliases if provided
            if "character_aliases" in prop and ((getattr(v, 'character_aliases', None) in (None, [])) or args.force):
                v.character_aliases = prop["character_aliases"]
                any_changed = True
            if any_changed:
                to_commit.append(v)
            if len(to_commit) >= args.batch:
                try:
                    session.commit()
                    applied += len(to_commit)
                    to_commit = []
                except Exception as e:
                    print(f"Commit failed: {e}")
                    raise

        if to_commit:
            session.commit()
            applied += len(to_commit)

        print(f"Applied changes to {applied} variants.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))

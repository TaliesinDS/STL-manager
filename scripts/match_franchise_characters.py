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

ROOT = Path(__file__).resolve().parent.parent
FR_DIR = ROOT / 'vocab' / 'franchises'

import sys
# Ensure project root is on sys.path so `from db...` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant

# Reuse helper functions from normalize_inventory
from scripts.normalize_inventory import tokens_from_variant, apply_updates_to_variant, TABLETOP_HINTS
from scripts.quick_scan import classify_token


# Certain character aliases are too generic to stand alone (e.g., 'angel').
# Require additional supporting franchise evidence (another alias or
# franchise token) before accepting these as valid character/franchise matches.
AMBIGUOUS_ALIASES = {"angel"}

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
        # franchise aliases
        for a in (j.get('aliases') or []):
            fam[str(a).strip().lower()] = franchise_key
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

        # tokens (strong/weak signals) at franchise level
        tokens_block = j.get('tokens') or {}
        strong = set((t or '').strip().lower() for t in (tokens_block.get('strong_signals') or []))
        weak = set((t or '').strip().lower() for t in (tokens_block.get('weak_signals') or []))
        f_tokens[franchise_key] = {'strong': strong, 'weak': weak}

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


def process(apply: bool, batch: int, out: str | None = None):
    fam, cam, f_tokens = load_franchise_maps(FR_DIR)
    proposals = []
    with get_session() as session:
        # only consider variants that currently have no franchise
        q = session.query(Variant).join(Variant.files).distinct().filter(Variant.franchise.is_(None))
        total = q.count()
        print(f"Found {total} candidate variants (franchise is NULL).")
        offset = 0
        while True:
            rows = q.limit(batch).offset(offset).all()
            if not rows:
                break
            for v in rows:
                tokens = tokens_from_variant(session, v)
                if not tokens:
                    continue
                token_list = list(tokens)
                # Tabletop context gate: only treat as tabletop when explicit tabletop
                # hints are present AND there is no stronger franchise/character alias
                # evidence. This prevents blocking when we clearly have a known IP
                # (e.g., queens_blade: 'menace').
                has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
                # Treat ambiguous aliases as insufficient evidence on their own
                has_alias_evidence = any(t in fam for t in token_list) or any((t in cam) and (t not in AMBIGUOUS_ALIASES) for t in token_list)
                is_tabletop_ctx = has_tabletop_hint and not has_alias_evidence

                inferred = {
                    'franchise': None,
                    'character_hint': None,
                    'character_name': None,
                    'faction_hint': None,
                    'normalization_warnings': [],
                    'token_version': None,
                }

                # count franchise alias matches
                alias_count = sum(1 for t in token_list if t in fam)
                has_char_any = any(t in cam for t in token_list)
                has_char_strong = False

                def short_or_numeric(tok: str) -> bool:
                    tl = tok.lower()
                    if tl.isdigit():
                        return True
                    if len(tl) <= 2:
                        return True
                    # patterns like '2b', '9s', 'a2'
                    import re as _re
                    return bool(_re.fullmatch(r"[a-z]\d|\d[a-z]", tl))

                def has_supporting_fr_tokens(fr_key: str, exclude_token: str | None = None) -> bool:
                    """Return True if there is independent evidence of this franchise in tokens.
                    Evidence means: any token (not equal to the current alias) that is either
                    - a strong/weak signal listed for the franchise, or
                    - an alias mapping to the franchise via fam.
                    """
                    f_tok = f_tokens.get(fr_key, {'strong': set(), 'weak': set()})
                    sigs = (f_tok.get('strong', set()) | f_tok.get('weak', set()))
                    for tt in token_list:
                        if exclude_token and tt == exclude_token:
                            continue
                        if tt in sigs:
                            return True
                        if tt in fam and fam[tt] == fr_key:
                            return True
                    return False

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
                            # Consider token strong if explicitly in strong_signals, or
                            # heuristically if longer than 2 and not purely numeric.
                            strong = (t in f_tok.get('strong', set())) or (len(t) > 2 and not t.isdigit()) or alias_count > 1 or has_char_strong
                            if is_tabletop_ctx:
                                # For tabletop items, record hint but do not set
                                # franchise; downstream processes may use this hint.
                                inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                                if not inferred.get('faction_hint'):
                                    inferred['faction_hint'] = t
                                break
                            if strong:
                                # For non-tabletop strong matches, set franchise but
                                # do not populate a general faction hint.
                                inferred['franchise'] = candidate_fr
                                break
                            else:
                                # record as hint only
                                if not inferred.get('faction_hint'):
                                    inferred['faction_hint'] = t
                                inferred.setdefault('normalization_warnings', []).append('faction_without_system')
                                break

                # Set token_version from tokenmap if available (reuse normalize behavior)
                # We don't have load_tokenmap here; leave token_version None so other scripts set it.

                changed = apply_updates_to_variant(v, inferred, session, force=False)
                if changed:
                    proposals.append({'variant_id': v.id, 'rel_path': v.rel_path, 'changes': changed})
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
                while True:
                    rows = q_apply.limit(batch).offset(offset).all()
                    if not rows:
                        break
                    any_changed = False
                    for v in rows:
                        tokens = tokens_from_variant(write_sess, v)
                        if not tokens:
                            continue
                        token_list = list(tokens)
                        has_tabletop_hint = any(t in TABLETOP_HINTS for t in token_list)
                        has_alias_evidence = any(t in fam for t in token_list) or any((t in cam) and (t not in AMBIGUOUS_ALIASES) for t in token_list)
                        is_tabletop_ctx = has_tabletop_hint and not has_alias_evidence

                        inferred = {
                            'franchise': None,
                            'character_hint': None,
                            'character_name': None,
                            'faction_hint': None,
                            'normalization_warnings': [],
                            'token_version': None,
                        }
                        alias_count = sum(1 for t in token_list if t in fam)
                        has_char_strong = False

                        def short_or_numeric(tok: str) -> bool:
                            tl = tok.lower()
                            if tl.isdigit():
                                return True
                            if len(tl) <= 2:
                                return True
                            import re as _re
                            return bool(_re.fullmatch(r"[a-z]\d|\d[a-z]", tl))

                        def has_supporting_fr_tokens(fr_key: str, exclude_token: str | None = None) -> bool:
                            f_tok = f_tokens.get(fr_key, {'strong': set(), 'weak': set()})
                            sigs = (f_tok.get('strong', set()) | f_tok.get('weak', set()))
                            for tt in token_list:
                                if exclude_token and tt == exclude_token:
                                    continue
                                if tt in sigs:
                                    return True
                                if tt in fam and fam[tt] == fr_key:
                                    return True
                            return False

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
                                    strong = (t in f_tok.get('strong', set())) or (len(t) > 2 and not t.isdigit()) or alias_count > 1 or has_char_strong
                                    if is_tabletop_ctx:
                                        inferred.setdefault('normalization_warnings', []).append('tabletop_no_franchise')
                                        if not inferred.get('faction_hint'):
                                            inferred['faction_hint'] = t
                                        break
                                    if strong:
                                        inferred['franchise'] = candidate_fr
                                        break
                                    else:
                                        inferred.setdefault('normalization_warnings', []).append('faction_without_system')
                                        break

                        changed = apply_updates_to_variant(v, inferred, write_sess, force=False)
                        if changed:
                            any_changed = True
                    if any_changed:
                        write_sess.commit()
                    offset += batch
            print('Apply complete.')


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Match variants to franchise & characters from franchise manifests')
    ap.add_argument('--batch', type=int, default=200)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', type=str, help='Write dry-run proposals + summary to this JSON file')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    process(apply=args.apply, batch=args.batch, out=args.out)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))

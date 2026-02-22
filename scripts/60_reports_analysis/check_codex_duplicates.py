#!/usr/bin/env python3
"""Deduplicate HH codex units and aliases, compare vs backup, or enforce flow-style list formatting.

Rehomed from scripts root; defaults generalized to repo-relative paths.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as DQ

ROOT = Path(__file__).resolve().parents[2]


def _yaml() -> YAML:
    y = YAML(typ='rt')  # round-trip to preserve formatting/comments
    y.preserve_quotes = True
    y.allow_duplicate_keys = True
    y.width = 4096
    return y


def load_yaml(path: str):
    yaml = _yaml()
    with open(path, encoding='utf-8') as f:
        return yaml.load(f)


def save_yaml(data, path: str):
    yaml = _yaml()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f)


def _rewrite_aliases_inline_in_text(path: str):
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.lstrip(' ')
        indent_len = len(line) - len(stripped)
        if stripped.startswith('aliases:') and stripped.strip() == 'aliases:':
            items = []
            j = i + 1
            while j < n:
                l2 = lines[j]
                s2 = l2.lstrip(' ')
                ind2 = len(l2) - len(s2)
                if ind2 <= indent_len:
                    break
                s2_stripped = s2.strip()
                if s2_stripped.startswith('- '):
                    val = s2_stripped[2:].strip()
                    items.append(val)
                    j += 1
                    continue
                else:
                    break
            if items:
                inline = ', '.join(items)
                out.append(' ' * indent_len + f'aliases: [{inline}]\n')
                i = j
                continue
        out.append(line)
        i += 1

    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(out)


def _to_commented_seq(lst) -> CommentedSeq:
    if isinstance(lst, CommentedSeq):
        return lst
    cs = CommentedSeq(lst if lst is not None else [])
    return cs


def _set_flow_style(seq: CommentedSeq, flow: bool = True):
    try:
        seq.yaml_set_flow_style(flow)
    except Exception:
        pass
    try:  # type: ignore[attr-defined]
        seq.fa.set_flow_style(flow)
    except Exception:
        pass
    try:  # type: ignore[attr-defined]
        seq.fa.flow_style = flow
    except Exception:
        pass


def enforce_flow_style(data: Any, debug: bool = False) -> Any:
    root = data
    try:
        w30k = root['codex_units']['warhammer_30k']
    except Exception:
        return data

    c_meta_editions = 0
    c_ag_editions = 0
    c_legion_groups = 0
    c_units_aliases = 0
    c_units_legal = 0
    c_units_available = 0

    meta = w30k.get('meta') or CommentedMap()
    if 'editions' in meta:
        editions = _to_commented_seq(meta['editions'])
        _set_flow_style(editions, True)
        meta['editions'] = editions
        c_meta_editions += 1

    ag = w30k.get('availability_groups') or {}
    if isinstance(ag, dict):
        for grp in ag.values():
            if isinstance(grp, dict) and 'legal_in_editions' in grp:
                le = _to_commented_seq(grp.get('legal_in_editions'))
                _set_flow_style(le, True)
                grp['legal_in_editions'] = le
                c_ag_editions += 1

    factions = w30k.get('factions') or {}
    la = None
    if isinstance(factions, dict):
        la = factions.get('legiones_astartes')
    if isinstance(la, dict):
        legions = la.get('legions') or {}
        if isinstance(legions, dict):
            for legion in legions.values():
                if isinstance(legion, dict) and 'include_groups' in legion:
                    inc = _to_commented_seq(legion.get('include_groups'))
                    _set_flow_style(inc, True)
                    legion['include_groups'] = inc
                    c_legion_groups += 1

    units = w30k.get('units') or {}
    if isinstance(units, dict):
        for unit in units.values():
            if not isinstance(unit, dict):
                continue
            for key in ('aliases', 'legal_in_editions', 'available_to'):
                if key in unit:
                    if key == 'aliases':
                        raw = unit.get(key) or []
                        new_seq = CommentedSeq([DQ(str(x)) for x in list(raw)])
                        _set_flow_style(new_seq, True)
                        unit[key] = new_seq
                        try:
                            _set_flow_style(unit[key], True)
                        except Exception:
                            pass
                        c_units_aliases += 1
                    else:
                        seq = _to_commented_seq(unit.get(key))
                        _set_flow_style(seq, True)
                        unit[key] = seq
                        if key == 'legal_in_editions':
                            c_units_legal += 1
                        elif key == 'available_to':
                            c_units_available += 1

    if debug:
        print(f"Flow-style enforcement: meta.editions={c_meta_editions}, ag.legal_in_editions={c_ag_editions}, legions.include_groups={c_legion_groups}, units.aliases={c_units_aliases}, units.legal_in_editions={c_units_legal}, units.available_to={c_units_available}")

    return data


def dedupe_units_and_aliases(data: Any) -> Any:
    w30k = data['codex_units']['warhammer_30k']
    units = w30k['units']

    seen_keys = set()
    deduped_units: Dict[str, Any] = CommentedMap()
    for key, value in units.items():
        if key not in seen_keys:
            deduped_units[key] = value
            seen_keys.add(key)

    for unit_key, unit in deduped_units.items():
        aliases = unit.get('aliases')
        if not aliases:
            continue
        seen_local = set()
        new_aliases: List[str] = []
        for alias in list(aliases):
            a = str(alias).lower()
            if a not in seen_local:
                new_aliases.append(alias)
                seen_local.add(a)
        cs = _to_commented_seq(new_aliases)
        _set_flow_style(cs, True)
        unit['aliases'] = cs

    w30k['units'] = deduped_units
    return data


def compare_files(current_path: str, backup_path: str):
    cur = load_yaml(current_path)
    bak = load_yaml(backup_path)

    u_cur = cur['codex_units']['warhammer_30k']['units']
    u_bak = bak['codex_units']['warhammer_30k']['units']

    k_cur = set(u_cur.keys())
    k_bak = set(u_bak.keys())

    missing_vs_backup = sorted(list(k_bak - k_cur))
    added_vs_backup = sorted(list(k_cur - k_bak))

    print('Units missing vs backup:', missing_vs_backup)
    print('Units added vs backup:', added_vs_backup)

    field_diffs = []
    alias_diffs = []
    for k in sorted(k_cur & k_bak):
        a = u_cur[k]
        b = u_bak[k]
        for field in ['name', 'role', 'base_profile', 'available_to', 'legal_in_editions']:
            if a.get(field) != b.get(field):
                field_diffs.append((k, field, b.get(field), a.get(field)))
        a_alias = [str(x).lower() for x in (a.get('aliases') or [])]
        b_alias = [str(x).lower() for x in (b.get('aliases') or [])]
        a_set, b_set = set(a_alias), set(b_alias)
        if a_set != b_set:
            alias_diffs.append((k, sorted(list(b_set - a_set)), sorted(list(a_set - b_set))))

    if field_diffs:
        print('\nField diffs (unit, field, backup_value -> current_value):')
        for unit, field, bval, aval in field_diffs:
            print(f"- {unit}.{field}: {bval} -> {aval}")
    else:
        print('\nNo field diffs for name/role/base_profile/available_to/legal_in_editions.')

    if alias_diffs:
        print('\nAlias set diffs (backup_only vs new_only):')
        for unit, backup_only, new_only in alias_diffs:
            print(f"- {unit}: backup_only={backup_only}; new_only={new_only}")
    else:
        print('\nNo alias set diffs.')


def main():
    parser = argparse.ArgumentParser(description='Deduplicate HH codex units and aliases, compare vs backup, or enforce flow-style list formatting.')
    default_input = str((ROOT / 'vocab' / 'codex_units_horus_heresy.yaml').resolve())
    default_output = str((ROOT / 'vocab' / 'codex_units_horus_heresy.deduped.yaml').resolve())
    default_backup = str((ROOT / 'vocab' / 'codex_units_horus_heresy.yaml.bak').resolve())
    parser.add_argument('--input', '-i', default=default_input, help='Input YAML file path')
    parser.add_argument('--output', '-o', default=default_output, help='Output YAML file path (when not using --inplace)')
    parser.add_argument('--inplace', action='store_true', help='Write changes back to the input file')
    parser.add_argument('--compare', action='store_true', help='Compare current input against backup and print diffs')
    parser.add_argument('--backup', '-b', default=default_backup, help='Backup YAML file path (for compare mode)')
    parser.add_argument('--enforce-flow', action='store_true', help='Enforce flow-style lists for selected fields (formatting only)')
    parser.add_argument('--debug-flow', action='store_true', help='Print debug info while enforcing flow style')
    args = parser.parse_args()

    if args.compare:
        compare_files(args.input, args.backup)
        return

    data = load_yaml(args.input)

    if args.enforce_flow and not args.inplace:
        formatted = enforce_flow_style(data, debug=args.debug_flow)
        save_yaml(formatted, args.output)
        _rewrite_aliases_inline_in_text(args.output)
        print('Flow-style formatting enforced. Output written to:', args.output)
        return

    if args.enforce_flow and args.inplace:
        formatted = enforce_flow_style(data, debug=args.debug_flow)
        save_yaml(formatted, args.input)
        _rewrite_aliases_inline_in_text(args.input)
        print('Flow-style formatting enforced in-place for:', args.input)
        return

    data = dedupe_units_and_aliases(data)
    data = enforce_flow_style(data, debug=args.debug_flow)
    out_path = args.input if args.inplace else args.output
    save_yaml(data, out_path)
    _rewrite_aliases_inline_in_text(out_path)
    print('Deduplication complete. Output written to: ' + out_path)


if __name__ == '__main__':
    main()

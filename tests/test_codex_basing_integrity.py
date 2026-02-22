import re
from pathlib import Path

# Resolve codex path relative to the repository root (parent of this tests/ directory)
REPO_ROOT = Path(__file__).resolve().parents[1]
CODEx_PATH = REPO_ROOT / "vocab" / "codex_units_w40k.yaml"


def _read_lines():
    assert CODEx_PATH.exists(), f"Missing codex file: {CODEx_PATH}"
    return CODEx_PATH.read_text(encoding="utf-8").splitlines()


def _get_meta_base_keys(lines):
    base_keys = set()
    inside_meta = False
    inside_bp = False
    meta_indent = None
    bp_indent = None
    for i, line in enumerate(lines, start=1):
        if not inside_meta and re.match(r"^\s*meta:\s*$", line):
            inside_meta = True
            meta_indent = len(line) - len(line.lstrip(" "))
            continue
        if inside_meta:
            indent = len(line) - len(line.lstrip(" "))
            if indent <= meta_indent and line.strip() and not line.lstrip().startswith("#"):
                inside_meta = False
                inside_bp = False
            if not inside_bp and re.match(r"^\s*base_profiles:\s*$", line):
                inside_bp = True
                bp_indent = len(line) - len(line.lstrip(" "))
                continue
            if inside_bp:
                if line.strip() == "" or line.lstrip().startswith("#"):
                    continue
                this_indent = len(line) - len(line.lstrip(" "))
                if this_indent <= bp_indent:
                    inside_bp = False
                    continue
                m = re.match(r"^\s*([\w_]+):\s*\{", line)
                if m:
                    base_keys.add(m.group(1))
    return base_keys


def _find_availability_groups_range(lines):
    av_start = None
    av_indent = None
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^(\s*)availability_groups:\s*$", line)
        if m:
            av_start = i
            av_indent = len(m.group(1))
            break
    if av_start is None:
        return None, None, None
    av_end = None
    for j in range(av_start + 1, len(lines) + 1):
        line = lines[j - 1]
        if line.strip() and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip(" "))
            if indent <= av_indent and not re.match(r"^\s*availability_groups:\s*$", line):
                av_end = j - 1
                break
    if av_end is None:
        av_end = len(lines)
    return av_start, av_end, av_indent


def _units_missing_base_profile(lines):
    # Walk the units block and track base_profile presence per unit
    inside_units = False
    units_indent = None
    unit_key_indent = None
    current_unit = None
    has_base = False
    missing = []
    prop_key_re = re.compile(r"^\s*([\w\-']+):\s*$")

    for i, line in enumerate(lines):
        if not inside_units:
            if re.match(r"^(\s*)units:\s*$", line):
                units_indent = len(line) - len(line.lstrip(" "))
                inside_units = True
            continue
        indent = len(line) - len(line.lstrip(" "))
        if not line.strip():
            continue
        # exit units
        if indent <= units_indent and not line.lstrip().startswith('#'):
            if current_unit is not None and not has_base:
                missing.append(current_unit)
            break
        m = prop_key_re.match(line)
        if m:
            key = m.group(1)
            if unit_key_indent is None and indent > units_indent:
                unit_key_indent = indent
            if indent == unit_key_indent:
                if current_unit is not None and not has_base:
                    missing.append(current_unit)
                current_unit = key
                has_base = False
                continue
        if current_unit is not None and 'base_profile:' in line:
            has_base = True
    if inside_units and current_unit is not None and not has_base:
        missing.append(current_unit)
    return missing


def _get_meta_editions(lines):
    # Extract editions list from meta.editions: ["8th", "9th", "10th"]
    editions = set()
    inside_meta = False
    for i, line in enumerate(lines, start=1):
        if not inside_meta and re.match(r"^\s*meta:\s*$", line):
            inside_meta = True
            continue
        if inside_meta:
            if re.match(r"^\s*editions:\s*\[(.*)\]\s*$", line):
                inner = re.findall(r"\"([^\"]+)\"", line)
                editions.update(inner)
                break
            # break out if meta ends
            indent = len(line) - len(line.lstrip(" "))
            if indent == 0 and line.strip():
                break
    return editions


def _get_factions_and_chapters(lines):
    # Collect top-level faction keys under factions:, and chapters under space_marines
    factions = set()
    chapters = set()
    inside_factions = False
    factions_indent = None
    inside_sm_chapters = False
    sm_chapters_indent = None
    for i, line in enumerate(lines, start=1):
        if not inside_factions and re.match(r"^\s*factions:\s*$", line):
            inside_factions = True
            factions_indent = len(line) - len(line.lstrip(" "))
            continue
        if inside_factions:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            indent = len(line) - len(line.lstrip(' '))
            m = re.match(r"^\s*([\w_]+):\s*$", line)
            if m and indent == factions_indent + 2:
                key = m.group(1)
                factions.add(key)
                inside_sm_chapters = (key == 'space_marines')
                sm_chapters_indent = None
                continue
            if inside_sm_chapters:
                if re.match(r"^\s*chapters:\s*$", line):
                    sm_chapters_indent = indent
                    continue
                if sm_chapters_indent is not None:
                    m2 = re.match(r"^\s*([\w_]+):\s*$", line)
                    if m2 and indent == sm_chapters_indent + 2:
                        chapters.add(m2.group(1))
                    # leaving chapters map
                    if indent <= factions_indent:
                        inside_sm_chapters = False
    return factions, chapters


def test_codex_basing_integrity():
    lines = _read_lines()

    # A) base_profile must not appear outside units (except default_base_profile under availability_groups)
    inside_units = False
    misplaced = []
    for i, line in enumerate(lines, start=1):
        if not inside_units and re.match(r"^\s*units:\s*$", line):
            inside_units = True
        if 'base_profile:' in line and 'default_base_profile:' not in line and not inside_units:
            misplaced.append(i)
    assert misplaced == [], f"base_profile outside units at lines: {misplaced[:10]}{'...' if len(misplaced)>10 else ''}"

    # B) Collect allowed base keys from meta.base_profiles
    base_keys = _get_meta_base_keys(lines)
    assert base_keys, "No base profile keys found in meta.base_profiles"

    # C) All used base_profile values must exist in meta.base_profiles
    unknown_used = []
    for i, line in enumerate(lines, start=1):
        m = re.search(r"base_profile:\s*([\w_]+)", line)
        if m and 'default_base_profile' not in line:
            val = m.group(1)
            if val not in base_keys:
                unknown_used.append((i, val))
    assert unknown_used == [], f"Unknown base_profile values: {unknown_used[:10]}{'...' if len(unknown_used)>10 else ''}"

    # D) default_base_profile values must exist too
    unknown_default = []
    for i, line in enumerate(lines, start=1):
        m = re.search(r"default_base_profile:\s*([\w_]+)", line)
        if m and m.group(1) not in base_keys:
            unknown_default.append((i, m.group(1)))
    assert unknown_default == [], f"Unknown default_base_profile values: {unknown_default}"

    # E) No duplicates within availability_groups.*.units lists
    av_start, av_end, av_indent = _find_availability_groups_range(lines)
    if av_start is not None:
        seen_per_group = {}
        dups = []
        current_group = None
        group_indent = None
        in_units_list = False
        units_list_indent = None
        for i in range(av_start + 1, av_end + 1):
            line = lines[i - 1]
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            indent = len(line) - len(line.lstrip(' '))
            mg = re.match(r"^\s*([\w_]+):\s*$", line)
            if mg and (group_indent is None or indent <= group_indent):
                if indent == av_indent + 2:
                    current_group = mg.group(1)
                    group_indent = indent
                    in_units_list = False
                    seen_per_group.setdefault(current_group, set())
                    continue
            if current_group:
                if re.match(r"^\s*units:\s*$", line) and indent == group_indent + 2:
                    in_units_list = True
                    units_list_indent = indent
                    continue
                if in_units_list and indent <= units_list_indent and mg:
                    in_units_list = False
                if in_units_list:
                    m2 = re.match(r"^\s*-\s*([\w_]+)\s*$", line)
                    if m2:
                        u = m2.group(1)
                        if u in seen_per_group[current_group]:
                            dups.append((i, current_group, u))
                        else:
                            seen_per_group[current_group].add(u)
        assert dups == [], f"Duplicate units in availability_groups: {dups[:10]}{'...' if len(dups)>10 else ''}"

    # F) Every unit has a base_profile
    missing_units = _units_missing_base_profile(lines)
    assert missing_units == [], f"Units missing base_profile: {missing_units[:10]}{'...' if len(missing_units)>10 else ''}"

    # G) Schema hygiene: editions and faction references
    valid_editions = _get_meta_editions(lines)
    assert valid_editions, "No editions found in meta.editions"

    factions, chapters = _get_factions_and_chapters(lines)
    assert 'space_marines' in factions, "Expected 'space_marines' faction present"

    # Scan units block for legal_in_editions and available_to/excluded_from
    inside_units = False
    unit_key_indent = None
    units_indent = None
    current_unit = None
    problems = []
    for i, line in enumerate(lines, start=1):
        if not inside_units and re.match(r"^\s*units:\s*$", line):
            inside_units = True
            units_indent = len(line) - len(line.lstrip(' '))
            continue
        if inside_units:
            indent = len(line) - len(line.lstrip(' '))
            if indent <= units_indent and line.strip() and not line.lstrip().startswith('#'):
                break
            mkey = re.match(r"^\s*([\w\-']+):\s*$", line)
            if mkey and (unit_key_indent is None or indent == unit_key_indent or indent == units_indent + 2):
                if unit_key_indent is None:
                    unit_key_indent = indent
                current_unit = mkey.group(1)
                continue
            # editions
            med = re.search(r"legal_in_editions:\s*\[(.*)\]", line)
            if med:
                inner = re.findall(r"\"([^\"]+)\"", line)
                bad = [e for e in inner if e not in valid_editions]
                if bad:
                    problems.append((i, current_unit, 'illegal_editions', bad))
            # faction refs (simple tokens array on one line)
            for key in ("available_to", "excluded_from"):
                mf = re.search(rf"{key}:\s*\[(.*)\]", line)
                if mf:
                    refs = re.findall(r"\"([^\"]+)\"", line)
                    for ref in refs:
                        if ref.endswith('/*'):
                            base = ref[:-2]
                            if base not in factions:
                                problems.append((i, current_unit, f'{key}_unknown_super', ref))
                        elif '/' in ref:
                            head, tail = ref.split('/', 1)
                            if head == 'space_marines':
                                if tail not in chapters and tail != '*':
                                    problems.append((i, current_unit, f'{key}_unknown_chapter', ref))
                            elif head not in factions:
                                problems.append((i, current_unit, f'{key}_unknown_faction', ref))
                        else:
                            if ref not in factions:
                                problems.append((i, current_unit, f'{key}_unknown_faction', ref))
    assert problems == [], f"Schema issues: {problems[:5]}{'...' if len(problems)>5 else ''}"

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

MD_HEADER_RE = re.compile(r"^##\s+.+\(`([a-z0-9_]+)`\)\s*$")
BULLET_RE = re.compile(r"^\s*-\s+([a-z0-9_]+)\s+—\s+aliases:\s*\[", re.IGNORECASE)


def parse_proposals(md_path: Path) -> Dict[str, List[Tuple[str, List[str]]]]:
    out: Dict[str, List[Tuple[str, List[str]]]] = {}
    section: str | None = None
    pending_alias = None
    pending_canonical = None
    with md_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = MD_HEADER_RE.match(line)
            if m:
                section = m.group(1)
                continue
            if section is None:
                continue
            if pending_alias is not None:
                # accumulate until closing bracket
                pending_alias += line
                if "]" in line:
                    # finalize
                    aliases = re.findall(r'"([^"]+)"', pending_alias)
                    out.setdefault(section, []).append((pending_canonical, aliases))  # type: ignore[arg-type]
                    pending_alias = None
                    pending_canonical = None
                continue
            m2 = BULLET_RE.match(line)
            if m2:
                canonical = m2.group(1)
                # capture alias content starting from this line
                alias_part = line.split("[", 1)[1]
                if "]" in alias_part:
                    aliases = re.findall(r'"([^"]+)"', alias_part)
                    out.setdefault(section, []).append((canonical, aliases))
                else:
                    pending_alias = alias_part
                    pending_canonical = canonical
    return out


def load_existing_canonicals(json_path: Path) -> set[str]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return {c.get("canonical") for c in data.get("characters", []) if isinstance(c, dict) and c.get("canonical")}


def insert_characters_preserving_style(json_path: Path, items: List[Tuple[str, List[str]]]) -> bool:
    """Insert new character entries into the characters array by text insertion to minimize reformatting.

    Returns True if file was modified.
    """
    text = json_path.read_text(encoding="utf-8")
    # Find the characters array bounds
    chars_key_idx = text.find("\"characters\"")
    if chars_key_idx == -1:
        return False
    open_bracket_idx = text.find("[", chars_key_idx)
    if open_bracket_idx == -1:
        return False
    # Find matching closing bracket for this array using square-bracket depth
    depth = 0
    end_idx = -1
    for i in range(open_bracket_idx, len(text)):
        ch = text[i]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end_idx = i
                break
    if end_idx == -1:
        return False

    # Determine if array currently empty (only whitespace/comments between brackets)
    array_content = text[open_bracket_idx + 1:end_idx].strip()
    is_empty = len(array_content) == 0

    # Determine indentation
    # Look backward from end_idx to find last non-empty line inside array
    _pre_array = text[:open_bracket_idx]
    _post_array = text[end_idx + 1:]
    before = text[open_bracket_idx + 1:end_idx]
    lines = before.splitlines()
    indent = "  "
    for ln in lines:
        s = ln.lstrip()
        if s.startswith('{'):
            indent = ln[: len(ln) - len(s)]
            break
    # Fallback indent if none found
    if not indent:
        indent = "  "

    # Prepare new entries text
    def fmt_entry(canon: str, aliases: List[str]) -> str:
        alias_list = ", ".join(f'"{a}"' for a in aliases)
        return f'{indent}{{"canonical": "{canon}", "aliases": [{alias_list}]}}'

    new_entries = [fmt_entry(c, a) for c, a in items]
    if not new_entries:
        return False

    insertion = "\n" + (",\n".join(new_entries)) + "\n"
    # If array not empty, ensure a leading comma before our first new entry
    if not is_empty:
        insertion = "," + insertion

    new_text = text[:end_idx] + insertion + text[end_idx:]
    json_path.write_text(new_text, encoding="utf-8")
    return True


def main():
    repo = Path(__file__).resolve().parents[2]
    md_path = repo / "docs" / "franchise_character_proposals.md"
    vocab_dir = repo / "vocab" / "franchises"

    proposals = parse_proposals(md_path)
    modified_files: List[Path] = []
    for section_id, items in proposals.items():
        manifest = vocab_dir / f"{section_id}.json"
        if not manifest.exists():
            continue  # only apply to existing manifests
        existing = load_existing_canonicals(manifest)
        to_add = [(c, a) for c, a in items if c not in existing]
        if not to_add:
            continue
        if insert_characters_preserving_style(manifest, to_add):
            modified_files.append(manifest)

    if modified_files:
        print("Updated manifests:")
        for p in modified_files:
            print(" -", p.relative_to(repo))
    else:
        print("No manifests required updates (all canonicals already present or no matching manifests).")


if __name__ == "__main__":
    main()

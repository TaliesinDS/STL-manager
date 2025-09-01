import argparse
import json
import re
from pathlib import Path


def load_existing_canonicals(franchises_dir: Path) -> set[str]:
    canonicals: set[str] = set()
    for fp in franchises_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        chars = data.get("characters") or []
        for ch in chars:
            can = ch.get("canonical")
            if isinstance(can, str) and can:
                canonicals.add(can)
    return canonicals


def dedup_proposals(md_path: Path, existing: set[str]) -> tuple[int, int]:
    lines = md_path.read_text(encoding="utf-8").splitlines()

    bullet_re = re.compile(r"^\s*-\s+([a-z0-9_]+)\s+—\s+aliases:\s*\[", re.IGNORECASE)
    section_re = re.compile(r"^## ")
    title_line = "# Franchise Character Proposals (Review List)"

    # Pass 1: remove bullets that already exist in manifests; skip repeated title blocks; handle multi-line alias arrays
    out_lines: list[str] = []
    removed_existing = 0
    skip_alias_block = False
    seen_title = False
    seen_intro = False
    for line in lines:
        # Strip duplicated intro blocks that start with 'Purpose:' after the first
        if not seen_intro and line.strip().startswith("Purpose:"):
            seen_intro = True
        elif seen_intro and line.strip().startswith("Purpose:"):
            # skip until next horizontal rule ('---')
            continue
        elif seen_intro and line.strip().startswith("---"):
            # if we were skipping a duplicate intro, resume normally
            pass
        if skip_alias_block:
            if "]" in line:
                skip_alias_block = False
            continue
        if line.strip() == title_line:
            if seen_title:
                # drop repeated title
                continue
            seen_title = True
        m = bullet_re.match(line)
        if m:
            canonical = m.group(1)
            if canonical in existing:
                removed_existing += 1
                if "]" not in line:
                    skip_alias_block = True
                continue
        out_lines.append(line)

    # Pass 2: de-duplicate bullets within the document (keep first occurrence)
    seen_doc: set[str] = set()
    deint_lines: list[str] = []
    removed_internal = 0
    skip_alias_block = False
    last_kept_canonical = None
    for line in out_lines:
        if skip_alias_block:
            # Attach alias block only if previous bullet kept; otherwise skip
            if "]" in line:
                skip_alias_block = False
            if last_kept_canonical is not None:
                deint_lines.append(line)
            continue
        m = bullet_re.match(line)
        if m:
            canonical = m.group(1)
            if canonical in seen_doc:
                removed_internal += 1
                if "]" not in line:
                    skip_alias_block = True
                last_kept_canonical = None
                continue
            seen_doc.add(canonical)
            deint_lines.append(line)
            last_kept_canonical = canonical
            if "]" not in line:
                skip_alias_block = True
        else:
            last_kept_canonical = None
            deint_lines.append(line)

    # Pass 3: remove empty sections (no kept bullets)
    final_lines: list[str] = []
    i = 0
    n = len(deint_lines)
    while i < n:
        line = deint_lines[i]
        if section_re.match(line):
            start = i
            j = i + 1
            has_bullets = False
            while j < n and not section_re.match(deint_lines[j]):
                if bullet_re.match(deint_lines[j]):
                    has_bullets = True
                j += 1
            if has_bullets:
                final_lines.extend(deint_lines[start:j])
            i = j
            continue
        else:
            final_lines.append(line)
            i += 1

    # Normalize blank lines
    normalized: list[str] = []
    blank_run = 0
    for l in final_lines:
        if l.strip() == "":
            blank_run += 1
            if blank_run <= 1:
                normalized.append("")
        else:
            blank_run = 0
            normalized.append(l)

    md_path.write_text("\n".join(normalized) + "\n", encoding="utf-8")
    kept = sum(1 for l in normalized if bullet_re.match(l))
    return removed_existing + removed_internal, kept


def main():
    ap = argparse.ArgumentParser(description="Remove proposal bullets that duplicate existing franchise canonicals.")
    ap.add_argument("--franchises", default=str(Path("vocab") / "franchises"), help="Path to franchises directory")
    ap.add_argument("--proposals", default=str(Path("docs") / "franchise_character_proposals.md"), help="Path to proposals markdown")
    args = ap.parse_args()

    franchises_dir = Path(args.franchises)
    md_path = Path(args.proposals)

    existing = load_existing_canonicals(franchises_dir)
    removed, kept = dedup_proposals(md_path, existing)
    print(f"Removed {removed} duplicate proposal(s); {kept} proposal(s) remain.")


if __name__ == "__main__":
    main()

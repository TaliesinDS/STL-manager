# STL-manager
a database and app to manage a collection of 3d print files.

STL Manager
Personal project to inventory and eventually manage a very large 3D model library (STL, OBJ, slicer project files, previews, archives) safely and incrementally.

Status: Phase 0 — planning & passive inventory only.

Goals (current phase)

Map existing extracted files (no archive extraction yet).
Produce a simple inventory (path, size, extension, depth, archive flag).
Make deliberate, reversible changes only after visibility.
Out of Scope (for now)

Bulk archive extraction
Geometry analysis (triangles, volume)
Deduplication / renaming
Web UI
Automatic tag inference
Next Micro Goal Implement a read-only scan script that outputs CSV and JSON inventories of existing extracted files.

## Quick Exploratory Token Scan (Planning Aid)

Added `scripts/quick_scan.py` to surface high-frequency filename tokens and highlight potential new metadata dimensions you might have overlooked (designers, factions, scale denominators, lineage families, variant cues).

PowerShell example:

```
python scripts/quick_scan.py --root D:\Models --limit 60000 --extensions .stl .obj .chitubox .lys --json-out quick_scan_report.json
```

With dynamic vocab from tokenmap (recommended after updates to `tokenmap.md`):

```
python scripts/quick_scan.py --root D:\Models --tokenmap tokenmap.md --json-out quick_scan_report.json
```

Double‑click option:
- Copy `quick_scan.py` and `run_quick_scan.bat` into any folder (or subfolder) you want to scan.
- Double click `run_quick_scan.bat` -> it treats that folder as root and writes `quick_scan_report.json` there.
- Omit `--root` / `--json-out` manually: script defaults root to its own directory and output file to `quick_scan_report.json`.

What it does (Phase 0 safe):
- Recurses files (no archive extraction) honoring extension filter.
- Splits stems (and now directory names) on `_ - space` unless `--skip-dirs` provided.
- Optionally loads designers / lineage / faction aliases / stopwords from `tokenmap.md` via `--tokenmap` (falls back to embedded defaults if parsing fails).
- Supports ignore list & domain summary via `--ignore-file` (newline tokens, `#` comments) and `--emit-known-summary` to print counts of classified domains and suppress noisy frequent known/ambiguous tokens from the unknown list.
	- If `--ignore-file` is omitted the script auto-loads `ignored_tokens.txt` from the scripts directory when present.
- Optional `--include-archives` adds archive filenames (.zip .rar .7z .cbz .cbr) to token stream (still no extraction) and reports `scanned_archives` in JSON.
- Counts token frequencies and classifies against a minimal embedded vocab subset (sync with `tokenmap.md`).
- Prints top unknown tokens (candidates for expansion into designer aliases, factions, lineage, style, etc.).
- Highlights scale ratio / mm tokens and numeric-containing tokens (pose, version, base size hints).
- Suggests review actions.

What it does NOT do:
- No writes / renames / DB mutations.
- No geometry parsing.
-- JSON optional (use --json-out). Without it: stdout only. Redirect if desired:

```
python scripts/quick_scan.py --root D:\Models > quick_scan_report.txt
```

Future Enhancements (optional):
- Emit JSON with structured sections.
- Merge token frequencies across multiple roots with a root_id tag.
- Integrate token_map_version diffing (mark which unknown tokens newly cross frequency thresholds).
- Add style token detection once style vocab stabilizes.
 - Optional: separate directory vs file token frequency breakdown.

License: (decide later)

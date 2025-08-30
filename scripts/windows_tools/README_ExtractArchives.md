# Extract-Archives.ps1

Bulk-safe, resumable archive extraction for a very large 3D model collection (STL / OBJ etc.).

## Current Feature Set
* Formats: `.rar`, `.zip`, `.7z` (extend with `-Extensions`)
* Discovery: Recursive scan from `-Root` preserving relative directory structure under optional `-OutputRoot`
* Dry planning: `-DryRun` (no filesystem writes) or `-ListOnly` (inventory only)
* Idempotence & Skips: destination existence, marker file (`.extracted`), non-empty dir checks
* Overwrite mode: fully deletes existing destination before re-extraction (`-Overwrite`)
* Marker creation: `-MarkExtracted` + fast skip via `-SkipIfMarker`
* Junk removal: `-RemoveJunk` (macOS and Windows metadata + AppleDouble) before flatten
* Flatten wrapper: `-FlattenSingleRoot` collapses redundant single top-level folder (multi-level)
* Parallel extraction: `-MaxParallel N` (bounded queue) with live progress + interactive controls
* Extraction limit: `-MaxExtract N` restricts number of successful extractions this run
* Logging: in-memory -> CSV (`-LogCsv` auto-generated if not provided)
* Long path handling: adds `\\?\` prefix when needed (Win long path support recommended)
* Interactive menu: launch with no args or `-Interactive` to pick modes, set limits & toggles
* Progress / control keys (parallel mode): pause, resume, stop feeding queue, abort, status snapshot

## Parameters (User-Facing)
| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `-Root` | string | current dir | Scan start point (recursive) |
| `-OutputRoot` | string | `-Root` | Destination root (relative structure preserved) |
| `-Extensions` | string[] | .rar,.zip,.7z | Archive extensions (with dot) |
| `-SevenZipPath` | string | auto-detect | Override path to `7z.exe` |
| `-DryRun` | switch | off | Plan only (create / extract steps reported) |
| `-ListOnly` | switch | off | List candidates (implies scan only) |
| `-Overwrite` | switch | off | Force re-extract; deletes existing destination folder |
| `-MarkExtracted` | switch | off | Create `.extracted` marker on success |
| `-SkipIfMarker` | switch | off | Skip if marker file already present |
| `-SkipIfNonEmpty` | switch | off | Skip if destination exists & has non-marker content |
| `-FlattenSingleRoot` | switch | off | Flatten single wrapper directory (multi-pass) |
| `-RemoveJunk` | switch | off | Delete metadata junk after extraction (or list in DryRun) |
| `-MaxExtract` | int | 0 (no limit) | Cap number of successful extractions this invocation |
| `-MaxParallel` | int | 1 | Parallel process count (queue + progress controls) |
| `-LogCsv` | string | auto timestamp | CSV log output path |
| `-PauseAfter` | switch | off | Wait for ENTER before exit (non-interactive) |
| `-Interactive` | switch | auto if none | Enter menu UI |

## Skip Logic Precedence
1. Destination exists & not `-Overwrite` => `dest_exists`
2. (If `-SkipIfNonEmpty`) Destination non-empty => `dest_non_empty`
3. (Else if `-SkipIfMarker`) Marker present => `marker_present`

Only one reason is recorded per skipped archive.

## Marker File (`.extracted`)
Presence-only sentinel to differentiate a completed, known-good extraction. Safe to delete (script may then re-extract depending on other flags).

## Junk Removal (`-RemoveJunk`)
Patterns removed (case-insensitive where applicable): `__MACOSX`, `.DS_Store`, `Thumbs.db`, `desktop.ini`, `.Spotlight-V100`, `.Trashes`, and `._*` AppleDouble sidecars. Executed before flatten to avoid blocking wrapper collapse.

## Flattening (`-FlattenSingleRoot`)
After extraction & junk removal, repeatedly collapses a single non-junk top-level directory (up to 5 levels) to eliminate redundant wrappers. Collision-safe: existing file/dir names are not overwritten; conflicts are logged.

## Parallel Mode (`-MaxParallel > 1`)
Implements a bounded process pool using separate 7-Zip processes. Each task: spawn -> wait -> post-process (junk removal, flatten, marker). Logs success/errors per archive.

### Parallel Controls (real-time, while window focused)
| Key | Action |
|-----|--------|
| `P` | Pause / resume feeding new archives to the queue |
| `S` | Stop queuing new archives (finish current in-flight set) |
| `Q` | Abort: kill in-flight processes and stop immediately |
| `Space` | Print a status snapshot instantly |

Status lines also auto-print after each completion and every ~10 seconds.

## Interactive Menu
Auto-shown when script launched with zero parameters. Options cover: Dry Run, Extract (with markers & skip), Overwrite, List, toggle Flatten/Junk, configure paths, set `MaxExtract`, set `MaxParallel`, Quit.

## Typical Workflows
### First Pass (safe preview then extraction)
```powershell
./Extract-Archives.ps1 -Root D:\Models -DryRun
./Extract-Archives.ps1 -Root D:\Models -MarkExtracted -SkipIfMarker -RemoveJunk -FlattenSingleRoot -MaxParallel 3
```
### Incremental Daily Batch (limit count)
```powershell
./Extract-Archives.ps1 -Root D:\Models -SkipIfMarker -MarkExtracted -MaxExtract 25 -MaxParallel 3
```
### Rebuild Specific Subtree
```powershell
./Extract-Archives.ps1 -Root D:\Models\NewDrop -Overwrite -MarkExtracted -FlattenSingleRoot
```
### Inventory Only
```powershell
./Extract-Archives.ps1 -Root D:\Models -ListOnly -Extensions .zip,.rar
```

## CSV Log Schema
Columns: `Archive, Action, Reason, Dest, Status, Error`
* Action: `Extract`, `Skip`, `List`
* Status: `Success`, `Skipped`, `Error`, `Planned`
* Reason: skip or planning rationale (`dest_exists`, `dest_non_empty`, `marker_present`, `DryRun`, `ListOnly`)

## Exit Codes
* `0` – No extraction errors (skips allowed)
* `1` – One or more extraction errors

## Performance Tips
* Start with `-MaxParallel 2` or `3`; CPU & disk IO patterns of 7-Zip may saturate beyond that for large compressed archives
* Use `-RemoveJunk` + `-FlattenSingleRoot` to reduce deep nesting cost before later indexing
* Avoid huge `-MaxParallel` on HDDs: seek thrash > throughput
* Enable Windows long path support (Group Policy / registry) for deep designer/collection paths

## Safety & Recovery
* `-Overwrite` deletes destination dir first – ensure backups for important curated paths
* Aborting with `Q` in parallel mode leaves partially extracted destinations (marker not created); rerunning with skip flags off will cleanly retry
* Combine `-SkipIfMarker` with `-MarkExtracted` for fast resumability after interruptions

## Troubleshooting
| Symptom | Likely Cause | Mitigation |
|---------|-------------|------------|
| "Unable to locate 7z.exe" | 7-Zip not installed or not in expected path | Install 7-Zip or pass `-SevenZipPath` |
| Stalls with many large archives | Too high `-MaxParallel` on slow disk | Lower to 2–3 |
| Wrapper folders remain | Flatten flag off or collisions preventing moves | Use `-FlattenSingleRoot`; inspect warnings |
| Marker skipped but incomplete contents | Prior manual deletion interrupted | Delete marker & rerun |
| Long path errors | OS long path support disabled | Enable Win32 long paths policy |

## Future (Not Yet Implemented)
* Nested archive expansion (.zip inside extracted tree)
* Content heuristics for smarter flatten decisions without full extraction
* Hash-based de-duplication index / similarity grouping
* Integrated checksum validation

## 7-Zip Dependency
Install from https://www.7-zip.org/ (GUI installer). Standard detection paths:
```
C:\Program Files\7-Zip\7z.exe
C:\Program Files (x86)\7-Zip\7z.exe
```
Or add to PATH / supply `-SevenZipPath`.

## Minimal Quick Reference
```powershell
# Interactive menu
./Extract-Archives.ps1

# Parallel batch (3 at a time), flatten & junk cleanup
./Extract-Archives.ps1 -Root D:\Models -MarkExtracted -SkipIfMarker -RemoveJunk -FlattenSingleRoot -MaxParallel 3

# Limited batch of 10
./Extract-Archives.ps1 -Root D:\Models -MarkExtracted -SkipIfMarker -MaxExtract 10
```

---
Comprehensive user guide for `Extract-Archives.ps1`.

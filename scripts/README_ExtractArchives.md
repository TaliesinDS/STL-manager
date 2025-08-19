# Extract-Archives.ps1

Bulk-safe archive extraction for a massive STL collection.

## Features
- Supports .rar, .zip, .7z (extend via -Extensions)
- Dry-run planning, list-only mode
- Idempotent (skips existing) or force overwrite
- Marker-based skip logic (.extracted)
- Long path resilience (adds \\?\ prefix automatically for long paths)
- CSV logging of every decision (Skip / Extract / Error)
- Separate output root preserving relative source layout

## Basic Usage
```powershell
# Preview actions only
./Extract-Archives.ps1 -Root D:\Models -DryRun

# Actually extract into same tree, create markers
./Extract-Archives.ps1 -Root D:\Models -MarkExtracted

# Extract only rar + zip, to another drive, with logging path specified
./Extract-Archives.ps1 -Root D:\Models -OutputRoot E:\Extracted -Extensions .rar,.zip -MarkExtracted -LogCsv E:\logs\extract.csv

# Re-extract everything (danger: deletes existing destination folders) 
./Extract-Archives.ps1 -Root D:\Models -Overwrite

# Just list candidates (no extraction)
./Extract-Archives.ps1 -Root D:\Models -ListOnly
```

## Recommended Initial Workflow
1. Dry run: `-DryRun` to confirm counts.
2. List only if you just want inventory: `-ListOnly`.
3. First real pass: add `-MarkExtracted` so future runs skip quickly with `-SkipIfMarker`.
4. Later tighten skipping: add `-SkipIfMarker -SkipIfNonEmpty`.

## Handling Long Paths
Ensure Windows 10+ long path support is enabled via Group Policy or registry: Enable Win32 long paths.

## Exit Codes
- 0: All extractions succeeded (errors may still be 0). 
- 1: One or more errors extracting archives.

## CSV Log Columns
Archive, Action, Reason, Dest, Status, Error

## Extending
Future ideas (not implemented yet):
- Nested archive expansion
- Internal structure heuristics (e.g., flatten single top folder)
- Parallel extraction (PowerShell 7)
- Hash-based de-duplication index

## 7-Zip Requirement
Install 7-Zip (https://www.7-zip.org/) so `7z.exe` is discoverable or pass `-SevenZipPath`.

---
Generated helper documentation for `Extract-Archives.ps1`.

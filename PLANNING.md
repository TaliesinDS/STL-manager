Planning Log
Dataset Snapshot (2025-08-15)
Unprocessed archives: ~5k (RAR/ZIP), ~2 TB
Extracted & partially ordered: ~96k files, ~2.6 TB
Formats: STL, OBJ, other meshes, presupported slicer project files, preview images, marketing extras
Deep nesting (some >260 char paths), nested archives
Stored on dedicated HDD
Guiding Principles
Inventory before mutation.
Sample before bulk extraction.
Keep raw model binaries outside Git (for now).
Small, verifiable steps.
Ask before increasing complexity.
Upcoming Steps
Step 1: Baseline repository files (this commit).
Step 2: Define inventory script specification.
Step 3: Implement scan (no hashes).
Step 4: Add hashing (SHA256).
Step 5: Add basic extension classification and mesh flag.
Open Questions

Exact directory roots naming.
Whether to store relative or absolute paths in inventory.
CSV vs JSON primary artifact.
DECISIONS.md

Decisions
2025-08-15: Created separate repo (STL-manager) to isolate code/planning from blog and avoid large binary history. 2025-08-15: Phase 0 limited to read-only inventory of already extracted files; archives untouched. (Add each new decision with date + rationale.)

.gitignore pycache/ .pyc .env .env. .vscode/ .idea/ .venv/ build/ dist/ notes/

Optional future patterns (uncomment if you choose to exclude)
*.stl
*.obj
*.zip
*.rar
scripts/ Add an empty scripts folder (you can drop a .gitkeep file inside if needed).
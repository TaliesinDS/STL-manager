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

License: (decide later)

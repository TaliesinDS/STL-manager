# Horus Heresy (30K) Codex YAML — Next Steps

This file persists our immediate plan so we can resume work even after session resets.

## Current status
- File: `vocab/codex_units_horus_heresy.yaml`
- Integrity tests: green (`tests/test_codex_basing_integrity.py`)
- Latest change: added alias hygiene for Astartes drop pods (Anvillus for Dreadclaw; Kharybdis spelling for Charybdis).

## Next actions
- Mechanicum: quick gap pass on infantry/support and transports — add any clear omissions.
- Talons of the Emperor: re-check flyers (Orion present); confirm if Ares variant belongs (add only if clearly HH-legal).
- Solar Auxilia/Militia: mop up lesser support/transport stragglers if still missing.
- Alias hygiene: continue adding high-signal synonyms; avoid duplicate unit entries.

## Test command (PowerShell)
```pwsh
c:/Users/akortekaas/Documents/GitHub/STL-manager/.venv/Scripts/python.exe -m pytest -q tests/test_codex_basing_integrity.py
```

## Notes
- Keep legality conservative until a Liber-based audit.
- Maintain `base_profile` only under units or `availability_groups.default_base_profile`.
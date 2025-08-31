# Assistant Chat Mode Guardrails (Windows + PowerShell)

This project runs on Windows with PowerShell as the default shell. The following rules are mandatory for any command the assistant provides or executes.

Rules
- Shell: All shell commands MUST target PowerShell. Never paste shell lines inside the Python REPL.
- Code fences: Use ```powershell fences for shell; use ```python for actual Python source files only.
- Interpreter: Use the venv interpreter explicitly: ` .\.venv\Scripts\python.exe ` (not `python`).
- Env var inline: Set `STLMGR_DB_URL` on the same command line via `$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";`.
- Working directory: Assume repo root. If uncertain, include `Set-Location` to the repo root first.
- Reports: Prefer `--out reports/<context>_<timestamp>.json` for long operations; keep artifacted logs in `reports/`.
- ID ranges: Build lists with PowerShell range join, e.g. `$ids = (5..64) -join ','`.
- Tasks first: If a matching VS Code task exists, prefer running it instead of raw commands.

Never do
- Don’t paste PowerShell lines into the Python REPL.
- Don’t use bash heredocs or Linux-y syntax on Windows.
- Don’t assume `python` on PATH; always use ` .\.venv\Scripts\python.exe `.

Command templates
- Normalize (dry-run, with summary):
  ```powershell
  $env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";
  .\.venv\Scripts\python.exe .\scripts\30_normalize_match\normalize_inventory.py `
    --batch 200 `
    --print-summary `
    --include-fields designer,designer_confidence,residual_tokens,franchise_hints,franchise,intended_use_bucket,lineage_family `
    --out ("reports/normalize_designers_dryrun_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
  ```

- Normalize specific IDs (apply):
  ```powershell
  $env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";
  $ids = (5..64) -join ',';
  .\.venv\Scripts\python.exe .\scripts\30_normalize_match\normalize_inventory.py `
    --batch 200 `
    --ids $ids `
    --apply `
    --print-summary `
    --include-fields designer,designer_confidence `
    --out ("reports/normalize_designers_apply_ids_" + $ids.Replace(',', '_') + ".json")
  ```

- Reload designers token map:
  ```powershell
  $env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";
  .\.venv\Scripts\python.exe .\scripts\20_loaders\load_designers.py .\vocab\designers_tokenmap.json --commit
  ```

- Run all tests (venv):
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q
  ```

Self-checks before running commands
- Verify ` .\.venv\Scripts\python.exe ` exists; if not, instruct to create/activate the venv.
- When a command uses `--out`, ensure `reports/` exists or rely on the script to create it.
- Prefer explicit paths relative to repo root; avoid `cd` into subfolders unless necessary.

By following these guardrails, the assistant will not mix PowerShell commands into Python REPL sessions and will produce consistently runnable commands for this repository.

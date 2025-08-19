<#
.SYNOPSIS
  Bulk extract .rar/.zip/.7z archives in a large 3D model collection safely & resumably.

.DESCRIPTION
  Iterates a root directory, finds archives (default: .rar, .zip, .7z) and extracts each
  into a sibling folder named after the archive (ArchiveName/). Extraction preserves
  the relative path from the root into the output root (can be same as root or elsewhere).

  Features:
    - Dry-run mode (no writes) to preview planned actions
    - Idempotent: skips archives whose extraction folder already exists (unless -Overwrite)
    - Optional marker file (.extracted) for faster subsequent scans / provenance
    - CSV log of actions & errors
    - Long-path support via \\?\ prefix (Win10+ long paths enabled recommended)
    - Safe detection of 7z.exe (auto, custom path param, or PATH lookup)
    - Optional listing only (-ListOnly)
    - Skips re-extraction of partial prior runs unless explicitly overridden

  NOT (yet) implemented (future / smart mode ideas):
    - Internal structure inspection before choosing extraction strategy
    - Nested archive in-place expansion
    - Multi-threaded extraction (PowerShell 7 ForEach-Object -Parallel)

.PARAMETER Root
  The root directory to scan for archives.

.PARAMETER OutputRoot
  Destination root for extracted folders (defaults to Root). Relative structure below Root is preserved.

.PARAMETER Extensions
  Archive extensions (case-insensitive) to include. Provide with leading dots.

.PARAMETER SevenZipPath
  Explicit path to 7z.exe if auto-detection fails or multiple versions exist.

.PARAMETER DryRun
  Perform discovery & logging only; no extraction.

.PARAMETER Overwrite
  Re-extract even if destination folder exists (deletes existing dest first).

.PARAMETER ListOnly
  Just list candidate archives (implies DryRun for extraction portion).

.PARAMETER MarkExtracted
  Create a .extracted marker file inside each destination folder on success.

.PARAMETER LogCsv
  Path to CSV log file (default: Extract-Archives_log_<timestamp>.csv under current directory).

.PARAMETER SkipIfMarker
  Skip archives whose target dir already contains a .extracted marker.

.PARAMETER SkipIfNonEmpty
  Skip if destination folder exists and is non-empty (default skip is existence check already).

.PARAMETER FlattenSingleRoot
  After extraction, if the archive contains exactly one top-level directory and no root-level files,
  move that directory's contents up one level (so you don't get nested redundant folders).

.PARAMETER RemoveJunk
  Remove common junk / metadata after extraction (or list in DryRun): __MACOSX, .DS_Store, Thumbs.db,
  desktop.ini, .Spotlight-V100, .Trashes and AppleDouble (._*) files.

.EXAMPLE
  PS> ./Extract-Archives.ps1 -Root D:\Models -DryRun
  Preview what would be extracted.

.EXAMPLE
  PS> ./Extract-Archives.ps1 -Root D:\Models -OutputRoot E:\Extracted -MarkExtracted -LogCsv E:\logs\extract.csv
  Extract all supported archives to a separate drive preserving relative layout.

.EXAMPLE
  PS> ./Extract-Archives.ps1 -Root D:\Models -Extensions .rar,.zip -Overwrite
  Force re-extract only .rar and .zip (not .7z) archives.

.NOTES
  Requires 7-Zip CLI (7z.exe). Install 7-Zip and ensure 7z.exe is in one of:
    C:\Program Files\7-Zip\7z.exe
    C:\Program Files (x86)\7-Zip\7z.exe
  Or provide -SevenZipPath.

#>
[CmdletBinding()] param(
  [Parameter(Position=0)] [string]$Root,
  [Parameter(Position=1)] [string]$OutputRoot,
    [string[]]$Extensions = @('.rar', '.zip', '.7z'),
    [string]$SevenZipPath,
    [switch]$DryRun,
    [switch]$Overwrite,
    [switch]$ListOnly,
    [switch]$MarkExtracted,
    [switch]$SkipIfMarker,
    [switch]$SkipIfNonEmpty,
  [switch]$FlattenSingleRoot,
  [switch]$RemoveJunk,
  [int]$MaxExtract,
  [int]$MaxParallel,
  [string]$LogCsv,
  [switch]$PauseAfter,
  [switch]$Interactive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info { param([string]$Msg) Write-Host "[INFO ] $Msg" -ForegroundColor Cyan }
function Write-Warn { param([string]$Msg) Write-Warning $Msg }
function Write-Err  { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }

function Resolve-SevenZipPath {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path $Explicit) { return (Resolve-Path $Explicit).Path }
        throw "Provided 7z.exe path not found: $Explicit"
    }
    $candidates = @(
        "$env:ProgramFiles\7-Zip\7z.exe",
        "$env:ProgramFiles(x86)\7-Zip\7z.exe"
    ) + (Get-Command 7z.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    foreach ($c in $candidates | Where-Object { $_ } | Select-Object -Unique) {
        if (Test-Path $c) { return (Resolve-Path $c).Path }
    }
    throw "Unable to locate 7z.exe. Install 7-Zip or specify -SevenZipPath."
}

function Add-LongPathPrefix { param([string]$Path)
    if ($PSVersionTable.PSVersion.Major -lt 5) { return $Path }
    if ($Path -match '^\\\\\?\\') { return $Path }
    if ($Path.Length -ge 240) { return "\\\\?\\$Path" }
    return $Path
}

function Get-RelativePath { param($Full, $Root)
    $rootNorm = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $fullNorm = [IO.Path]::GetFullPath($Full)
    if ($fullNorm.StartsWith($rootNorm, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $fullNorm.Substring($rootNorm.Length).TrimStart([IO.Path]::DirectorySeparatorChar)
    }
    return $fullNorm
}

function Remove-SafeDirectory { param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Write-Info "Removing existing directory: $Path"
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
}

function Get-ArchiveRootStructure {
  param([string]$SevenZipExe, [string]$ArchivePath)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $SevenZipExe
  # -slt for technical listing (key = value lines), suppress headers with -ba not valid with -slt; rely on Path = lines
  $psi.Arguments = "l -slt `"$ArchivePath`""
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $proc = [System.Diagnostics.Process]::Start($psi)
  $out = $proc.StandardOutput.ReadToEnd()
  $err = $proc.StandardError.ReadToEnd()
  $proc.WaitForExit()
  if ($proc.ExitCode -ne 0) { throw "7z listing failed (exit $($proc.ExitCode)): $err" }
  $paths = @()
  foreach ($line in $out -split "`r?`n") {
    if ($line.StartsWith('Path = ')) {
      $p = $line.Substring(7).Trim()
      if ($p -and -not ($p -eq '.' )) { $paths += $p }
    }
  }
  $rootFiles = $false
  $topDirs = @{}
  foreach ($p in $paths) {
    if ($p -notmatch '[\\/]') { $rootFiles = $true; continue }
    $first = ($p -split '[\\/]')[0]
    if ($first) { $topDirs[$first] = $true }
  }
  return [pscustomobject]@{ HasRootFiles = $rootFiles; TopLevelDirs = $topDirs.Keys }
}

function Invoke-FlattenSingleRoot {
  param([string]$DestinationPath, [string[]]$IgnoreDirs = @('__MACOSX'))
  $changed = $false
  $safetyLimit = 5
  for ($i=0; $i -lt $safetyLimit; $i++) {
    if (-not (Test-Path -LiteralPath $DestinationPath)) { break }
    $children = @(Get-ChildItem -LiteralPath $DestinationPath -Force | Where-Object { $_.Name -notin @('.extracted') })
    if (-not $children -or $children.Count -eq 0) { break }
    $dirs = @($children | Where-Object { $_.PSIsContainer -and ($IgnoreDirs -notcontains $_.Name) })
    $files = @($children | Where-Object { -not $_.PSIsContainer })
    # If after ignoring junk dirs there are still regular files stop.
    if ($files.Count -gt 0) { break }
    # Allow flatten only if exactly one non-ignored directory (others may be ignorable junk which we delete first)
    $junkDirs = @($children | Where-Object { $_.PSIsContainer -and ($IgnoreDirs -contains $_.Name) })
    foreach ($jd in $junkDirs) { try { Remove-Item -LiteralPath $jd.FullName -Recurse -Force -ErrorAction Stop } catch { Write-Warn "Failed to remove junk dir during flatten '$($jd.FullName)': $($_.Exception.Message)" } }
    $dirs = @(Get-ChildItem -LiteralPath $DestinationPath -Force | Where-Object { $_.PSIsContainer -and $_.Name -notin @('.extracted') -and ($IgnoreDirs -notcontains $_.Name) })
    if ($dirs.Count -ne 1) { break }
    $innerDir = $dirs[0]
    Write-Info "Flattening wrapper directory '$($innerDir.Name)' -> '$DestinationPath'"
    foreach ($item in Get-ChildItem -LiteralPath $innerDir.FullName -Force) {
      $target = Join-Path $DestinationPath $item.Name
      if (Test-Path -LiteralPath $target) {
        Write-Warn "Skipping move of '$($item.Name)' (target exists)."
        continue
      }
      try { Move-Item -LiteralPath $item.FullName -Destination $target -Force -ErrorAction Stop } catch { Write-Warn "Move failed for '$($item.FullName)': $($_.Exception.Message)" }
    }
    try { Remove-Item -LiteralPath $innerDir.FullName -Recurse -Force -ErrorAction Stop } catch { Write-Warn "Failed removing emptied wrapper: $($_.Exception.Message)" }
    $changed = $true
  }
  return $changed
}

function Get-JunkItemsInPath {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return @() }
  $patterns = @('__MACOSX', '.DS_Store', 'Thumbs.db', 'desktop.ini', '.Spotlight-V100', '.Trashes')
  $results = New-Object System.Collections.Generic.List[Object]
  foreach ($p in $patterns) {
    $found = Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ieq $p }
    if ($found) { $results.AddRange($found) }
  }
  $appleDouble = Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '._*' }
  if ($appleDouble) { $results.AddRange($appleDouble) }
  return $results | Select-Object -Unique
}

function Remove-JunkItems {
  param([string]$Path, [switch]$WhatIfOnly)
  $junk = Get-JunkItemsInPath -Path $Path
  if (-not $junk -or $junk.Count -eq 0) { return 0 }
  $removed = 0
  foreach ($j in $junk) {
    if ($WhatIfOnly) {
      Write-Info "[DryRun] Would remove junk: $($j.FullName)"
    } else {
      try {
        if ($j.PSIsContainer) { Remove-Item -LiteralPath $j.FullName -Recurse -Force -ErrorAction Stop }
        else { Remove-Item -LiteralPath $j.FullName -Force -ErrorAction Stop }
        Write-Info "Removed junk: $($j.FullName)"
      } catch { Write-Warn "Failed to remove junk '$($j.FullName)': $($_.Exception.Message)" }
    }
    $removed++
  }
  return $removed
}

# ----------------------- Status Helpers -----------------------
function Show-ParallelStatus {
  param(
    [int]$Extracted,[int]$Errors,[int]$Skipped,[int]$InFlight,[int]$Pending,[int]$Total
  )
  $done = $Extracted + $Errors
  if ($Total -gt 0) { $pct = [Math]::Round((($done)/$Total)*100,1) } else { $pct = 0 }
  Write-Host ("[STATUS] Completed: {0}/{1} ({2}%), Extracted: {3}, Errors: {4}, Skipped: {5}, InFlight: {6}, Pending: {7}" -f $done,$Total,$pct,$Extracted,$Errors,$Skipped,$InFlight,$Pending) -ForegroundColor DarkCyan
}

# ----------------------- Interactive Menu -----------------------
function Show-InteractiveMenu {
  Write-Host ""; Write-Host "==== Archive Extraction Menu ====" -ForegroundColor Yellow
  Write-Host " 1) Dry run (scan only)"
  Write-Host " 2) Extract (create marker + skip if marker)" 
  Write-Host " 3) Extract (overwrite existing destinations)"
  Write-Host " 4) List only (list candidates)"
  Write-Host " 5) Toggle FlattenSingleRoot (current: $FlattenSingleRoot)"
  Write-Host " 6) Toggle RemoveJunk (current: $RemoveJunk)"
  Write-Host " 7) Configure Root / Output paths" 
  Write-Host " 8) Set max extracts this run (current: $([string]::IsNullOrWhiteSpace($MaxExtract) -or $MaxExtract -le 0 ? 'All' : $MaxExtract))"
  Write-Host " 9) Set max parallel extractions (current: $([string]::IsNullOrWhiteSpace($MaxParallel) -or $MaxParallel -le 1 ? '1 (sequential)' : $MaxParallel))"
  Write-Host "10) Quit"
  Write-Host ""; return (Read-Host "Select option [1-10]")
}

function Invoke-InteractiveSelection {
  param()
  # Prompt only once if values not already supplied
  if (-not $Root -or -not (Test-Path -LiteralPath $Root)) {
    $entered = Read-Host "Enter Root folder to scan (blank = current directory)"
    if ($entered) { $Root = $entered } else { $Root = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $Root)) { Write-Warn "Path not found, using current directory"; $Root = (Get-Location).Path }
  }
  if (-not $OutputRoot) {
    $outEntered = Read-Host "Enter Output root (blank = same as Root)"
    if ($outEntered) { $OutputRoot = $outEntered } else { $OutputRoot = $Root }
  }

  $done = $false
  while (-not $done) {
  Write-Info "Parallel controls: P=pause/resume feed, S=stop after current in-flight, Q=abort now, Space=status snapshot"
    $choice = Show-InteractiveMenu
    switch ($choice) {
      '1' { $script:DryRun = $true; $script:Overwrite=$false; $script:ListOnly=$false; $script:MarkExtracted=$false; $script:SkipIfMarker=$false; $script:SkipIfNonEmpty=$false; $done = $true }
  $pauseFeeding = $false
  $stopAfterInflight = $false
  $abort = $false
  $lastStatus = Get-Date
      '2' { $script:DryRun = $false; $script:Overwrite=$false; $script:ListOnly=$false; $script:MarkExtracted=$true; $script:SkipIfMarker=$true; $done = $true }
    while ($inflight.Count -lt $MaxParallel -and $pending.Count -gt 0 -and -not $pauseFeeding -and -not $stopAfterInflight -and -not $abort) {
      '4' { $script:ListOnly = $true; $script:DryRun = $true; $done = $true }
  '5' { $script:FlattenSingleRoot = -not $script:FlattenSingleRoot }
  '6' { $script:RemoveJunk = -not $script:RemoveJunk }
  '7' {
        $r = Read-Host "Root folder (blank keep current: $Root)"; if ($r) { if (Test-Path -LiteralPath $r) { $script:Root = $r } else { Write-Warn "Path not found; keeping previous." } }
        if (-not $script:Root) { $script:Root = (Get-Location).Path }
        $newOut = Read-Host "Output root (blank keep current: $OutputRoot)"; if ($newOut) { $script:OutputRoot = $newOut }
      }
  '8' {
        $lim = Read-Host "Enter max number of archives to extract this run (blank or 0 = no limit)"
        if ($lim) {
          [int]$val = 0
          if ([int]::TryParse($lim, [ref]$val)) { $script:MaxExtract = $val } else { Write-Warn "Not a number; keeping previous." }
        }
      }
  '9' {
        $par = Read-Host "Enter max parallel extractions (1 = sequential)"
        if ($par) {
          [int]$pval = 1
          if ([int]::TryParse($par, [ref]$pval)) { if ($pval -lt 1) { $pval = 1 }; $script:MaxParallel = $pval } else { Write-Warn "Not a number; keeping previous." }
        }
      }
 '10' { Write-Host "Quitting."; exit 0 }
      Default { Write-Warn "Invalid selection." }
    }
  }
  # Pause after by default in menu mode so window doesn't close instantly
  # Removed automatic PauseAfter; loop logic at end handles staying open.
}

# If launched with right-click and no meaningful params, auto interactive
if (-not $PSBoundParameters.ContainsKey('Interactive') -and $PSBoundParameters.Count -eq 0) {
  $Interactive = $true
}

if ($Interactive) {
  Invoke-InteractiveSelection
}

# Normalize & validate roots (robust, avoids hidden chars & property accessor lint issue)
Write-Info "Script start: $(Get-Date -Format o)"

# If -Root not supplied (or empty), default to the current working directory
    # Handle key input for control (best-effort; ignore errors if console not available)
    try {
      while ([Console]::KeyAvailable) {
        $k = [Console]::ReadKey($true)
        switch ($k.Key) {
          'P' { $pauseFeeding = -not $pauseFeeding; Write-Info ("Feed " + ($pauseFeeding ? 'PAUSED' : 'RESUMED')) }
          'S' { $stopAfterInflight = $true; Write-Info 'Will stop queuing new archives after current in-flight.' }
          'Q' { Write-Warn 'Abort requested. Terminating in-flight processes.'; $abort = $true; foreach ($e in $inflight) { try { $e.Proc.Kill() } catch {} } ; $pending.Clear() }
          'Spacebar' { Show-ParallelStatus -Extracted $extracted -Errors $errors -Skipped $skipped -InFlight $inflight.Count -Pending $pending.Count -Total $totalPlanned }
        }
      }
    } catch { }
    if ($abort) { break }
    # periodic status every ~10s even if nothing finished
    if ((Get-Date) -gt $lastStatus.AddSeconds(10)) { Show-ParallelStatus -Extracted $extracted -Errors $errors -Skipped $skipped -InFlight $inflight.Count -Pending $pending.Count -Total $totalPlanned; $lastStatus = Get-Date }
if (-not $PSBoundParameters.ContainsKey('Root') -or [string]::IsNullOrWhiteSpace($Root)) {
  $Root = (Get-Location).Path
  Write-Info "No -Root specified; defaulting to current directory: $Root"
}

if (-not (Test-Path -LiteralPath $Root)) {
  Write-Err "Root path not found: $Root"
  if (-not $PSBoundParameters.ContainsKey('Root')) { Write-Err "(This was the auto-detected current directory; ensure you are launching from a valid folder.)" }
  exit 1
}

# Use Get-Item / FullName instead of Resolve-Path .Path to dodge linter quirk
$RootItem = Get-Item -LiteralPath $Root -ErrorAction Stop
$Root = [IO.Path]::GetFullPath($RootItem.FullName).TrimEnd([IO.Path]::DirectorySeparatorChar,'/')

if (-not $OutputRoot) { $OutputRoot = $Root }
if (Test-Path -LiteralPath $OutputRoot) {
  $OutputItem = Get-Item -LiteralPath $OutputRoot -ErrorAction SilentlyContinue
  if ($OutputItem) { $OutputRoot = [IO.Path]::GetFullPath($OutputItem.FullName).TrimEnd([IO.Path]::DirectorySeparatorChar,'/') }
}
elseif (-not $DryRun) {
  New-Item -ItemType Directory -Path $OutputRoot | Out-Null
} elseif ($DryRun) {
  Write-Info "[DryRun] Would create output root: $OutputRoot"
}

# Prepare logging
if (-not $LogCsv) {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $LogCsv = Join-Path -Path (Get-Location) -ChildPath "Extract-Archives_log_$timestamp.csv"
}
$log = New-Object System.Collections.Generic.List[Object]

# Detect 7z
try { $SevenZip = Resolve-SevenZipPath -Explicit $SevenZipPath; Write-Info "Using 7z.exe: $SevenZip" }
catch { Write-Err $_.Exception.Message; return }

# Normalize extensions
$extSet = $Extensions | ForEach-Object { $_.ToLowerInvariant() } | Select-Object -Unique

Write-Info "Scanning '$Root' for extensions: $($extSet -join ', ')"
$archives = @(Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction Stop | Where-Object { $extSet -contains $_.Extension.ToLowerInvariant() })

Write-Info "Found $($archives.Count) archive candidate(s)."
if ($ListOnly) { Write-Info "ListOnly: skipping extraction phase." }

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$processed = 0
$skipped = 0
$extracted = 0
$errors = 0
if ($MaxExtract -and $MaxExtract -lt 0) { Write-Warn "MaxExtract cannot be negative; ignoring."; $MaxExtract = 0 }
if ($MaxExtract -and $MaxExtract -gt 0) { Write-Info "Limiting to first $MaxExtract extraction(s) this run." }
if ($MaxParallel -and $MaxParallel -gt 1) { Write-Info "Parallel mode enabled (max $MaxParallel concurrent extractions)." }

if ($MaxParallel -and $MaxParallel -gt 1 -and -not $DryRun -and -not $ListOnly) {
  # Build planned task list first (respecting MaxExtract limit afterwards)
  $tasks = New-Object System.Collections.Generic.List[Object]
  foreach ($a in $archives) {
    $processed++
    # Early break if MaxExtract reached (only counts successful extractions, so cannot enforce yet) -> we defer to later.
    $relativeDir = Get-RelativePath -Full $a.DirectoryName -Root $Root
    if ($null -ne $relativeDir) { $relativeDir = $relativeDir.TrimStart([IO.Path]::DirectorySeparatorChar, '/') }
    $destParent = if ([string]::IsNullOrWhiteSpace($relativeDir)) { $OutputRoot } else { Join-Path $OutputRoot $relativeDir }
    $destDir = Join-Path $destParent $a.BaseName
    $markerPath = Join-Path $destDir '.extracted'
    $reason = $null
    $destExists = Test-Path -LiteralPath $destDir -PathType Container
    if ($destExists -and -not $Overwrite) { $reason = 'dest_exists' }
    elseif ($SkipIfNonEmpty) {
      if ($destExists -and -not $Overwrite) {
        $nonMarkerItems = Get-ChildItem -LiteralPath $destDir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.extracted' }
        if ($nonMarkerItems -and $nonMarkerItems.Count -gt 0) { $reason = 'dest_non_empty' }
      }
    }
    elseif ($SkipIfMarker) { if (Test-Path -LiteralPath $markerPath) { $reason = 'marker_present' } }
    if ($reason) {
      $skipped++
      $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Skip'; Reason=$reason; Dest=$destDir; Status='Skipped'; Error='' }) | Out-Null
      continue
    }
    if (-not (Test-Path -LiteralPath $destParent)) { New-Item -ItemType Directory -Path $destParent -Force | Out-Null }
    if ((Test-Path -LiteralPath $destDir) -and $Overwrite) { Remove-SafeDirectory -Path $destDir }
    if (-not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    $tasks.Add([pscustomobject]@{ Archive=$a; DestDir=$destDir; Marker=$markerPath }) | Out-Null
  }
  if ($MaxExtract -and $MaxExtract -gt 0 -and $tasks.Count -gt $MaxExtract) {
    $tasks = $tasks | Select-Object -First $MaxExtract
    Write-Info "Trimmed task list to $MaxExtract due to MaxExtract limit."
  }
  $totalPlanned = $tasks.Count
  Write-Info "Planned $totalPlanned extraction task(s) for parallel processing."
  $inflight = New-Object System.Collections.Generic.List[Object]
  $pending = [System.Collections.Generic.Queue[Object]]::new()
  foreach ($t in $tasks) { $pending.Enqueue($t) }
  while ($pending.Count -gt 0 -or $inflight.Count -gt 0) {
    while ($inflight.Count -lt $MaxParallel -and $pending.Count -gt 0) {
      $t = $pending.Dequeue()
      $a = $t.Archive
      $archivePath = Add-LongPathPrefix $a.FullName
      $destPath = Add-LongPathPrefix $t.DestDir
      $quotedDest = if ($destPath -match '\s') { '"' + $destPath + '"' } else { $destPath }
      $quotedArchive = if ($archivePath -match '\s') { '"' + $archivePath + '"' } else { $archivePath }
      $arguments = @('x','-y',"-o$quotedDest",$quotedArchive)
      $outFile = Join-Path $env:TEMP ("extract_out_" + [guid]::NewGuid().ToString() + ".log")
      $errFile = Join-Path $env:TEMP ("extract_err_" + [guid]::NewGuid().ToString() + ".log")
      $proc = Start-Process -FilePath $SevenZip -ArgumentList $arguments -RedirectStandardOutput $outFile -RedirectStandardError $errFile -PassThru -WindowStyle Hidden
      Write-Info "[PARALLEL] Started ($($extracted + $inflight.Count + 1)/$totalPlanned): $($a.Name) (PID $($proc.Id))"
      $inflight.Add([pscustomobject]@{ Proc=$proc; Task=$t; OutFile=$outFile; ErrFile=$errFile }) | Out-Null
    }
    # Check finished processes
    for ($i = $inflight.Count - 1; $i -ge 0; $i--) {
      $entry = $inflight[$i]
      if ($entry.Proc.HasExited) {
        $a = $entry.Task.Archive
        $destDir = $entry.Task.DestDir
        $markerPath = $entry.Task.Marker
        $stdErr = (Get-Content -LiteralPath $entry.ErrFile -ErrorAction SilentlyContinue) -join "`n"
        $exitCode = $entry.Proc.ExitCode
        if ($exitCode -eq 1) { Write-Warn "7z reported warnings extracting $($a.Name). Proceeding (exit 1)." }
        if ($exitCode -ne 0 -and $exitCode -ne 1) {
          $errors++
          Write-Err "Failed (exit $exitCode): $($a.FullName)"
          $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Error'; Error=$stdErr }) | Out-Null
        } else {
          if ($RemoveJunk) { try { [void](Remove-JunkItems -Path $destDir) } catch { Write-Warn "Junk removal failed: $($_.Exception.Message)" } }
          if ($FlattenSingleRoot) { try { $flattened = Invoke-FlattenSingleRoot -DestinationPath $destDir; if ($flattened) { Write-Info "Flatten complete ($($a.Name))." } } catch { Write-Warn "Flatten failed ($($a.Name)): $($_.Exception.Message)" } }
          if ($MarkExtracted) { New-Item -ItemType File -Path $markerPath -Force | Out-Null }
          $extracted++
          $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Success'; Error='' }) | Out-Null
        }
        # cleanup temp logs
        foreach ($f in @($entry.OutFile,$entry.ErrFile)) { if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue } }
        $inflight.RemoveAt($i)
        if ($MaxExtract -and $MaxExtract -gt 0 -and $extracted -ge $MaxExtract) {
          Write-Info "Reached MaxExtract limit ($MaxExtract); cancelling remaining queued extractions."; $pending.Clear(); break
        }
      }
    }
    if ($inflight.Count -gt 0 -and $pending.Count -gt 0) { Start-Sleep -Milliseconds 250 }
    elseif ($inflight.Count -gt 0) { Start-Sleep -Milliseconds 150 }
  }
}
else {
  foreach ($a in $archives) {
    $processed++
    if ($MaxExtract -and $MaxExtract -gt 0 -and $extracted -ge $MaxExtract) { Write-Info "Reached MaxExtract limit ($MaxExtract); stopping early."; break }
    $relativeDir = Get-RelativePath -Full $a.DirectoryName -Root $Root
    if ($null -ne $relativeDir) { $relativeDir = $relativeDir.TrimStart([IO.Path]::DirectorySeparatorChar, '/') }
    $destParent = if ([string]::IsNullOrWhiteSpace($relativeDir)) { $OutputRoot } else { Join-Path $OutputRoot $relativeDir }
    $destDir = Join-Path $destParent $a.BaseName
    $markerPath = Join-Path $destDir '.extracted'
    $reason = $null
    $destExists = Test-Path -LiteralPath $destDir -PathType Container
    if ($destExists -and -not $Overwrite) { $reason = 'dest_exists' }
    elseif ($SkipIfNonEmpty) {
      if ($destExists -and -not $Overwrite) {
        $nonMarkerItems = Get-ChildItem -LiteralPath $destDir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.extracted' }
        if ($nonMarkerItems -and $nonMarkerItems.Count -gt 0) { $reason = 'dest_non_empty' }
      }
    }
    elseif ($SkipIfMarker) { if (Test-Path -LiteralPath $markerPath) { $reason = 'marker_present' } }
    if ($reason) { $skipped++; $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Skip'; Reason=$reason; Dest=$destDir; Status='Skipped'; Error='' }) | Out-Null; continue }
    if ($ListOnly) { $skipped++; $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='List'; Reason='ListOnly'; Dest=$destDir; Status='Planned'; Error='' }) | Out-Null; continue }
    if (-not (Test-Path -LiteralPath $destParent)) { if ($DryRun) { Write-Info "[DryRun] Would create directory: $destParent" } else { New-Item -ItemType Directory -Path $destParent -Force | Out-Null } }
    if ((Test-Path -LiteralPath $destDir) -and $Overwrite) { if ($DryRun) { Write-Info "[DryRun] Would remove existing destination (overwrite): $destDir" } else { Remove-SafeDirectory -Path $destDir } }
    if (-not (Test-Path -LiteralPath $destDir)) { if ($DryRun) { Write-Info "[DryRun] Would create directory: $destDir" } else { New-Item -ItemType Directory -Path $destDir -Force | Out-Null } }
    $archivePath = Add-LongPathPrefix $a.FullName
    $destPath = Add-LongPathPrefix $destDir
    if ($DryRun) {
      Write-Info "[DryRun] Would extract ($processed/$($archives.Count)): $($a.Name) -> $destDir"
      if ($FlattenSingleRoot) { try { $structure = Get-ArchiveRootStructure -SevenZipExe $SevenZip -ArchivePath $a.FullName; if (-not $structure.HasRootFiles -and $structure.TopLevelDirs.Count -eq 1) { Write-Info "[DryRun] Would flatten single top-level folder: $($structure.TopLevelDirs[0])" } } catch { Write-Warn "[DryRun] Could not inspect for flatten: $($_.Exception.Message)" } }
      if ($RemoveJunk) { Write-Info "[DryRun] Would remove junk files/folders after extraction." }
      $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason='DryRun'; Dest=$destDir; Status='Planned'; Error='' }) | Out-Null
      continue
    }
    Write-Info "Extracting ($processed/$($archives.Count)): $($a.Name) -> $destDir"
    try {
      $quotedDest = if ($destPath -match '\s') { '"' + $destPath + '"' } else { $destPath }
      $quotedArchive = if ($archivePath -match '\s') { '"' + $archivePath + '"' } else { $archivePath }
      $arguments = @('x','-y',"-o$quotedDest",$quotedArchive)
      $psi = New-Object System.Diagnostics.ProcessStartInfo
      $psi.FileName = $SevenZip
      $psi.Arguments = ($arguments -join ' ')
      $psi.RedirectStandardError = $true
      $psi.RedirectStandardOutput = $true
      $psi.UseShellExecute = $false
      $p = [System.Diagnostics.Process]::Start($psi)
      $null = $p.StandardOutput.ReadToEnd()
      $stdErr = $p.StandardError.ReadToEnd()
      $p.WaitForExit()
      if ($p.ExitCode -eq 1) { Write-Warn "7z reported warnings extracting $($a.Name). Proceeding (exit 1)." }
      elseif ($p.ExitCode -ne 0) { throw "7z exit code $($p.ExitCode). $stdErr" }
      if ($MarkExtracted) { New-Item -ItemType File -Path $markerPath -Force | Out-Null }
      if ($RemoveJunk) { try { [void](Remove-JunkItems -Path $destDir) } catch { Write-Warn "Junk removal failed: $($_.Exception.Message)" } }
      if ($FlattenSingleRoot) { try { $flattened = Invoke-FlattenSingleRoot -DestinationPath $destDir; if ($flattened) { Write-Info "Flatten complete." } else { Write-Info "No flatten needed." } } catch { Write-Warn "Flatten failed: $($_.Exception.Message)" } }
      $extracted++
      $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Success'; Error='' }) | Out-Null
    }
    catch {
      $errors++
      Write-Err "Failed: $($a.FullName): $($_.Exception.Message)"
      $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Error'; Error=$_.Exception.Message }) | Out-Null
    }
  }
}

$sw.Stop()

Write-Info "Processed: $processed  Extracted: $extracted  Skipped: $skipped  Errors: $errors  Elapsed: $([Math]::Round($sw.Elapsed.TotalMinutes,2)) min"

try {
    $log | Export-Csv -Path $LogCsv -NoTypeInformation -Encoding UTF8
    Write-Info "Log written: $LogCsv"
} catch { Write-Warn "Failed to write log CSV: $($_.Exception.Message)" }

if ($errors -gt 0) { $exit=1 } else { $exit=0 }
Write-Info "Exit code: $exit"

if ($Interactive) {
  # Immediately loop back to menu preserving root/output and persistent toggles (not operation-specific flags).
  & $PSCommandPath -Interactive -Root $Root -OutputRoot $OutputRoot -Extensions $Extensions -FlattenSingleRoot:$FlattenSingleRoot -RemoveJunk:$RemoveJunk -MaxParallel:$MaxParallel -MaxExtract:$MaxExtract
  exit $LASTEXITCODE
} elseif ($PauseAfter) {
  Read-Host "Press ENTER to close" | Out-Null
}
exit $exit

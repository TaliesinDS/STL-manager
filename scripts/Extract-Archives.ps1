<#!
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
    [Parameter(Mandatory=$true, Position=0)] [ValidateNotNullOrEmpty()] [string]$Root,
    [Parameter(Position=1)] [string]$OutputRoot,
    [string[]]$Extensions = @('.rar', '.zip', '.7z'),
    [string]$SevenZipPath,
    [switch]$DryRun,
    [switch]$Overwrite,
    [switch]$ListOnly,
    [switch]$MarkExtracted,
    [switch]$SkipIfMarker,
    [switch]$SkipIfNonEmpty,
    [string]$LogCsv
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

function Safe-RemoveDirectory { param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Write-Info "Removing existing directory: $Path"
    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
}

# Normalize & validate roots
# (Two-step assign to avoid any hidden encoding issues with direct member access on same line)
$resolvedRoot = Resolve-Path -LiteralPath $Root
$Root = $resolvedRoot.Path
if (-not $OutputRoot) {
  $OutputRoot = $Root
}
# PowerShell 5.1 compatibility: avoid null-conditional (?.) and null-coalescing (??) operators
$resolvedOutputRoot = Resolve-Path -LiteralPath $OutputRoot -ErrorAction SilentlyContinue
if ($resolvedOutputRoot) {
  $OutputRoot = $resolvedOutputRoot.Path
}
if (-not (Test-Path $OutputRoot)) {
    if ($DryRun) { Write-Info "[DryRun] Would create output root: $OutputRoot" } else { New-Item -ItemType Directory -Path $OutputRoot | Out-Null }
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
$archives = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction Stop | Where-Object { $extSet -contains $_.Extension.ToLowerInvariant() }

Write-Info "Found $($archives.Count) archive candidate(s)."
if ($ListOnly) { Write-Info "ListOnly: skipping extraction phase." }

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$processed = 0
$skipped = 0
$extracted = 0
$errors = 0

foreach ($a in $archives) {
    $processed++
    $relativeDir = Split-Path (Get-RelativePath -Full $a.DirectoryName -Root $Root) -NoQualifier
  if ($relativeDir) {
    $destParent = Join-Path $OutputRoot $relativeDir
  } else {
    $destParent = $OutputRoot
  }
    $destDir = Join-Path $destParent $a.BaseName
    $markerPath = Join-Path $destDir '.extracted'

    $reason = $null
    if (Test-Path $destDir -PathType Container -and -not $Overwrite) { $reason = 'dest_exists' }
    elseif ($SkipIfNonEmpty -and (Test-Path $destDir) -and (Get-ChildItem -LiteralPath $destDir -Force | Where-Object { $_.Name -ne '.extracted' }).Count -gt 0 -and -not $Overwrite) { $reason = 'dest_non_empty' }
    elseif ($SkipIfMarker -and (Test-Path $markerPath)) { $reason = 'marker_present' }

    if ($reason) {
        $skipped++
        $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Skip'; Reason=$reason; Dest=$destDir; Status='Skipped'; Error='' }) | Out-Null
        continue
    }

    if ($ListOnly) {
        $skipped++
        $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='List'; Reason='ListOnly'; Dest=$destDir; Status='Planned'; Error='' }) | Out-Null
        continue
    }

    if (-not (Test-Path $destParent)) {
        if ($DryRun) { Write-Info "[DryRun] Would create directory: $destParent" } else { New-Item -ItemType Directory -Path $destParent | Out-Null }
    }
    if (Test-Path $destDir -and $Overwrite) {
        if ($DryRun) { Write-Info "[DryRun] Would remove existing destination (overwrite): $destDir" } else { Safe-RemoveDirectory -Path $destDir }
    }
    if (-not (Test-Path $destDir)) {
        if ($DryRun) { Write-Info "[DryRun] Would create directory: $destDir" } else { New-Item -ItemType Directory -Path $destDir | Out-Null }
    }

    $archivePath = Add-LongPathPrefix $a.FullName
    $destPath = Add-LongPathPrefix $destDir

    Write-Info "Extracting ($processed/$($archives.Count)): $($a.Name) -> $destDir"

    if ($DryRun) {
        $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason='DryRun'; Dest=$destDir; Status='Planned'; Error='' }) | Out-Null
        continue
    }

    try {
        $arguments = @('x', '-y', "-o$destPath", '--', $archivePath)
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $SevenZip
        $psi.Arguments = ($arguments -join ' ')
        $psi.RedirectStandardError = $true
        $psi.RedirectStandardOutput = $true
        $psi.UseShellExecute = $false
        $p = [System.Diagnostics.Process]::Start($psi)
        $stdOut = $p.StandardOutput.ReadToEnd()
        $stdErr = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        if ($p.ExitCode -ne 0) { throw "7z exit code $($p.ExitCode). $stdErr" }
        if ($MarkExtracted) { New-Item -ItemType File -Path $markerPath -Force | Out-Null }
        $extracted++
        $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Success'; Error='' }) | Out-Null
    }
    catch {
        $errors++
        Write-Err "Failed: $($a.FullName): $($_.Exception.Message)"
        $log.Add([pscustomobject]@{ Archive=$a.FullName; Action='Extract'; Reason=''; Dest=$destDir; Status='Error'; Error=$_.Exception.Message }) | Out-Null
    }
}

$sw.Stop()

Write-Info "Processed: $processed  Extracted: $extracted  Skipped: $skipped  Errors: $errors  Elapsed: $([Math]::Round($sw.Elapsed.TotalMinutes,2)) min"

try {
    $log | Export-Csv -Path $LogCsv -NoTypeInformation -Encoding UTF8
    Write-Info "Log written: $LogCsv"
} catch { Write-Warn "Failed to write log CSV: $($_.Exception.Message)" }

if ($errors -gt 0) { exit 1 } else { exit 0 }

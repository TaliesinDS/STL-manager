<#
.SYNOPSIS
Opens the STL Manager web UI in a dedicated browser "app" window (Chromium app mode)

.DESCRIPTION
This helper tries to find Microsoft Edge or Google Chrome and launches the given URL
in "app" mode (no tabs/address bar) using a separate profile directory so the window
is isolated from your normal browser session. If Edge/Chrome are not found it falls
back to opening the system default browser.

Usage examples:
  # Open default URL
  pwsh .\scripts\open_app_window.ps1

  # Specify a URL
  pwsh .\scripts\open_app_window.ps1 -Url 'http://127.0.0.1:8000'

This script does not start the backend server; run your normal start script first
and then call this script (or integrate it into your one-click batch file).
#>

param(
    [string]$Url = 'http://127.0.0.1:8000/',
    [string]$ProfileDir = "$env:LOCALAPPDATA\stl_manager_profile",
    [switch]$VerboseOutput
)

function Get-ExePath($candidates) {
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

$edgeCandidates = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe"
)

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
)

$exe = Get-ExePath ($edgeCandidates + $chromeCandidates)

if ($null -eq $exe) {
    if ($VerboseOutput) { Write-Output "Edge/Chrome not found on expected paths. Falling back to default browser." }
    Start-Process $Url
    return
}

# Ensure profile directory exists (isolates this app window from user tabs/extensions)
try {
    if (-not (Test-Path $ProfileDir)) {
        New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
        if ($VerboseOutput) { Write-Output "Created profile dir: $ProfileDir" }
    }
} catch {
    Write-Warning "Could not create profile dir '$ProfileDir': $_. Exception: $($_.Exception.Message)"
}

# Build Chromium-style args. --app opens a frameless window pointing at the URL.
$args = @(
    "--app=$Url",
    "--user-data-dir=$ProfileDir",
    "--new-window",
    "--no-first-run",
    "--disable-extensions"
)

if ($VerboseOutput) { Write-Output "Launching: $exe $($args -join ' ')" }

try {
    Start-Process -FilePath $exe -ArgumentList $args -WindowStyle Normal
    if ($VerboseOutput) { Write-Output "Launched $exe in app mode for URL $Url" }
} catch {
    Write-Warning "Failed to launch $exe in app mode: $($_.Exception.Message). Falling back to default browser."
    Start-Process $Url
}

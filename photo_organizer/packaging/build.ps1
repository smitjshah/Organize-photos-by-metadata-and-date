# Builds dist\PhotoOrganizer.exe from a clean state.
# Run from the repo root: powershell -File photo_organizer\packaging\build.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

Write-Host "Cleaning previous build artifacts..."
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "Building with PyInstaller (onefile)..."
& .\.venv\Scripts\pyinstaller.exe photo_organizer\packaging\photo_organizer.spec --noconfirm

$exePath = Join-Path $RepoRoot "dist\PhotoOrganizer.exe"
if (-not (Test-Path $exePath)) {
    throw "Build failed: $exePath was not produced."
}

$sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "Build succeeded: $exePath ($sizeMB MB)"
Write-Host "Manual step: double-click the exe once to confirm it launches."

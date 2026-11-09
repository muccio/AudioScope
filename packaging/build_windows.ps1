<#
.SYNOPSIS
    AudioScope Windows Standalone Executable & Installer Build Script
.DESCRIPTION
    Automates PyInstaller build with PyAV/FFmpeg DLL bundling, Per-Monitor V2 DPI manifest,
    and optional Inno Setup compiler generation.
#>

[CmdletBinding()]
param (
    [switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " AudioScope Windows Standalone Packaging Pipeline" -ForegroundColor Cyan
Write-Host " Project Root: $ProjectRoot" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Activate Virtual Environment if available
$VenvCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"),
    (Join-Path (Split-Path -Parent $ProjectRoot) ".venv\Scripts\Activate.ps1")
)
foreach ($VenvPath in $VenvCandidates) {
    if (Test-Path $VenvPath) {
        Write-Host "Activating virtual environment at $VenvPath..." -ForegroundColor Yellow
        & $VenvPath
        break
    }
}

# 2. Verify pyinstaller
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "PyInstaller is not found in PATH or the active Python virtual environment."
    exit 1
}

# 3. Clean prior build artifacts
Write-Host "Cleaning prior build and dist directories..." -ForegroundColor Yellow
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }

# 4. Verify Icon
$IconPath = Join-Path $ProjectRoot "packaging\assets\icon.ico"
if (-not (Test-Path $IconPath)) {
    Write-Warning "Icon not found at $IconPath."
}

# 5. Run PyInstaller
$SpecFile = Join-Path $ProjectRoot "packaging\audioscope.spec"
Write-Host "Executing PyInstaller with spec: $SpecFile..." -ForegroundColor Green
Set-Location $ProjectRoot
pyinstaller --noconfirm --clean $SpecFile

$ExeOutput = Join-Path $DistDir "AudioScope\AudioScope.exe"
if (-not (Test-Path $ExeOutput)) {
    Write-Error "Build failed: $ExeOutput was not generated."
    exit 1
}

Write-Host "Executable generated successfully at: $ExeOutput" -ForegroundColor Green

# 6. Optional Inno Setup Compilation
if (-not $SkipInstaller) {
    $IssPath = Join-Path $ProjectRoot "packaging\installer.iss"
    $IsccCandidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
    )
    $IsccExe = $IsccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

    if ($IsccExe) {
        Write-Host "Compiling Windows Installer using Inno Setup ($IsccExe)..." -ForegroundColor Cyan
        & $IsccExe $IssPath
        Write-Host "Installer compiled successfully in $DistDir!" -ForegroundColor Green
    } else {
        Write-Host "Inno Setup (ISCC.exe) not found. Skipping installer setup generation." -ForegroundColor Gray
        Write-Host "Standalone portable folder is ready at: $(Join-Path $DistDir 'AudioScope')" -ForegroundColor Yellow
    }
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " AudioScope Windows Build Pipeline Finished." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

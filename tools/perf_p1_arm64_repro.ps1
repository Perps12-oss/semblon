# PERF P1 — Windows ARM64 OpenCV repro + recovery (lab only)
# Does NOT swap the S1 / product identity environment (x64 cv2).
# Authority: docs/PERF-P1-ARM64.md
#
# Usage (from repo root, PowerShell):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1 -PeOnly
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1 -TimeoutSec 20

param(
  [string]$Arm64Python = "C:\Users\S8633\AppData\Local\Programs\Python\Python314-arm64\python.exe",
  [string]$Venv = ".venv-arm64-perf",
  [string]$Bin = "C:\Users\S8633\.arm64-build\build\bin\Release",
  [string]$Pyd = "C:\Users\S8633\.arm64-build\build\lib\python3\Release\cv2.cp314-win_arm64.pyd",
  [double]$TimeoutSec = 20,
  [switch]$PeOnly,
  [switch]$SkipVenvCreate
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "PERF P1 ARM64 OpenCV lab probe — identity firewall: do not swap S1" -ForegroundColor Cyan

if (-not (Test-Path $Arm64Python)) {
  throw "ARM64 Python not found: $Arm64Python"
}

if (-not $SkipVenvCreate -and -not (Test-Path $Venv)) {
  Write-Host "Creating isolated venv $Venv (not S1)..."
  & $Arm64Python -m venv $Venv
}

$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
  throw "Missing $Py — create venv or pass existing -Venv"
}

$env:SEMBLON_ARM64_OPENCV_BIN = $Bin
$env:SEMBLON_ARM64_OPENCV_PYD = $Pyd

Write-Host "1) PE layout (no LoadLibrary)..."
& $Py "tools\_perf_p1_load_cv2.py" --pe-only --bin $Bin --pyd $Pyd
if ($LASTEXITCODE -ne 0) { throw "pe-only failed exit=$LASTEXITCODE" }

if ($PeOnly) {
  Write-Host "PeOnly set — stopping before LoadLibrary."
  exit 0
}

Write-Host "2) Timed LoadLibrary (fail-fast per DLL; hang expected historically on $([IO.Path]::GetFileName($Bin))\opencv_geometry500.dll)..."
& $Py "tools\_perf_p1_load_cv2.py" --bin $Bin --pyd $Pyd --timeout $TimeoutSec --json
$code = $LASTEXITCODE
Write-Host "timed load exit=$code (0=ok, 2=timeout/hang, 3=other failure)"

Write-Host "3) Timed import via lab opencv (subprocess fail-fast)..."
& $Py -m semblon lab opencv --timeout 8
Write-Host "lab opencv exit=$LASTEXITCODE"

Write-Host @"

Recovery / next (owner only — still no S1 swap):
  - If geometry DLL still hangs: rebuild OpenCV with different geometry config, or obtain a real win_arm64 wheel.
  - Do NOT pip-install into the S1 x64 env.
  - Do NOT claim native speedup until import_cv2 succeeds AND a separate-store folder timing is recorded vs docs/PERF-P0-BASELINE.md.
  - Product workers default stays 1 until measured.

"@
exit $code

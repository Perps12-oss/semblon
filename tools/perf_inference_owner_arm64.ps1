# PERF-6 — Owner Windows ARM64 native validation
# Compares:
#   A) Emulated x64 OpenCV DNN (production venv)
#   B) Native ARM64 ONNX Runtime experimental backend (.venv-arm64-perf)
#   C) Native ARM64 OpenCV DNN only if load succeeds
#
# Does NOT swap S1 / production defaults. Does NOT run 1K/5K/10K.
# Authority: docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md §PERF-6
#
# Usage (repo root, PowerShell on SKY):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_inference_owner_arm64.ps1 `
#     -Corpus "D:\path\to\owner-photographic-48still"
#
# Optional:
#   -X64Python / -X64Venv  for role A
#   -Arm64Python / -Arm64Venv for roles B/C
#   -AllowLabStandIn  (harness dry-run only — not PERF-6 PASS)

param(
  [Parameter(Mandatory = $true)]
  [string]$Corpus,

  [string]$Arm64Python = "C:\Users\S8633\AppData\Local\Programs\Python\Python314-arm64\python.exe",
  [string]$Arm64Venv = ".venv-arm64-perf",
  [string]$X64Venv = ".venv-312",
  [string]$X64Python = "",
  [string]$FacePack = "",
  [string]$OutDir = "docs\evidence\perf-inference",
  [switch]$AllowLabStandIn,
  [switch]$SkipRoleC,
  [switch]$SkipVenvCreate
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "PERF-6 owner ARM64 validation — production path untouched" -ForegroundColor Cyan

if (-not (Test-Path $Corpus)) {
  throw "Corpus not found: $Corpus (owner photographic 48-still required)"
}
$corpusLeaf = Split-Path -Leaf $Corpus
if ($Corpus -match "perf-inference-48still" -and -not $AllowLabStandIn) {
  throw "Refusing lab stand-in corpus. Pass -AllowLabStandIn only for dry-runs."
}

if (-not $FacePack) {
  $FacePack = Join-Path $env:USERPROFILE ".semblon\models\yunet_sface"
}
if (-not (Test-Path $FacePack)) {
  throw "Face pack missing: $FacePack"
}
$env:SEMBLON_PERF_FACE_PACK = $FacePack
$env:SEMBLON_FACE_PACK = $FacePack

# --- Resolve Pythons ---
if (-not (Test-Path $Arm64Python)) {
  throw "ARM64 Python not found: $Arm64Python"
}
if (-not $SkipVenvCreate -and -not (Test-Path $Arm64Venv)) {
  Write-Host "Creating isolated $Arm64Venv (not S1)..."
  & $Arm64Python -m venv $Arm64Venv
}
$Arm64Py = Join-Path $Arm64Venv "Scripts\python.exe"
if (-not (Test-Path $Arm64Py)) {
  throw "Missing $Arm64Py"
}

$X64Py = $null
if ($X64Python -and (Test-Path $X64Python)) {
  $X64Py = $X64Python
} elseif (Test-Path (Join-Path $X64Venv "Scripts\python.exe")) {
  $X64Py = (Resolve-Path (Join-Path $X64Venv "Scripts\python.exe")).Path
} else {
  throw "x64 venv python not found ($X64Venv). Pass -X64Python for role A (emulated OpenCV)."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$allow = @()
if ($AllowLabStandIn) { $allow = @("--allow-lab-stand-in") }

function Invoke-Role {
  param(
    [string]$Py,
    [string]$Role,
    [string]$Backend,
    [string]$Label
  )
  Write-Host "`n=== Role $Role ($Label) via $Py ===" -ForegroundColor Yellow
  & $Py -c "import platform,sys; print(sys.executable); print(platform.machine(), sys.version)"
  $benchOut = Join-Path $OutDir "owner-arm64-bench-$Role.json"
  $embOut = Join-Path $OutDir "owner-arm64-embeddings-$Role.json"
  $verifyOut = Join-Path $OutDir "owner-arm64-runtime-$Role.json"
  & $Py "tools\perf_inference_owner_arm64.py" verify --out $verifyOut
  if ($LASTEXITCODE -ne 0) { throw "verify $Role failed exit=$LASTEXITCODE" }
  & $Py "tools\perf_inference_owner_arm64.py" bench `
    --role $Role --backend $Backend --corpus $Corpus `
    --out $benchOut --embeddings-out $embOut @allow
  if ($LASTEXITCODE -ne 0) { throw "bench $Role failed exit=$LASTEXITCODE" }
}

# A — emulated x64 OpenCV production backend
Invoke-Role -Py $X64Py -Role "A" -Backend "opencv_dnn" -Label "emulated x64 OpenCV DNN"

# B — native ARM64 ORT experimental
Invoke-Role -Py $Arm64Py -Role "B" -Backend "ort_yunet_sface" -Label "native ARM64 ORT"

# C — native ARM64 OpenCV only if import works
$benchC = Join-Path $OutDir "owner-arm64-bench-C.json"
if (-not $SkipRoleC) {
  Write-Host "`n=== Probe native OpenCV DNN (role C) ===" -ForegroundColor Yellow
  & $Arm64Py -c "import cv2; print('cv2', cv2.__version__, hasattr(cv2,'FaceDetectorYN'))"
  if ($LASTEXITCODE -eq 0) {
    try {
      Invoke-Role -Py $Arm64Py -Role "C" -Backend "opencv_dnn" -Label "native ARM64 OpenCV DNN"
    } catch {
      Write-Host "Role C skipped/failed (expected if geometry DLL hangs): $_" -ForegroundColor DarkYellow
      if (Test-Path $benchC) { Remove-Item $benchC -Force }
    }
  } else {
    Write-Host "Role C skipped — OpenCV import failed on ARM64 venv (historical BLOCKED)." -ForegroundColor DarkYellow
  }
}

# Identity + decision (use ARM64 python; pure JSON compare)
$identityOut = Join-Path $OutDir "owner-arm64-identity-safety.json"
$decideOut = Join-Path $OutDir "owner-arm64-decision.json"
$embA = Join-Path $OutDir "owner-arm64-embeddings-A.json"
$embB = Join-Path $OutDir "owner-arm64-embeddings-B.json"
$benchA = Join-Path $OutDir "owner-arm64-bench-A.json"
$benchB = Join-Path $OutDir "owner-arm64-bench-B.json"

Write-Host "`n=== Identity safety (A OpenCV embeddings vs B ORT embeddings) ===" -ForegroundColor Yellow
& $Arm64Py "tools\perf_inference_owner_arm64.py" identity `
  --reference-embeddings $embA `
  --candidate-embeddings $embB `
  --out $identityOut
if ($LASTEXITCODE -ne 0) { throw "identity failed exit=$LASTEXITCODE" }

Write-Host "`n=== Decision gate ===" -ForegroundColor Yellow
$decideArgs = @(
  "tools\perf_inference_owner_arm64.py", "decide",
  "--bench-a", $benchA,
  "--bench-b", $benchB,
  "--identity", $identityOut,
  "--out", $decideOut
)
if (Test-Path $benchC) {
  $decideArgs += @("--bench-c", $benchC)
}
& $Arm64Py @decideArgs
if ($LASTEXITCODE -ne 0) { throw "decide failed exit=$LASTEXITCODE" }

Write-Host @"

PERF-6 complete. Evidence under $OutDir :
  owner-arm64-runtime-A.json / owner-arm64-runtime-B.json
  owner-arm64-bench-A.json / owner-arm64-bench-B.json
  owner-arm64-identity-safety.json
  owner-arm64-decision.json

Update docs/BUILD-STATUS.md and docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md from the decision JSON.
Do not cut over production. Do not run 1K/5K/10K yet.

"@ -ForegroundColor Green
exit 0

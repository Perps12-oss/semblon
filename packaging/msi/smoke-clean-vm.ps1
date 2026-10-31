<#
.SYNOPSIS
  Semblon code-MSI clean-VM smoke (Gate C engineering checklist wrapper).

.DESCRIPTION
  Automates checks that do not need the GUI. Prints MANUAL QA steps for
  shell / ingest / People / keep-discovery. Does not download weights.
  Does not claim Gate C PASS.

.NOTES
  Run on a fresh Windows 10/11 VM after installing Semblon-*-code.msi
  (signed preferred). Network can stay off for core offline checks once
  the MSI is on the machine.
#>
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\Programs\Semblon",
    [string]$StoreDir = "$env:LOCALAPPDATA\Semblon"
)

$ErrorActionPreference = "Stop"
Write-Host "`n=== SEMBLON CODE MSI SMOKE (engineering) ===" -ForegroundColor Cyan

$fail = 0

function Assert-True([bool]$ok, [string]$msg) {
    if ($ok) {
        Write-Host "PASS: $msg" -ForegroundColor Green
    } else {
        Write-Host "FAIL: $msg" -ForegroundColor Red
        $script:fail++
    }
}

# --- Automated ---
$cmd = Join-Path $InstallRoot "semblon.cmd"
Assert-True (Test-Path -LiteralPath $cmd) "semblon.cmd present under Programs\Semblon"

if (Test-Path -LiteralPath $InstallRoot) {
    $weights = @(Get-ChildItem -LiteralPath $InstallRoot -Recurse -Include *.onnx,buffalo_l -ErrorAction SilentlyContinue)
    Assert-True ($weights.Count -eq 0) "No .onnx / buffalo_l under install tree"
} else {
    Assert-True $false "Install root missing: $InstallRoot"
}

if (Test-Path -LiteralPath $cmd) {
    & $cmd --help | Out-Null
    Assert-True ($LASTEXITCODE -eq 0) "semblon.cmd --help exit 0"
}

Write-Host "`n--- MANUAL QA (copy results to the release ticket) ---" -ForegroundColor Yellow
Write-Host "1. Launch: `"$cmd`" shell  — PySide6 archive opens."
Write-Host "2. Add a small stills folder; ingest completes offline (no network required for core)."
Write-Host "3. Open Focus → draw a region → Find similar. With BYO region pack: scored hits; without: honest unavailable / colour-only."
Write-Host "4. Keep this find; reopen from keeps (if exposed) or confirm `{store}.discoveries.json` beside the store."
Write-Host "5. People: review a cluster → name a person (no auto-name)."
Write-Host "6. Uninstall MSI; confirm $StoreDir still present; Programs\Semblon gone."
Write-Host "7. If signed: SmartScreen shows verified publisher (not a full unknown-publisher block)."

Write-Host "`nStore path (survives uninstall): $StoreDir" -ForegroundColor Cyan
Write-Host "Full checklist: packaging\msi\smoke-checklist.md"
Write-Host "Signing runbook: packaging\msi\SIGNING_GATE.md"

if ($fail -gt 0) {
    Write-Host "`nSMOKE AUTOMATED CHECKS FAILED ($fail)" -ForegroundColor Red
    exit 1
}
Write-Host "`nSMOKE AUTOMATED CHECKS PASSED — complete MANUAL QA before Gate C claim" -ForegroundColor Green
exit 0

# Post-MSI / first-run bootstrap: create .venv and install Semblon (code only).
# Does NOT download or bundle buffalo_l. First real ingest may still pull weights
# via InsightFace into %USERPROFILE%\.insightface\models\buffalo_l.
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "-3.12"
)

$ErrorActionPreference = "Stop"
$Root = $Root.TrimEnd('\', '/')

$InstallScript = Join-Path $Root "tools\install-windows.ps1"
if (-not (Test-Path -LiteralPath $InstallScript)) {
    Write-Error "Missing $InstallScript - MSI payload incomplete."
}

Write-Host "Semblon MSI bootstrap (code only; no buffalo_l weights)..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $InstallScript -Root $Root `
    -PythonLauncher $PythonLauncher -PythonVersion $PythonVersion
if ($LASTEXITCODE -ne 0) {
    Write-Error "Bootstrap failed (exit $LASTEXITCODE)."
}

Write-Host "Store remains at %LOCALAPPDATA%\Semblon (not removed on uninstall)."
Write-Host "Weights: UNAVAILABLE for redistribution - docs\licenses.md"

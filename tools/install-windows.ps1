# One-time Windows install for this repository or MSI install root.
# Creates .venv and installs Semblon editable.
# Does not bundle buffalo_l weights (internal evaluation only; first ingest may download them).
param(
    [string]$Root = "",
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "-3.12"
)

$ErrorActionPreference = "Stop"

if ($Root) {
    $Root = $Root.TrimEnd('\', '/')
} else {
    $Root = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
        $Root = $PSScriptRoot
        if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
            Write-Error "Run this script from a Semblon checkout (pyproject.toml not found)."
        }
    }
}

if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
    Write-Error "pyproject.toml not found under $Root"
}

Set-Location $Root
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "Creating .venv with $PythonLauncher $PythonVersion"
    & $PythonLauncher $PythonVersion -m venv .venv
}

if (-not (Test-Path $VenvPy)) {
    Write-Error "venv python not found at $VenvPy"
}

& $VenvPy -m pip install -U pip
& $VenvPy -m pip install -r (Join-Path $Root "requirements.txt")
& $VenvPy -m pip install -e .
# Optional research only: pip install -e ".[gui]"  (S8 toolkit spike; not product Home)

& $VenvPy -c "import semblon; print('import ok', semblon.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Install finished but 'import semblon' failed. Delete .venv and re-run this script."
}

Write-Host ""
Write-Host "Install complete. Double-click semblon.cmd or run:"
Write-Host "  .\semblon.cmd home"
Write-Host "Store default: %LOCALAPPDATA%\Semblon\store.sqlite"
Write-Host "Upgrade preserves that store. Uninstall: tools\uninstall-windows.ps1 (keeps store)."
Write-Host "buffalo_l is internal evaluation only — see docs/licenses.md"
Write-Host "MSI code packaging: packaging\msi (weights UNAVAILABLE for redistribution)."

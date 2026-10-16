# One-time Windows install for this repository or MSI install root.
# Creates .venv and installs Semblon editable.
# Does not bundle buffalo_l weights. Ingest does not download them.
param(
    [string]$Root = "",
    [string]$PythonLauncher = "py",
    [string]$PythonVersion = "-3.12"
)

$ErrorActionPreference = "Stop"

function Exit-IfNativeFailed {
    param([string]$What)
    # $ErrorActionPreference=Stop does not fail PowerShell 5.1 on a native non-zero exit.
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Error "$What failed with exit code $LASTEXITCODE"
    }
}

# Dot-sourcing defines Exit-IfNativeFailed only. It must not create a venv.
if ($MyInvocation.InvocationName -eq '.') {
    return
}

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
    Exit-IfNativeFailed "venv create"
}

if (-not (Test-Path $VenvPy)) {
    Write-Error "venv python not found at $VenvPy"
}

& $VenvPy -m pip install -U pip
Exit-IfNativeFailed "pip upgrade"
& $VenvPy -m pip install -r (Join-Path $Root "requirements.txt")
Exit-IfNativeFailed "pip install -r requirements.txt"
# Product shell is PySide6 (`semblon shell`). The gui extra is required.
& $VenvPy -m pip install -e ".[gui]"
Exit-IfNativeFailed "pip install -e .[gui]"
# insightface depends on opencv-python. Keep only the pinned headless build.
# Uninstall can remove the shared cv2 package, so reinstall headless afterwards.
& $VenvPy -m pip uninstall -y opencv-python opencv-contrib-python
& $VenvPy -m pip install --force-reinstall --no-deps "opencv-python-headless==5.0.0.93"
Exit-IfNativeFailed "reinstall opencv-python-headless"
& $VenvPy (Join-Path $Root "tools\assert_one_opencv.py")
Exit-IfNativeFailed "one opencv"

& $VenvPy -c "import semblon, PySide6; print('import ok', semblon.__version__, 'PySide6', PySide6.__version__)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Install finished but 'import semblon' failed. Delete .venv and re-run this script."
}

Write-Host ""
Write-Host "Install complete. Double-click semblon.cmd or run:"
Write-Host "  .\semblon.cmd shell"
Write-Host "Store default: %LOCALAPPDATA%\Semblon\store.sqlite"
Write-Host "Upgrade preserves that store. Uninstall: tools\uninstall-windows.ps1 (keeps store)."
Write-Host "buffalo_l is internal evaluation only - see docs/licenses.md"
Write-Host "MSI code packaging: packaging\msi (weights UNAVAILABLE for redistribution)."

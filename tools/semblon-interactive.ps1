# Double-click entry: Semblon home (tk Home: ingest + Open Review).
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    # Smoke/automation only: skip the home UI and process this folder.
    [string]$Folder = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$Root = $Root.TrimEnd('\', '/')

trap {
    Write-Host ""
    Write-Host "Semblon launcher error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

function Test-SemblonImport {
    param([string]$PythonExe)
    & $PythonExe -c "import semblon" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Repair-SemblonInstall {
    param([string]$PythonExe, [string]$RepoRoot)
    $pyproject = Join-Path $RepoRoot "pyproject.toml"
    if (-not (Test-Path -LiteralPath $pyproject)) {
        return $false
    }
    Write-Host "Semblon package missing in this venv. Reinstalling editable install..." -ForegroundColor Yellow
    & $PythonExe -m pip install -e $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    return (Test-SemblonImport -PythonExe $PythonExe)
}

function Get-SemblonLaunch {
    # Prefer python -m semblon. Never run a stale semblon.exe when python exists
    # but import fails - that is the ModuleNotFoundError path after package moves.
    $candidates = @(
        @{ Py = Join-Path $Root ".venv\Scripts\python.exe"; Repo = $Root },
        @{ Py = Join-Path $Root "semblon\.venv\Scripts\python.exe"; Repo = (Join-Path $Root "semblon") }
    )
    foreach ($c in $candidates) {
        if (-not (Test-Path -LiteralPath $c.Py)) {
            continue
        }
        if (Test-SemblonImport -PythonExe $c.Py) {
            return @{ Kind = "py"; Path = $c.Py }
        }
        if (Repair-SemblonInstall -PythonExe $c.Py -RepoRoot $c.Repo) {
            return @{ Kind = "py"; Path = $c.Py }
        }
        # ASCII-only file: Windows PowerShell 5.1 often reads UTF-8 as CP1252;
        # an em-dash (U+2014) becomes a stray quote and breaks string parsing.
        $msg = @(
            "Semblon package still missing after reinstall under $($c.Repo)."
            "From that folder run:"
            "  powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1"
            "Then double-click semblon.cmd again."
        ) -join [Environment]::NewLine
        Write-Error $msg
        exit 1
    }
    $msiMarker = Join-Path $Root ".semblon-msi-install"
    $bootstrap = Join-Path $Root "tools\msi\bootstrap-install.ps1"
    $install = Join-Path $Root "tools\install-windows.ps1"
    if ((Test-Path -LiteralPath $msiMarker) -and (Test-Path -LiteralPath $bootstrap)) {
        Write-Host "MSI code install: bootstrapping .venv (no buffalo_l weights)..." -ForegroundColor Yellow
        & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap -Root $Root
        if ($LASTEXITCODE -ne 0) {
            Write-Error "MSI bootstrap failed. Install Python 3.12 (py launcher), then re-run Semblon."
            exit 1
        }
        $py = Join-Path $Root ".venv\Scripts\python.exe"
        if ((Test-Path -LiteralPath $py) -and (Test-SemblonImport -PythonExe $py)) {
            return @{ Kind = "py"; Path = $py }
        }
        Write-Error "MSI bootstrap finished but semblon import failed under $Root"
        exit 1
    }
    if (Test-Path -LiteralPath $install) {
        Write-Host "Semblon: .venv missing - running install-windows.ps1 once..." -ForegroundColor Yellow
        & powershell -NoProfile -ExecutionPolicy Bypass -File $install -Root $Root
        if ($LASTEXITCODE -ne 0) {
            Write-Error "install-windows.ps1 failed under $Root"
            exit 1
        }
        $py = Join-Path $Root ".venv\Scripts\python.exe"
        if ((Test-Path -LiteralPath $py) -and (Test-SemblonImport -PythonExe $py)) {
            return @{ Kind = "py"; Path = $py }
        }
    }
    $msg = @(
        "Semblon: repo .venv not found under $Root."
        "From this folder, once:"
        "  powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1"
        "Then double-click semblon.cmd."
    ) -join [Environment]::NewLine
    Write-Error $msg
    exit 1
}

function Invoke-SemblonProcess {
    param([string]$PhotoFolder)
    $cliArgs = @("process", $PhotoFolder)
    if ($NoOpen) { $cliArgs += "--no-open" }
    $launch = Get-SemblonLaunch
    & $launch.Path -m semblon @cliArgs
    exit $LASTEXITCODE
}

function Invoke-SemblonHome {
    $launch = Get-SemblonLaunch
    & $launch.Path -m semblon home
    exit $LASTEXITCODE
}

if ($Folder) {
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
        Write-Error "Folder not found: $Folder"
        exit 2
    }
    Invoke-SemblonProcess -PhotoFolder $Folder
}

Invoke-SemblonHome

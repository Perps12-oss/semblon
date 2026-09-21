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
    # but import fails — that is the ModuleNotFoundError path after package moves.
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
        Write-Error @"
Semblon package still missing after reinstall under $($c.Repo).
From that folder run:
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
Then double-click semblon.cmd again.
"@
        exit 1
    }
    Write-Error @"
Semblon: repo .venv not found under $Root.
From this folder, once:
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
Then double-click semblon.cmd.
"@
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

# Double-click entry: Semblon home (Choose folder / Open Review). Not full S8 shell.
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

function Get-SemblonLaunch {
    $candidates = @(
        @{ Exe = Join-Path $Root ".venv\Scripts\semblon.exe"; Py = Join-Path $Root ".venv\Scripts\python.exe" },
        @{ Exe = Join-Path $Root "semblon\.venv\Scripts\semblon.exe"; Py = Join-Path $Root "semblon\.venv\Scripts\python.exe" }
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c.Exe) {
            return @{ Kind = "exe"; Path = $c.Exe }
        }
        if (Test-Path -LiteralPath $c.Py) {
            return @{ Kind = "py"; Path = $c.Py }
        }
    }
    Write-Error "Semblon: repo .venv not found under $Root"
    exit 1
}

function Invoke-SemblonProcess {
    param([string]$PhotoFolder)
    $cliArgs = @("process", $PhotoFolder)
    if ($NoOpen) { $cliArgs += "--no-open" }
    $launch = Get-SemblonLaunch
    if ($launch.Kind -eq "exe") {
        & $launch.Path @cliArgs
        exit $LASTEXITCODE
    }
    & $launch.Path -m semblon @cliArgs
    exit $LASTEXITCODE
}

function Invoke-SemblonHome {
    $launch = Get-SemblonLaunch
    if ($launch.Kind -eq "exe") {
        & $launch.Path home
        exit $LASTEXITCODE
    }
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

# Double-click entry: native folder picker, then semblon process (no venv activate).
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    # Smoke/automation only: skip the dialog and process this folder.
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

function Invoke-SemblonProcess {
    param([string]$PhotoFolder)
    $cliArgs = @("process", $PhotoFolder)
    if ($NoOpen) { $cliArgs += "--no-open" }

    $candidates = @(
        @{ Exe = Join-Path $Root ".venv\Scripts\semblon.exe"; Py = Join-Path $Root ".venv\Scripts\python.exe" },
        @{ Exe = Join-Path $Root "semblon\.venv\Scripts\semblon.exe"; Py = Join-Path $Root "semblon\.venv\Scripts\python.exe" }
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c.Exe) {
            & $c.Exe @cliArgs
            exit $LASTEXITCODE
        }
        if (Test-Path -LiteralPath $c.Py) {
            & $c.Py -m semblon @cliArgs
            exit $LASTEXITCODE
        }
    }
    Write-Error "Semblon: repo .venv not found under $Root"
    exit 1
}

if ($Folder) {
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
        Write-Error "Folder not found: $Folder"
        exit 2
    }
    Invoke-SemblonProcess -PhotoFolder $Folder
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Choose a folder of photos for Semblon to process"
$dialog.ShowNewFolderButton = $false

$result = $dialog.ShowDialog()
if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
    exit 0
}

$selected = $dialog.SelectedPath
if (-not $selected) {
    exit 0
}

Invoke-SemblonProcess -PhotoFolder $selected

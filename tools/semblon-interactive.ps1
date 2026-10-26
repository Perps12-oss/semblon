# Double-click entry: Semblon archive shell (PySide6).
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    # Smoke/automation only: skip the home UI and process this folder.
    [string]$Folder = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

# Normalize Root, but keep drive roots ("C:\") intact - TrimEnd would turn "C:\" into "C:".
$Root = $Root.TrimEnd('\', '/')
if ($Root -match '^[A-Za-z]:$') { $Root = "$Root\" }

trap {
    Write-Host ""
    Write-Host "Semblon launcher error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

function Test-SemblonImport {
    param([string]$PythonExe)
    # A half-finished install can import semblon from the folder but still lack the window toolkit.
    & $PythonExe -c "import semblon, PySide6, cv2" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Repair-SemblonInstall {
    param([string]$PythonExe, [string]$RepoRoot)
    $pyproject = Join-Path $RepoRoot "pyproject.toml"
    if (-not (Test-Path -LiteralPath $pyproject)) {
        return $false
    }
    Write-Host "Semblon setup is incomplete in this venv. Finishing the install..." -ForegroundColor Yellow
    $installer = Join-Path $RepoRoot "tools\install-windows.ps1"
    if (Test-Path -LiteralPath $installer) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $installer -Root $RepoRoot
        return (Test-SemblonImport -PythonExe $PythonExe)
    }
    & $PythonExe -m pip install -e "${RepoRoot}[gui]"
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    & $PythonExe -m pip uninstall -y opencv-python opencv-contrib-python | Out-Null
    & $PythonExe -m pip install --force-reinstall --no-deps "opencv-python-headless==5.0.0.93"
    if ($LASTEXITCODE -ne 0) {
        # Pinned build may not exist for this Python; fall back to the normal headless wheel.
        & $PythonExe -m pip install --force-reinstall opencv-python-headless
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
        Write-Host $msg -ForegroundColor Red
        exit 1
    }
    $msiMarker = Join-Path $Root ".semblon-msi-install"
    $bootstrap = Join-Path $Root "tools\msi\bootstrap-install.ps1"
    $install = Join-Path $Root "tools\install-windows.ps1"
    if ((Test-Path -LiteralPath $msiMarker) -and (Test-Path -LiteralPath $bootstrap)) {
        Write-Host "MSI code install: bootstrapping .venv (no buffalo_l weights)..." -ForegroundColor Yellow
        & powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap -Root $Root
        if ($LASTEXITCODE -ne 0) {
            Write-Host "MSI bootstrap failed. Install Python 3.12 (py launcher), then re-run Semblon." -ForegroundColor Red
            exit 1
        }
        $py = Join-Path $Root ".venv\Scripts\python.exe"
        if ((Test-Path -LiteralPath $py) -and (Test-SemblonImport -PythonExe $py)) {
            return @{ Kind = "py"; Path = $py }
        }
        Write-Host "MSI bootstrap finished but semblon import failed under $Root" -ForegroundColor Red
        exit 1
    }
    if (Test-Path -LiteralPath $install) {
        Write-Host "Semblon: .venv missing - running install-windows.ps1 once..." -ForegroundColor Yellow
        & powershell -NoProfile -ExecutionPolicy Bypass -File $install -Root $Root
        if ($LASTEXITCODE -ne 0) {
            Write-Host "install-windows.ps1 failed under $Root" -ForegroundColor Red
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
    Write-Host $msg -ForegroundColor Red
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

function Invoke-SemblonShell {
    $launch = Get-SemblonLaunch
    $pyw = $launch.Path -replace 'python\.exe$', 'pythonw.exe'
    $exe = if (Test-Path -LiteralPath $pyw) { $pyw } else { $launch.Path }

    # pythonw has no console; capture stderr so an early crash is reported
    # instead of the app silently never appearing.
    $log = Join-Path $env:TEMP "semblon-shell.err.log"
    if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue }

    $proc = Start-Process -FilePath $exe `
        -ArgumentList "-m semblon shell" `
        -RedirectStandardError $log `
        -PassThru

    Start-Sleep -Seconds 2
    if ($proc.HasExited -and $proc.ExitCode -ne 0) {
        Write-Host "Semblon shell exited with code $($proc.ExitCode)." -ForegroundColor Red
        if ((Test-Path -LiteralPath $log) -and ((Get-Item -LiteralPath $log).Length -gt 0)) {
            Write-Host "--- $log ---" -ForegroundColor Yellow
            Get-Content -LiteralPath $log | Write-Host
        } else {
            Write-Host "No stderr captured. Run this for the full traceback:" -ForegroundColor Yellow
            Write-Host "  `"$($launch.Path)`" -m semblon shell" -ForegroundColor Yellow
        }
        exit 1
    }
    exit 0
}

if ($Folder) {
    if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
        Write-Host "Folder not found: $Folder" -ForegroundColor Red
        exit 2
    }
    Invoke-SemblonProcess -PhotoFolder $Folder
}

Invoke-SemblonShell
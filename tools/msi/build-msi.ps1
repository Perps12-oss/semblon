# Build Semblon code MSI on Windows (WiX Toolset v4/v5).
# Does NOT bundle buffalo_l. Linux agents stage+validate only — run this on Windows.
#
# Prerequisites:
#   - Python 3.11–3.13 on PATH as `py -3.12` (or pass -PythonLauncher)
#   - WiX CLI:  dotnet tool install --global wix
#               wix extension add WixToolset.UI.wixext
#   - Optional signing: signtool on PATH + -SignThumbprint
#
# Usage (from repo root):
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignThumbprint ABC123...
param(
    [string]$Configuration = "Release",
    [string]$OutDir = "",
    [string]$SignThumbprint = "",
    [string]$SignPfxPath = "",
    [string]$SignPfxPassword = "",
    [string]$WixExe = "wix",
    [switch]$SkipStage
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
    Write-Error "Run from a Semblon checkout (pyproject.toml not found at $RepoRoot)."
}
Set-Location $RepoRoot

$MsiDir = Join-Path $RepoRoot "packaging\msi"
$Payload = Join-Path $MsiDir "payload"
$Dist = if ($OutDir) { $OutDir } else { Join-Path $MsiDir "dist" }
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

$Py = Get-Command py -ErrorAction SilentlyContinue
if (-not $Py) {
    $Py = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $Py) {
    Write-Error "Python launcher (py/python) required to stage payload."
}
$Python = $Py.Source

if (-not $SkipStage) {
    Write-Host "==> stage payload (code only)"
    & $Python (Join-Path $RepoRoot "tools\msi\stage-payload.py") --repo $RepoRoot --out $Payload
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "==> assert no weights"
& $Python (Join-Path $RepoRoot "tools\msi\assert-no-weights.py") $Payload
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> generate WiX components"
& $Python (Join-Path $RepoRoot "tools\msi\generate-components.py") --payload $Payload --out (Join-Path $MsiDir "PayloadComponents.wxs")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Read version from semblon/__init__.py
$Init = Get-Content (Join-Path $RepoRoot "semblon\__init__.py") -Raw
if ($Init -notmatch '__version__\s*=\s*"([^"]+)"') {
    Write-Error "Could not parse semblon.__version__"
}
$Version = $Matches[1]
Write-Host "ProductVersion=$Version"

$WixCmd = Get-Command $WixExe -ErrorAction SilentlyContinue
if (-not $WixCmd) {
    Write-Error @"
WiX CLI '$WixExe' not found on PATH.
Install on this Windows machine:
  dotnet tool install --global wix
  wix --version
Then re-run this script.
Payload + PayloadComponents.wxs are ready under packaging\msi\.
"@
}

$MsiName = "Semblon-$Version-code.msi"
$MsiPath = Join-Path $Dist $MsiName

Write-Host "==> wix build -> $MsiPath"
Push-Location $MsiDir
try {
    & $WixExe build `
        ".\Semblon.wxs" `
        ".\PayloadComponents.wxs" `
        -d "ProductVersion=$Version" `
        -o $MsiPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "==> post-build weight scan of MSI adjacent payload"
& $Python (Join-Path $RepoRoot "tools\msi\assert-no-weights.py") $Payload
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

function Resolve-SignTool {
    $cmd = Get-Command signtool -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe",
        "${env:ProgramFiles(x86)}\Microsoft SDKs\ClickOnce\SignTool\signtool.exe"
    )
    $found = Get-ChildItem -Path $candidates -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    Write-Error "signtool not found; install Windows SDK signing tools."
}

if ($SignPfxPath) {
    if (-not (Test-Path -LiteralPath $SignPfxPath)) {
        Write-Error "SignPfxPath not found: $SignPfxPath"
    }
    $SignToolPath = Resolve-SignTool
    Write-Host "==> signtool sign (pfx)"
    & $SignToolPath sign /f $SignPfxPath /p $SignPfxPassword /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /d "Semblon Installer" $MsiPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $SignToolPath verify /pa /v $MsiPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
elseif ($SignThumbprint) {
    $SignToolPath = Resolve-SignTool
    Write-Host "==> signtool sign (thumbprint)"
    & $SignToolPath sign /sha1 $SignThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /d "Semblon Installer" $MsiPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $SignToolPath verify /pa /v $MsiPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Built: $MsiPath"
Write-Host "Code MSI only — buffalo_l NOT included (licence UNAVAILABLE)."
Write-Host "Install is per-user under %LOCALAPPDATA%\Programs\Semblon"
Write-Host "Store stays at %LOCALAPPDATA%\Semblon (survives uninstall)."
Write-Host "Configuration=$Configuration (informational)"

# Remove the install-root .venv. Does NOT delete %LOCALAPPDATA%\Semblon unless -DeleteStore.
# For MSI installs, prefer Apps & Features uninstall (removes Programs\Semblon code);
# this script is for checkout / payload .venv cleanup. Store path is never the MSI code root.
param(
    [string]$Root = "",
    [switch]$DeleteStore
)

$ErrorActionPreference = "Stop"

if ($Root) {
    $Root = $Root.TrimEnd('\', '/')
} else {
    $Root = Split-Path -Parent $PSScriptRoot
}

$Venv = Join-Path $Root ".venv"
if (Test-Path $Venv) {
    Remove-Item -Recurse -Force $Venv
    Write-Host "Removed $Venv"
} else {
    Write-Host "No .venv at $Venv"
}

$StoreDir = Join-Path $env:LOCALAPPDATA "Semblon"
if ($DeleteStore) {
    if (Test-Path $StoreDir) {
        Remove-Item -Recurse -Force $StoreDir
        Write-Host "Deleted store $StoreDir"
    }
} else {
    Write-Host "Kept user data at $StoreDir (pass -DeleteStore to remove)"
}

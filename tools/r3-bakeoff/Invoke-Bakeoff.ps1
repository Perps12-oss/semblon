#Requires -Version 5.1
<#
.SYNOPSIS
  Thin wrapper around tools/r3-bakeoff/run_bakeoff.py

.NOTES
  Measurement stubs only. Does not claim PASS. Does not choose a toolkit winner.
#>
param(
  [string]$Toolkit = "",
  [string]$ToolkitVersion = "",
  [string]$Operator = "",
  [string]$Out = "",
  [string]$Frametimes = "",
  [string]$WcagPairs = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runner = Join-Path $PSScriptRoot "run_bakeoff.py"

$argsList = @($runner)
if ($Toolkit) { $argsList += @("--toolkit", $Toolkit) }
if ($ToolkitVersion) { $argsList += @("--toolkit-version", $ToolkitVersion) }
if ($Operator) { $argsList += @("--operator", $Operator) }
if ($Out) { $argsList += @("--out", $Out) }
if ($Frametimes) { $argsList += @("--frametimes", $Frametimes) }
if ($WcagPairs) { $argsList += @("--wcag-pairs", $WcagPairs) }

Push-Location $repoRoot
try {
  & py -3 @argsList
  exit $LASTEXITCODE
} finally {
  Pop-Location
}

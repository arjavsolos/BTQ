$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$legacyActivate = Join-Path $scriptDir "..\bin\Activate.ps1"

if (-not (Test-Path $legacyActivate)) {
    throw "Could not find activation script at $legacyActivate"
}

. $legacyActivate

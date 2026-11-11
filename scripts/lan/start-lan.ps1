# PowerShell 5.1+, central launcher for the LAN duel gateway.
# This script never deletes a room, database, audit file, or checkpoint.
[CmdletBinding()]
param(
    [ValidateSet('cpu_rdseed', 'cpu_rdrand', 'os_csprng', 'inherit')]
    [string]$Mode = 'cpu_rdseed',
    [switch]$NewRoom,
    [string]$HostAddress = '0.0.0.0',
    [ValidateRange(1, 65535)] [int]$Port = 8765,
    [string]$Scenario = 'IBS-S-03'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $root 'lan_server.py') -PathType Leaf)) {
    throw 'Cannot find lan_server.py; wrong installation location.'
}
if ($Mode -ne 'inherit') {
    $env:IBS_DICE_SOURCE = $Mode
}
if ($Mode -eq 'cpu_rdseed' -and -not (Test-Path -LiteralPath (Join-Path $root 'ibs_cpu_rng.dll') -PathType Leaf)) {
    throw 'RDSEED DLL is missing. Build ibs_cpu_rng.dll first; no silent RNG fallback.'
}
$argsList = @('lan_server.py', '--host', $HostAddress, '--port', [string]$Port)
if ($NewRoom) {
    Write-Warning 'NewRoom rotates room tickets. Make sure both players are ready for a new room.'
    $argsList += @('--new-room', '--scenario', $Scenario)
}
Push-Location $root
try {
    & python @argsList
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw ('lan_server.py failed, exit code ' + $code) }
} finally {
    Pop-Location
}

param([string]$ExpectedSession = '')
# Stops only processes verified as part of THIS standalone game's runtime.
. (Join-Path $PSScriptRoot 'game-runtime.ps1')
if ($ExpectedSession -ne '') {
    $StoredSession = Join-Path $RuntimeDir 'solo-session.txt'
    if (-not (Test-Path -LiteralPath $StoredSession)) { exit 0 }
    try { $ExistingSession = (Get-Content -LiteralPath $StoredSession -Raw -ErrorAction Stop).Trim() }
    catch { exit 0 }
    if ($ExistingSession -ne $ExpectedSession) { exit 0 }
}
# Invalidate the browser watcher before stopping verified game processes.
Remove-Item -LiteralPath (Join-Path $RuntimeDir 'solo-session.txt') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $RuntimeDir 'solo-presence.json') -Force -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $PidFile)) { Write-Host 'No recorded game processes.'; exit 0 }
$Ids = @(Get-Content -LiteralPath $PidFile)
$Backend = if ($Ids.Count -gt 0 -and [int]$Ids[0] -gt 0) { Get-GameProcess ([int]$Ids[0]) 'backend' }
$Frontend = if ($Ids.Count -gt 1 -and [int]$Ids[1] -gt 0) { Get-GameProcess ([int]$Ids[1]) 'frontend' }
Stop-GameProcess $Backend
Stop-GameProcess $Frontend
Save-GameProcesses $null $null
Write-Host 'Standalone game services stopped. Saved games and reports are unchanged.'

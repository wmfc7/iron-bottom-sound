# Standalone-only browser lifecycle watcher. PowerShell 5.1 compatible.
# Starts hidden, stops only the game's verified backend/frontend through stop-game.ps1.
param([Parameter(Mandatory = $true)][ValidatePattern('^[a-f0-9]{32}$')][string]$Session)
$ErrorActionPreference = 'Stop'
$RuntimeDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'tmp\runtime'
$SessionFile = Join-Path $RuntimeDir 'solo-session.txt'
$PresenceFile = Join-Path $RuntimeDir 'solo-presence.json'
$StopScript = Join-Path $PSScriptRoot 'stop-game.ps1'
$StartedUtc = [DateTime]::UtcNow
$EverSeen = $false
$Reason = $null

while ($true) {
    Start-Sleep -Seconds 2
    if (-not (Test-Path -LiteralPath $SessionFile)) { break }
    try { $CurrentSession = (Get-Content -LiteralPath $SessionFile -Raw -ErrorAction Stop).Trim() }
    catch { continue }
    # Another double-click started a newer session. Never stop the new game.
    if ($CurrentSession -ne $Session) { break }

    $Age = ([DateTime]::UtcNow - $StartedUtc).TotalSeconds
    if (Test-Path -LiteralPath $PresenceFile) {
        try {
            $PresenceItem = Get-Item -LiteralPath $PresenceFile -ErrorAction Stop
            $State = Get-Content -LiteralPath $PresenceFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            if ($State.session -ne $Session) { continue }
            if ($State.seen -eq $true) { $EverSeen = $true }
            $SinceUpdate = ([DateTime]::UtcNow - $PresenceItem.LastWriteTimeUtc).TotalSeconds
            if ($EverSeen -and [int]$State.active -eq 0 -and $SinceUpdate -ge 6) {
                $Reason = 'All solo game pages closed.'
                break
            }
            # Tab crash / browser forcibly killed: no pagehide beacon may arrive.
            # Generous timeout also protects background-tab timer throttling.
            if ($EverSeen -and $SinceUpdate -ge 150) {
                $Reason = 'No game page heartbeat for 150 seconds.'
                break
            }
        } catch {
            # Vite may be updating its JSON state file; retry next poll.
        }
    }
    if (-not $EverSeen -and $Age -ge 75) {
        $Reason = 'Game browser never connected within 75 seconds.'
        break
    }
}

if ($null -ne $Reason) {
    # Recheck the token just before stopping; an old watcher must not stop a
    # newly launched session (including a new session started during a poll).
    try { $CurrentSession = (Get-Content -LiteralPath $SessionFile -Raw -ErrorAction Stop).Trim() }
    catch { exit 0 }
    if ($CurrentSession -ne $Session) { exit 0 }
    try {
        "[$([DateTime]::UtcNow.ToString('o'))] $Reason" | Out-File -FilePath (Join-Path $RuntimeDir 'solo-auto-stop.log') -Append -Encoding UTF8
        & $StopScript -ExpectedSession $Session *>> (Join-Path $RuntimeDir 'solo-auto-stop.log')
    } catch {
        try { "[$([DateTime]::UtcNow.ToString('o'))] Auto-stop error: $_" | Out-File -FilePath (Join-Path $RuntimeDir 'solo-auto-stop.log') -Append -Encoding UTF8 } catch { }
    }
}

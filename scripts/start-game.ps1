# Restores the original standalone launcher after project organization.
# Standalone mode only binds to 127.0.0.1, never to EasyTier or public interfaces.
param([switch]$RestartBackend, [switch]$NoBrowser)
if ($env:IBS_LAUNCHER_UTF8 -eq '1') { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) }
. (Join-Path $PSScriptRoot 'game-runtime.ps1')
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
if (@(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue).Count -gt 0) {
    throw 'Port 8765 is running. Stop the multiplayer gateway before starting solo mode.'
}
$Backend = $null
$Frontend = $null
foreach ($entry in @(@(8000, 'backend'), @(5173, 'frontend'))) {
    $owners = @(Get-NetTCPConnection -LocalPort $entry[0] -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -gt 1) { throw "Port $($entry[0]) has multiple owners; left untouched." }
    if ($owners.Count -eq 1) {
        $owned = Get-GameListener $owners[0] $entry[1]
        if ($entry[1] -eq 'backend') { $Backend = $owned } else { $Frontend = $owned }
    }
}
Save-GameProcesses $Backend $Frontend
# Only browser-launched solo mode is automatically monitored. -NoBrowser preserves
# the original manual stop behavior (useful for development or headless runs).
$AutoStopEnabled = -not $NoBrowser
$SoloSessionFile = Join-Path $RuntimeDir 'solo-session.txt'
$SoloPresenceFile = Join-Path $RuntimeDir 'solo-presence.json'
$SoloSessionId = $null
if (-not $AutoStopEnabled) {
    # A manual/headless start cancels a lingering watcher from an earlier run.
    Remove-Item -LiteralPath $SoloSessionFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $SoloPresenceFile -Force -ErrorAction SilentlyContinue
}
if ($AutoStopEnabled) {
    $SoloSessionId = [guid]::NewGuid().ToString('N')
    # Invalidate any watcher from a previous launch before touching its processes.
    Set-Content -LiteralPath $SoloSessionFile -Value $SoloSessionId -Encoding ASCII
    Remove-Item -LiteralPath $SoloPresenceFile -Force -ErrorAction SilentlyContinue
    # A reused Vite server was started without this session token; restart only
    # a frontend already verified as belonging to THIS project.
    if ($null -ne $Frontend) {
        Write-Host 'Restarting the project frontend for browser-close monitoring.'
        Stop-GameProcess $Frontend
        $Frontend = $null
        Save-GameProcesses $Backend $null
        for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
            if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 250
        }
        if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Frontend port 5173 was not released; cannot safely enable browser monitoring.'
        }
    }
    $env:IBS_SOLO_MONITOR_ID = $SoloSessionId
}
if ($null -ne $Backend) {
    $Fresh = $false
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2; $Fresh = $health.status -eq 'ready' } catch { }
    if ($RestartBackend -or -not $Fresh) {
        Stop-GameProcess $Backend
        $Backend = $null
        for ($Attempt = 0; $Attempt -lt 20; $Attempt++) {
            if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 250
        }
    }
}
if ($null -eq $Backend) {
    $env:IBS_DB_PATH = Join-Path $ProjectRoot 'backend\iron-bottom-sound.sqlite3'
    $env:IBS_REPORTS_DIR = Join-Path $ProjectRoot 'backend\reports'
    $SourceDir = Join-Path $ProjectRoot 'backend\src'
    $Process = Start-Process -FilePath 'python' -ArgumentList @(
        '-m', 'uvicorn', 'iron_bottom_sound.api:app', '--app-dir', ('"' + $SourceDir + '"'),
        '--host', '127.0.0.1', '--port', '8000', '--reload', '--reload-dir', ('"' + $SourceDir + '"')
    ) -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $RuntimeDir 'backend.log') -RedirectStandardError (Join-Path $RuntimeDir 'backend-error.log') -WindowStyle Hidden -PassThru
    $Backend = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    Save-GameProcesses $Backend $Frontend
}
if ($null -eq $Frontend) {
    $Node = Get-Command 'node' -ErrorAction SilentlyContinue
    $NodePath = if ($Node) { $Node.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
    if (-not (Test-Path -LiteralPath $NodePath)) { throw 'Node.js not found. Install Node.js 20+.' }
    $Process = Start-Process -FilePath $NodePath -ArgumentList @(
        'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort'
    ) -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -RedirectStandardOutput (Join-Path $RuntimeDir 'frontend.log') -RedirectStandardError (Join-Path $RuntimeDir 'frontend-error.log') -WindowStyle Hidden -PassThru
    $Frontend = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    Save-GameProcesses $Backend $Frontend
}
$Ready = $false
for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
    if (-not (Get-Process -Id $Backend.ProcessId -ErrorAction SilentlyContinue) -or
        -not (Get-Process -Id $Frontend.ProcessId -ErrorAction SilentlyContinue)) {
        throw "A launched process exited. See logs in $RuntimeDir."
    }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1
        $page = Invoke-WebRequest 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 1
        if ($health.status -eq 'ready' -and $page.StatusCode -eq 200) { $Ready = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $Ready) { throw "Game did not become ready. See logs in $RuntimeDir." }
if ($AutoStopEnabled) {
    # Independent hidden watchdog: closing the .bat console does not leave a
    # permanent server behind. It invokes the EXISTING verified stop-game.ps1.
    $WatcherScript = Join-Path $PSScriptRoot 'Watch-SoloBrowser.ps1'
    if (-not (Test-Path -LiteralPath $WatcherScript)) {
        & (Join-Path $PSScriptRoot 'stop-game.ps1')
        throw 'Missing Watch-SoloBrowser.ps1; game services stopped to avoid orphan processes.'
    }
    try {
        $Watcher = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
            '-File', ('"' + $WatcherScript + '"'), '-Session', $SoloSessionId
        ) -WindowStyle Hidden -PassThru -ErrorAction Stop
        if ($null -eq $Watcher) { throw 'Watchdog did not start.' }
        Start-Process 'http://127.0.0.1:5173' -ErrorAction Stop
        Write-Host 'Auto-stop enabled: close all solo game tabs to stop backend and frontend.'
        Write-Host 'Normal close: ~6-10 sec. Browser crash fallback: up to ~150 sec.'
    } catch {
        & (Join-Path $PSScriptRoot 'stop-game.ps1')
        throw
    }
}
Write-Host 'Iron Bottom Sound SOLO mode ready: http://127.0.0.1:5173'
Write-Host 'Saved games are preserved; solo back-end binds only loopback.'

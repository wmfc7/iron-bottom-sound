# ASCII-only script for Windows PowerShell 5.1 and PowerShell 7.
# Install the LAN dice synchronization v3 patch; do not touch save files.
$ErrorActionPreference = 'Stop'
$sourceDir = $PSScriptRoot
$root = Split-Path -Parent $sourceDir
$server = Join-Path $root 'lan_server.py'
$oldPy = Join-Path $root 'lan_dice.py'
$oldJs = Join-Path $root 'lan_dice_client.js'
$srcPy = Join-Path $sourceDir 'lan_dice.py'
$srcJs = Join-Path $sourceDir 'lan_dice_client.js'

foreach ($path in @($server, $oldPy, $oldJs, $srcPy, $srcJs)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file missing: $path"
    }
}
$serverText = Get-Content -LiteralPath $server -Raw -Encoding UTF8
if ($serverText -notmatch 'IBS_LAN_INTERACTIVE_DICE_V2_ASYNC_SUBMIT') {
    throw 'Incompatible lan_server.py: v2 async dice marker not found. No files changed.'
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python command was not found. No files changed.'
}

# Check source files before replacing the working copy.
& python -m py_compile $srcPy
if ($LASTEXITCODE -ne 0) { throw 'Source Python syntax check failed. No files changed.' }
$hasNode = $null -ne (Get-Command node -ErrorAction SilentlyContinue)
if ($hasNode) {
    & node --check $srcJs
    if ($LASTEXITCODE -ne 0) { throw 'Source JavaScript syntax check failed. No files changed.' }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$backupPy = "$oldPy.before-sync-v3-$stamp.bak"
$backupJs = "$oldJs.before-sync-v3-$stamp.bak"
Copy-Item -LiteralPath $oldPy -Destination $backupPy -ErrorAction Stop
Copy-Item -LiteralPath $oldJs -Destination $backupJs -ErrorAction Stop

try {
    Copy-Item -LiteralPath $srcPy -Destination $oldPy -Force -ErrorAction Stop
    Copy-Item -LiteralPath $srcJs -Destination $oldJs -Force -ErrorAction Stop
    & python -m py_compile $oldPy
    if ($LASTEXITCODE -ne 0) { throw 'Installed Python syntax check failed.' }
    if ($hasNode) {
        & node --check $oldJs
        if ($LASTEXITCODE -ne 0) { throw 'Installed JavaScript syntax check failed.' }
    }
} catch {
    Copy-Item -LiteralPath $backupPy -Destination $oldPy -Force
    Copy-Item -LiteralPath $backupJs -Destination $oldJs -Force
    throw "Install failed and files were restored from backup: $($_.Exception.Message)"
}

Write-Host 'Dice sync v3 installed successfully.' -ForegroundColor Green
Write-Host "Backup Python: $backupPy"
Write-Host "Backup JS: $backupJs"
Write-Host 'Restart LAN server (CPU RDSEED mode) and press Ctrl+F5 on both clients.'

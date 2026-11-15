#requires -Version 5.1
[CmdletBinding()]
param([string]$ProjectRoot = '', [switch]$Force)
$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ProjectRoot) {
    if (Test-Path -LiteralPath (Join-Path $folder 'scripts\build\Build-Host.ps1')) { $ProjectRoot = $folder }
    elseif (Test-Path -LiteralPath (Join-Path $folder 'IBS-temporary-apps.json')) { $ProjectRoot = $folder }
    elseif (Test-Path -LiteralPath (Join-Path $folder 'iron-bottom-sound\IBS-temporary-apps.json')) {
        $ProjectRoot = Join-Path $folder 'iron-bottom-sound'
    } else { throw 'Cannot identify project directory. Pass -ProjectRoot explicitly.' }
}
$file = Join-Path $ProjectRoot 'IBS-temporary-apps.json'
$nodeDir = Join-Path $ProjectRoot '.ibs-build-tools\node'
$nodeMarker = Join-Path $nodeDir '.ibs-builder-portable-node.marker'
$hasNode = Test-Path -LiteralPath $nodeMarker -PathType Leaf
$hasApps = Test-Path -LiteralPath $file -PathType Leaf
if (-not $hasApps -and -not $hasNode) { Write-Host 'No managed temporary apps or portable Node were found.'; exit 0 }
$data = if ($hasApps) { Get-Content -LiteralPath $file -Raw | ConvertFrom-Json } else { [pscustomobject]@{winget_package_ids=@()} }
$allowed = @('Python.Python.3.12', 'OpenJS.NodeJS.LTS')
$ids = @($data.winget_package_ids)
foreach ($id in $ids) { if ([string]$id -cnotin $allowed) { throw ('Unexpected package in record: ' + $id) } }
if ($ids.Count -eq 0 -and -not $hasNode) { Write-Host 'No temporary apps remain.'; exit 0 }
Write-Host 'These package IDs were recorded as newly installed by the IBS builder:'
$ids | ForEach-Object { Write-Host ('  ' + $_) }
if ($hasNode) { Write-Host ('  Project-local portable Node: ' + $nodeDir) }
if (-not $Force) {
    $response = Read-Host 'Uninstall exactly these apps now? Type YES to confirm'
    if ($response -cne 'YES') { Write-Host 'Cancelled.'; exit 2 }
}
$winget = $null
if ($ids.Count -gt 0) {
    $winget = (Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    if (-not $winget) { throw 'winget.exe is unavailable. Manual cleanup is required.' }
}
$failed = @()
foreach ($id in $ids) {
    & $winget uninstall --id $id --exact --silent --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { $failed += $id; Write-Warning ('Uninstall failed: ' + $id) }
}
if ($failed.Count -eq 0) {
    if ($hasApps) { Remove-Item -LiteralPath $file -Force }
    if ($hasNode) {
        Remove-Item -LiteralPath $nodeDir -Recurse -Force
        $parent = Split-Path -Parent $nodeDir
        if ((Test-Path -LiteralPath $parent -PathType Container) -and @(Get-ChildItem -LiteralPath $parent -Force).Count -eq 0) { Remove-Item -LiteralPath $parent -Force }
    }
    Write-Host 'Cleanup complete. No pre-existing applications were selected.' -ForegroundColor Green
} else {
    $data.winget_package_ids = @($failed)
    $data | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $file -Encoding UTF8
    throw ('Some packages still require cleanup: ' + ($failed -join ', '))
}

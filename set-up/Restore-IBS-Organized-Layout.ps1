#requires -Version 5.1
[CmdletBinding(SupportsShouldProcess=$true)]
param([string]$ProjectRoot = '')
$ErrorActionPreference = 'Stop'
if (-not $ProjectRoot) { $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath
$items = @(
    @{ Name='lan_server.py'; Dir='lan' },
    @{ Name='lan_dice.py'; Dir='lan' },
    @{ Name='lan_dice_client.js'; Dir='lan' },
    @{ Name='lan_lobby.html'; Dir='lan' },
    @{ Name='lan_lobby_storage.py'; Dir='lan' },
    @{ Name='lan_seat.html'; Dir='lan' },
    @{ Name='lan_unseal.py'; Dir='lan' },
    @{ Name='ibs_cpu_rng.c'; Dir='CPU-RNG' },
    @{ Name='ibs_cpu_rng.dll'; Dir='CPU-RNG' }
)
# SHA-256 of the original organized source uploaded on 2026-11-16.
# A previous launcher copied these unmodified originals into the root. New patched
# source files can differ, so permit removing only these exact known original copies.
$knownOldHashes = @{
    'lan_server.py' = '9B094167B046F737AEE80A5F89729E8F2F0F162FD8CFB7D71160CDD19D1EE1B7'
    'lan_dice.py' = '15C36C22BF8A1BAB7438E2C28D4E9DAECF3DA65279DEB0CC79A5DE72D8B64CE7'
    'lan_dice_client.js' = '267988A285D3DF4781B912781460F27030729C8D82140BC6DA8AC72A4B13623B'
    'lan_lobby.html' = 'A9EAD851A53D5FFCA94C039890424566BF46EC8845B3874363CCC568F145A1A6'
    'lan_lobby_storage.py' = 'CB43F72D3922D9402C21DEAC451F32A3ED12C8FFAF37427BDA39DD14B43C8330'
    'lan_seat.html' = 'CE552C78D5BAA4B21179FB978AE1343283AEBC9F864BB2978C8F21E4F8EF2881'
    'lan_unseal.py' = '52B5F9ED83C031D7E7D90BC711BFC1D49FA92A569B5D18F30918A406CC12C781'
    'ibs_cpu_rng.c' = '43A77E52AC3664378474141E31C7DE00CC415522F3E09A483673CF99230ADD80'
    'ibs_cpu_rng.dll' = '5928E31F46E9ED2F1E3BE814AFB9B2F28ED0F65BBBE5D42DFAE3FF62951E6C84'
}
$removed = 0
$skipped = 0
foreach ($item in $items) {
    $old = Join-Path $ProjectRoot $item.Name
    $correct = Join-Path (Join-Path $ProjectRoot $item.Dir) $item.Name
    if (-not (Test-Path -LiteralPath $old -PathType Leaf)) { continue }
    if (-not (Test-Path -LiteralPath $correct -PathType Leaf)) {
        Write-Warning ('Keeping root file: canonical target missing: ' + $correct)
        $skipped++
        continue
    }
    $oldObj = Get-Item -LiteralPath $old -Force
    $correctObj = Get-Item -LiteralPath $correct -Force
    if ((($oldObj.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) -or
        (($correctObj.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        Write-Warning ('Keeping linked file: ' + $old)
        $skipped++
        continue
    }
    $oldHash = (Get-FileHash -LiteralPath $old -Algorithm SHA256).Hash
    $correctHash = (Get-FileHash -LiteralPath $correct -Algorithm SHA256).Hash
    if ($oldHash -ne $correctHash -and $oldHash -ne $knownOldHashes[$item.Name]) {
        Write-Warning ('Keeping unknown modified root file (SHA-256 differs): ' + $old)
        $skipped++
        continue
    }
    if ($PSCmdlet.ShouldProcess($old, 'Remove duplicate copy after SHA256 match')) {
        Remove-Item -LiteralPath $old -Force -ErrorAction Stop
        Write-Host ('Removed identical legacy duplicate: ' + $item.Name) -ForegroundColor Green
        $removed++
    }
}
Write-Host ('Organized cleanup: removed ' + $removed + ' verified root duplicates; kept ' + $skipped + ' nonidentical/missing-target files.')
if ($skipped -gt 0) { exit 2 }

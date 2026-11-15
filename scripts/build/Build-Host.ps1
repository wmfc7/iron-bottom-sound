[CmdletBinding()]
param(
  [ValidateSet('cpu_rdseed','cpu_rdrand','os_csprng')][string]$DiceMode = 'cpu_rdseed',
  [switch]$RebuildCpuRng,
  [switch]$SkipFrontend,
  [switch]$SkipTests
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$distRoot = Join-Path $root 'dist\Iron-Bottom-Sound-Host'
$venv = Join-Path $root '.build-venv'
function Invoke-Checked([string]$Exe, [string[]]$ArgumentList) {
  & $Exe @ArgumentList
  if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgumentList -join ' ') failed with exit code $LASTEXITCODE" }
}
Set-Location $root
if (-not $SkipFrontend) {
  if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw 'pnpm not found. Install Node.js 22 LTS and run: npm install -g pnpm' }
  Push-Location (Join-Path $root 'frontend')
  try {
    Invoke-Checked 'pnpm' @('install','--frozen-lockfile')
    Invoke-Checked 'pnpm' @('run','build')
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $root 'frontend\dist\index.html'))) { throw 'frontend/dist/index.html is missing' }
if (-not (Test-Path $venv)) { Invoke-Checked 'py' @('-3.11','-m','venv',$venv) }
$pythonExe = Join-Path $venv 'Scripts\python.exe'
Invoke-Checked $pythonExe @('-m','pip','install','--upgrade','pip')
Invoke-Checked $pythonExe @('-m','pip','install','-e','.','pyinstaller>=6.10')
if (-not $SkipTests) { Invoke-Checked $pythonExe @('-m','pytest','tests/test_lan_easytier_lobby.py','tests/test_lan_easytier_autofind.py','-q') }
if ($DiceMode -eq 'cpu_rdseed' -or $DiceMode -eq 'cpu_rdrand') {
  $rngDll = Join-Path $root 'ibs_cpu_rng.dll'
  if ($RebuildCpuRng) {
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
      throw 'Rebuilding the optional CPU RNG DLL requires MSVC cl.exe. Use the supplied prebuilt DLL by omitting -RebuildCpuRng.'
    }
    Invoke-Checked 'cl.exe' @('/nologo','/LD','/O2','/W4','/GS','ibs_cpu_rng.c','/Fe:ibs_cpu_rng.dll')
  }
  if (-not (Test-Path -LiteralPath $rngDll -PathType Leaf)) {
    throw 'ibs_cpu_rng.dll is missing. Place the supplied Windows x64 DLL in the project root, or explicitly rebuild with -RebuildCpuRng from an MSVC x64 tools prompt.'
  }
  # Validate the PE machine type before copying. This catches x86/ARM DLLs early.
  $bytes = [System.IO.File]::ReadAllBytes($rngDll)
  if ($bytes.Length -lt 256 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) { throw 'ibs_cpu_rng.dll is not a valid PE image (missing MZ header).' }
  $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
  if ($peOffset -lt 0 -or ($peOffset + 6) -gt $bytes.Length -or [System.Text.Encoding]::ASCII.GetString($bytes, $peOffset, 4) -ne "PE`0`0") { throw 'ibs_cpu_rng.dll has an invalid PE header.' }
  $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
  if ($machine -ne 0x8664) { throw ('ibs_cpu_rng.dll must be Windows x64 (AMD64); detected PE machine 0x{0:X4}.' -f $machine) }
  Write-Host ('Using prebuilt Windows x64 CPU RNG DLL: {0}' -f $rngDll)
}
if (Test-Path $distRoot) { Remove-Item $distRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
$work = Join-Path $root 'build\pyinstaller'
New-Item -ItemType Directory -Force -Path $work | Out-Null
Invoke-Checked $pythonExe @('-m','PyInstaller','--noconfirm','--clean','--onedir','--name','IBSHost','--distpath',(Join-Path $root 'build\pyinstaller-dist'),'--workpath',$work,'--specpath',(Join-Path $root 'build\spec'),'--paths',(Join-Path $root 'backend\src'),'--collect-all','iron_bottom_sound','--hidden-import','lan_lobby_storage','--hidden-import','lan_unseal','--hidden-import','lan_dice','lan_server.py')
New-Item -ItemType Directory -Force -Path (Join-Path $distRoot 'app') | Out-Null
Copy-Item (Join-Path $root 'build\pyinstaller-dist\IBSHost\*') (Join-Path $distRoot 'app') -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $distRoot 'frontend\dist'),(Join-Path $distRoot 'backend\lan-saves'),(Join-Path $distRoot 'backend\reports'),(Join-Path $distRoot 'resources\derived\structured'),(Join-Path $distRoot 'resources\originals\assets\images'),(Join-Path $distRoot 'resources\originals\rules'),(Join-Path $distRoot 'resources\originals\scenarios'),(Join-Path $distRoot 'resources\originals\records'),(Join-Path $distRoot 'docs\rules') | Out-Null
Copy-Item (Join-Path $root 'frontend\dist\*') (Join-Path $distRoot 'frontend\dist') -Recurse -Force
Copy-Item (Join-Path $root 'lan_lobby.html') $distRoot -Force
Copy-Item (Join-Path $root 'lan_seat.html') $distRoot -Force
Copy-Item (Join-Path $root 'resources\derived\structured\*') (Join-Path $distRoot 'resources\derived\structured') -Recurse -Force
Copy-Item (Join-Path $root 'resources\originals\assets\images\*') (Join-Path $distRoot 'resources\originals\assets\images') -Recurse -Force
$requiredDocs = @(
 'resources\originals\rules\iron-bottom-sound-iv-rules-zh.pdf',
 'resources\originals\rules\player-aid-tables-zh.pdf',
 'resources\originals\scenarios\scenario-book-zh.pdf',
 'resources\originals\records\ship-record-manual-1.1-zh.pdf',
 'resources\originals\assets\images\岛屿.jpg'
)
foreach ($relative in $requiredDocs) {
  $source = Join-Path $root $relative
  if (-not (Test-Path $source)) { throw "Required game resource missing: $relative" }
  $destination = Join-Path $distRoot $relative
  New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
  Copy-Item $source $destination -Force
}
if ((Get-ChildItem (Join-Path $root 'docs\rules') -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) { Copy-Item (Join-Path $root 'docs\rules\*') (Join-Path $distRoot 'docs\rules') -Recurse -Force }
if ($DiceMode -in @('cpu_rdseed','cpu_rdrand')) { Copy-Item (Join-Path $root 'ibs_cpu_rng.dll') (Join-Path $distRoot 'app') -Force }
Copy-Item (Join-Path $root 'scripts\host\Start-Host.ps1') $distRoot -Force
Copy-Item (Join-Path $root 'scripts\host\Start_Host.bat') $distRoot -Force
Copy-Item (Join-Path $root 'scripts\host\README-Host.txt') $distRoot -Force
@"
@echo off
setlocal
cd /d "%~dp0"
set "IBS_ROOT=%~dp0"
set "IBS_DB_PATH=%~dp0backend\iron-bottom-sound.sqlite3"
set "IBS_REPORTS_DIR=%~dp0backend\reports"
set "IBS_DICE_SOURCE=$DiceMode"
set "IBS_DICE_CPU_DLL=%~dp0app\ibs_cpu_rng.dll"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Host.ps1" -DiceMode "$DiceMode"
if errorlevel 1 pause
"@ | Set-Content (Join-Path $distRoot 'Start_Host.bat') -Encoding ASCII
$zip = Join-Path $root 'dist\IBS-Host-Windows-x64.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $distRoot '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Host package created: $zip"

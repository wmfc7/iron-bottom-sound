[CmdletBinding()]
param(
  [ValidateSet('cpu_rdseed','cpu_rdrand','os_csprng')][string]$DiceMode = 'cpu_rdseed',
  [switch]$RebuildCpuRng,
  [switch]$SkipFrontend,
  [switch]$SkipTests,
  [string]$PythonPath = ''
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$distRoot = Join-Path $root 'dist\Iron-Bottom-Sound-Host'
$venv = Join-Path $root '.build-venv'
function Invoke-Checked([string]$Exe, [string[]]$ArgumentList) {
  & $Exe @ArgumentList
  if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgumentList -join ' ') failed with exit code $LASTEXITCODE" }
}
# The project requires Python >=3.11 (pyproject.toml); do not pin an exact minor version.
# Keep version discovery inside the script (not in the param defaults) for PS 5.1.
# IBS_HOST_BUILD_PYTHON311PLUS_BUNDLE_V3
function Test-CompatiblePython([string]$Candidate) {
  if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
  try {
    # Avoid embedded quotes in PowerShell 5.1 native executable arguments.
    $probe = 'import sys;print(sys.version_info.major,sys.version_info.minor,sys.version_info.micro,64 if sys.maxsize>2**32 else 32,sys.executable,sep=chr(124))'
    $lines = @(& $Candidate -c $probe 2>$null)
    if ($LASTEXITCODE -ne 0) { return $null }
    foreach ($line in $lines) {
      $value = ([string]$line).Trim()
      if ($value -notmatch '^(\d+)\|(\d+)\|(\d+)\|(\d+)\|(.+)$') { continue }
      $major = [int]$Matches[1]; $minor = [int]$Matches[2]; $micro = [int]$Matches[3]
      if ($major -ne 3 -or $minor -lt 11 -or [int]$Matches[4] -ne 64) { continue }
      return [pscustomobject]@{ Executable=$Candidate; Version=($major.ToString()+'.'+$minor.ToString()+'.'+$micro.ToString()); ActualPath=[string]$Matches[5] }
    }
  } catch { }
  return $null
}
function Find-CompatiblePython {
  $candidates = New-Object 'System.Collections.Generic.List[string]'
  $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
  # The setup script has already validated this Python path; prefer it when supplied.
  if (-not [string]::IsNullOrWhiteSpace($env:IBS_BUILD_PYTHON)) {
    $preferred = Test-CompatiblePython $env:IBS_BUILD_PYTHON
    if ($preferred) { return $preferred }
  }
  # Python launcher detects installations not exposed through PATH.
  if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    try {
      $launcherList = & py -0p 2>$null
      foreach ($entry in @($launcherList)) {
        $found = [regex]::Match([string]$entry, '(?<python>[A-Za-z]:\\[^\r\n]*?python\.exe)\s*$')
        if ($found.Success) {
          $candidatePath = $found.Groups['python'].Value.Trim()
          if ($seen.Add($candidatePath)) { $candidates.Add($candidatePath) }
        }
      }
      # Some py.exe versions use a different listing format.
      $launcherPython = & py -3 -c 'import sys;print(sys.executable)' 2>$null
      if ($LASTEXITCODE -eq 0) {
        foreach ($candidatePath in @($launcherPython)) {
          $candidatePath = ([string]$candidatePath).Trim()
          if ($candidatePath -and $seen.Add($candidatePath)) { $candidates.Add($candidatePath) }
        }
      }
    } catch { }
  }
  foreach ($name in @('python.exe','python3.exe')) {
    foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
      if ($command -and $command.Source -and $seen.Add($command.Source)) { $candidates.Add($command.Source) }
    }
  }
  foreach ($candidatePath in @('D:\Python\python.exe','C:\Python\python.exe')) {
    if ($seen.Add($candidatePath)) { $candidates.Add($candidatePath) }
  }
  foreach ($directory in @(
      (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
      (Join-Path $env:ProgramFiles 'Python'),
      'C:\Python') ) {
    if (-not (Test-Path -LiteralPath $directory)) { continue }
    foreach ($item in @(Get-ChildItem -LiteralPath $directory -Filter python.exe -File -Recurse -ErrorAction SilentlyContinue)) {
      if ($seen.Add($item.FullName)) { $candidates.Add($item.FullName) }
    }
  }
  foreach ($registryRoot in @('HKCU:\Software\Python\PythonCore','HKLM:\Software\Python\PythonCore','HKLM:\Software\WOW6432Node\Python\PythonCore')) {
    if (-not (Test-Path -LiteralPath $registryRoot)) { continue }
    foreach ($versionKey in @(Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue)) {
      $installKey = Join-Path $versionKey.PSPath 'InstallPath'
      if (-not (Test-Path -LiteralPath $installKey)) { continue }
      try {
        $installLocation = (Get-Item -LiteralPath $installKey).GetValue('')
        if ($installLocation) {
          $candidatePath = Join-Path $installLocation 'python.exe'
          if ($seen.Add($candidatePath)) { $candidates.Add($candidatePath) }
        }
      } catch { }
    }
  }
  foreach ($candidatePath in $candidates) {
    $info = Test-CompatiblePython $candidatePath
    if ($info) { return $info }
  }
  return $null
}

function New-BuildVenv([string]$Interpreter) {
  Invoke-Checked $Interpreter @('-m','venv',$venv)
  $venvInterpreter = Join-Path $venv 'Scripts\python.exe'
  if (-not (Test-CompatiblePython $venvInterpreter)) {
    throw 'Virtual environment was created but does not contain Python >=3.11 x64.'
  }
}

Set-Location $root
if (-not $SkipFrontend) {
  $pnpmCommand = Get-Command pnpm.cmd -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $pnpmCommand) { throw 'pnpm.cmd not found. Run Run-IBS-Setup.cmd to prepare temporary pnpm 10.' }
  Push-Location (Join-Path $root 'frontend')
  try {
    Invoke-Checked $pnpmCommand.Source @('install','--frozen-lockfile')
    Invoke-Checked $pnpmCommand.Source @('run','build')
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $root 'frontend\dist\index.html'))) { throw 'frontend/dist/index.html is missing' }
$pythonExe = Join-Path $venv 'Scripts\python.exe'
$existingVenv = if (Test-Path -LiteralPath $pythonExe) { Test-CompatiblePython $pythonExe } else { $null }
if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
  # Explicit interpreter choice must take precedence over an existing virtualenv.
  $selectedPython = Test-CompatiblePython $PythonPath
  if (-not $selectedPython) { throw "-PythonPath must point to an existing Python >=3.11 x64 interpreter: $PythonPath" }
  if (Test-Path -LiteralPath $venv) {
    Write-Host 'Recreating .build-venv to honor the explicitly selected -PythonPath.'
    Remove-Item -LiteralPath $venv -Recurse -Force
  }
  New-BuildVenv $selectedPython.Executable
} elseif ($existingVenv) {
  Write-Host ("Reusing .build-venv: Python {0} ({1})" -f $existingVenv.Version,$existingVenv.ActualPath)
} else {
  $selectedPython = Find-CompatiblePython
  if (-not $selectedPython) {
    throw 'No compatible Python >=3.11 x64 was found. Check py -0p, or run Build-Host.ps1 -PythonPath "C:\path\to\python.exe".'
  }
  Write-Host ("Selected Python {0}: {1}" -f $selectedPython.Version,$selectedPython.ActualPath)
  if (Test-Path -LiteralPath $venv) {
    Write-Host 'Existing .build-venv is missing or incompatible; recreating it.'
    Remove-Item -LiteralPath $venv -Recurse -Force
  }
  New-BuildVenv $selectedPython.Executable
}
# The imported source archive may contain an empty .egg-info placeholder.
# pip sees it as an installed distribution with no version and can raise
# TypeError in check_install_conflicts during a self-upgrade.
$eggInfoDir = Join-Path $root 'backend\src\iron_bottom_sound.egg-info'
if (Test-Path -LiteralPath $eggInfoDir -PathType Container) {
  $eggInfoEntries = @(Get-ChildItem -LiteralPath $eggInfoDir -Force -ErrorAction Stop)
  if ($eggInfoEntries.Count -eq 0) {
    Remove-Item -LiteralPath $eggInfoDir -Recurse -Force
    Write-Host 'Removed empty iron_bottom_sound.egg-info metadata placeholder.'
  } elseif (-not (Test-Path -LiteralPath (Join-Path $eggInfoDir 'PKG-INFO') -PathType Leaf)) {
    Write-Warning 'iron_bottom_sound.egg-info has no PKG-INFO. Metadata may be incomplete; leaving nonempty folder untouched.'
  }
}
# Skip only the optional conflict *warning scan* while upgrading pip itself.
# The subsequent project/dependency installations still use normal checks.
Invoke-Checked $pythonExe @('-m','pip','install','--upgrade','pip','--no-warn-conflicts')
Invoke-Checked $pythonExe @('-m','pip','install','-e','.','pyinstaller>=6.10')
if (-not $SkipTests) {
  Invoke-Checked $pythonExe @('-m','pip','install','pytest>=8')
  Invoke-Checked $pythonExe @('-m','pytest','tests/test_lan_easytier_lobby.py','tests/test_lan_easytier_autofind.py','-q')
}
if ($DiceMode -eq 'cpu_rdseed' -or $DiceMode -eq 'cpu_rdrand') {
  $rngDll = Join-Path $root 'CPU-RNG\ibs_cpu_rng.dll'
  if ($RebuildCpuRng) {
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
      throw 'Rebuilding the optional CPU RNG DLL requires MSVC cl.exe. Use the supplied prebuilt DLL by omitting -RebuildCpuRng.'
    }
    Push-Location (Join-Path $root 'CPU-RNG')
    try { Invoke-Checked 'cl.exe' @('/nologo','/LD','/O2','/W4','/GS','ibs_cpu_rng.c','/Fe:ibs_cpu_rng.dll') }
    finally { Pop-Location }
  }
  if (-not (Test-Path -LiteralPath $rngDll -PathType Leaf)) {
    throw 'CPU-RNG\ibs_cpu_rng.dll is missing. Keep the supplied Windows x64 DLL in CPU-RNG, or explicitly rebuild with -RebuildCpuRng from an MSVC x64 tools prompt.'
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
Invoke-Checked $pythonExe @('-m','PyInstaller','--noconfirm','--clean','--onedir','--name','IBSHost','--distpath',(Join-Path $root 'build\pyinstaller-dist'),'--workpath',$work,'--specpath',(Join-Path $root 'build\spec'),'--paths',(Join-Path $root 'backend\src'),'--paths',(Join-Path $root 'lan'),'--collect-all','iron_bottom_sound','--hidden-import','lan_lobby_storage','--hidden-import','lan_unseal','--hidden-import','lan_dice',(Join-Path $root 'lan\lan_server.py'))
New-Item -ItemType Directory -Force -Path (Join-Path $distRoot 'app') | Out-Null
Copy-Item (Join-Path $root 'build\pyinstaller-dist\IBSHost\*') (Join-Path $distRoot 'app') -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $distRoot 'frontend\dist'),(Join-Path $distRoot 'backend\lan-saves'),(Join-Path $distRoot 'backend\reports'),(Join-Path $distRoot 'resources\derived\structured'),(Join-Path $distRoot 'resources\originals\assets\images'),(Join-Path $distRoot 'resources\originals\rules'),(Join-Path $distRoot 'resources\originals\scenarios'),(Join-Path $distRoot 'resources\originals\records'),(Join-Path $distRoot 'docs\rules') | Out-Null
Copy-Item (Join-Path $root 'frontend\dist\*') (Join-Path $distRoot 'frontend\dist') -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $distRoot 'lan') | Out-Null
foreach ($asset in @('lan_lobby.html', 'lan_seat.html', 'lan_dice_client.js')) {
  Copy-Item (Join-Path $root ('lan\' + $asset)) (Join-Path $distRoot 'lan') -Force
}
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
if ($DiceMode -in @('cpu_rdseed','cpu_rdrand')) { Copy-Item (Join-Path $root 'CPU-RNG\ibs_cpu_rng.dll') (Join-Path $distRoot 'app') -Force }
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

#requires -Version 5.1
<#
Iron Bottom Sound builder, PowerShell 5.1 / Windows x64.
Builds IN an existing extracted project; does not extract archives.
Uses existing Node or project-local verified Node ZIP; installs missing Python via winget, then removes
ONLY package IDs verified absent before this run and installed by this script.
EasyTier and previously installed applications are never removed.
Review the included README before use.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = '',
    [string]$PythonPath = '',
    [string]$NodePath = '',
    [ValidateSet('cpu_rdseed','cpu_rdrand','os_csprng')]
    [string]$DiceMode = 'cpu_rdseed',
    [switch]$SkipTests,
    [switch]$NoAppInstall,
    [switch]$KeepInstalledApps
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDirectory) { $scriptDirectory = (Get-Location).ProviderPath }
$script:Transcribing = $false
$script:AddedApps = New-Object 'System.Collections.Generic.List[string]'
$script:WorkingFolder = $null
$script:LogFile = $null
$script:StateFile = $null
$script:CreatedVenv = $false
$script:TemporaryPython = $false
$script:PortableNodeCreated = $false
$script:PortableNodeRoot = $null
$script:BuildSucceeded = $false

function Step([string]$Message) { Write-Host ("`n=== " + $Message + ' ===') -ForegroundColor Cyan }
function Invoke-Checked([string]$Exe, [string[]]$ArgumentList) {
    Write-Host ('Running: ' + $Exe + ' ' + ($ArgumentList -join ' '))
    & $Exe @ArgumentList
    if ($LASTEXITCODE -ne 0) { throw ('Command failed, exit ' + $LASTEXITCODE + ': ' + $Exe) }
}
function Find-App([string]$Name, [string[]]$Fallbacks) {
    $result = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($result) { return [string]$result.Source }
    foreach ($file in $Fallbacks) {
        if ($file -and (Test-Path -LiteralPath $file -PathType Leaf)) { return $file }
    }
    return $null
}
function Refresh-Path {
    $extra = @(
        [Environment]::GetEnvironmentVariable('Path','Machine'),
        [Environment]::GetEnvironmentVariable('Path','User'),
        $env:Path,
        (Join-Path $env:APPDATA 'npm'),
        (Join-Path $env:ProgramFiles 'nodejs'),
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs')
    )
    $env:Path = ($extra | Where-Object { $_ }) -join ';'
}
function Resolve-ExistingProject([string]$Specified) {
    if ($Specified) {
        $candidates = @($Specified)
    } else {
        $parent = Split-Path -Parent $scriptDirectory
        $candidates = @($scriptDirectory,
            (Join-Path $scriptDirectory 'iron-bottom-sound'),
            $parent, (Join-Path $parent 'iron-bottom-sound'))
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not $candidate -or -not (Test-Path -LiteralPath $candidate -PathType Container)) { continue }
        if (Test-Path -LiteralPath (Join-Path $candidate 'scripts\build\Build-Host.ps1') -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Extracted project folder not found. Put these installer files inside the iron-bottom-sound source folder, or pass -ProjectRoot "C:\path\to\iron-bottom-sound".'
}
function Test-RequiredSource([string]$Root) {
    $files = @('scripts\build\Build-Host.ps1','scripts\build\Build-Guest.ps1',
        'scripts\host\Start_Host.bat','frontend\pnpm-lock.yaml','pyproject.toml',
        'lan\lan_server.py','CPU-RNG\ibs_cpu_rng.dll',
        'resources\originals\rules\iron-bottom-sound-iv-rules-zh.pdf',
        'resources\originals\rules\player-aid-tables-zh.pdf',
        'resources\originals\scenarios\scenario-book-zh.pdf',
        'resources\originals\records\ship-record-manual-1.1-zh.pdf',
        'resources\originals\assets\images\岛屿.jpg')
    foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $file) -PathType Leaf)) {
            throw ('Project file missing: ' + $file)
        }
    }
}
function Test-PythonCandidate([string]$Exe, [string[]]$LaunchArgs) {
    if (-not $Exe) { return $null }
    try {
        # The probe contains no quotes: robust under Windows PowerShell 5.1 native argument handling.
        $probe = 'import sys;print(sys.version_info.major,sys.version_info.minor,sys.version_info.micro,64 if sys.maxsize>2**32 else 32,sys.executable,sep=chr(124))'
        $lines = @(& $Exe @LaunchArgs -c $probe 2>$null)
        if ($LASTEXITCODE -ne 0) { return $null }
        foreach ($line in $lines) {
            $text = ([string]$line).Trim()
            if ($text -notmatch '^(\d+)\|(\d+)\|(\d+)\|(\d+)\|(.+)$') { continue }
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            $micro = [int]$Matches[3]
            $bits = [int]$Matches[4]
            $realPath = [string]$Matches[5]
            if ($major -ne 3 -or $minor -lt 11 -or $bits -ne 64) { continue }
            if (-not (Test-Path -LiteralPath $realPath -PathType Leaf)) { continue }
            return [pscustomobject]@{ Path = $realPath; Version = ($major.ToString() + '.' + $minor.ToString() + '.' + $micro.ToString()) }
        }
    } catch { }
    return $null
}
function Get-RegisteredPythonPaths {
    # PEP 514 registry locations; covers system and per-user Python installations.
    $roots = @('HKCU:\Software\Python\PythonCore',
               'HKLM:\Software\Python\PythonCore',
               'HKLM:\Software\WOW6432Node\Python\PythonCore')
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($versionKey in @(Get-ChildItem -Path $root -ErrorAction SilentlyContinue)) {
            $installKey = Join-Path $versionKey.PSPath 'InstallPath'
            if (-not (Test-Path $installKey)) { continue }
            try {
                $key = Get-Item -LiteralPath $installKey -ErrorAction Stop
                $executable = [string]$key.GetValue('ExecutablePath')
                if ($executable) { Write-Output $executable }
                $folder = [string]$key.GetValue('')
                if ($folder) { Write-Output (Join-Path $folder 'python.exe') }
            } catch { }
        }
    }
    # Some winget/MSI records store only InstallLocation in the uninstall registry.
    foreach ($root in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                       'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                       'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
        if (-not (Test-Path $root)) { continue }
        foreach ($record in @(Get-ChildItem -Path $root -ErrorAction SilentlyContinue)) {
            try {
                $entry = Get-ItemProperty -LiteralPath $record.PSPath -ErrorAction SilentlyContinue
                if ($entry.DisplayName -match '^Python 3\.(1[1-9]|[2-9][0-9])') {
                    if ($entry.InstallLocation) {
                        Write-Output (Join-Path ([string]$entry.InstallLocation) 'python.exe')
                    }
                }
            } catch { }
        }
    }
}
function Find-Python([string]$Specified) {
    if ($Specified) {
        $result = Test-PythonCandidate $Specified @()
        if (-not $result) {
            Write-Host ('Specified Python failed the >=3.11 x64 execution test: ' + $Specified) -ForegroundColor Yellow
        }
        return $result
    }
    # Preferred path from the user's previously working installation.
    $paths = New-Object 'System.Collections.Generic.List[string]'
    $paths.Add('D:\Python\python.exe')
    foreach ($registered in @(Get-RegisteredPythonPaths)) {
        if ($registered) { $paths.Add(([string]$registered).Trim('"')) }
    }
    $launcher = Find-App 'py.exe' @(
        (Join-Path $env:WINDIR 'py.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'))
    if ($launcher) {
        # Some systems have several Python releases; prefer the project's known 3.12 environment.
        foreach ($selector in @('-3.12','-3.11','-3.13','-3.14','-3')) {
            $candidate = Test-PythonCandidate $launcher @($selector)
            if ($candidate) { return $candidate }
        }
        try {
            foreach ($line in @(& $launcher '-0p' 2>$null)) {
                $str = [string]$line
                if ($str -match '(?i)([a-z]:\\[^\r\n"]+?python(?:\d+)?\.exe)') {
                    $paths.Add($Matches[1].Trim())
                }
            }
        } catch { }
    }
    # Search all executable candidates on PATH, not just the first one.
    foreach ($name in @('python.exe','python3.exe')) {
        foreach ($found in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
            if ($found -and $found.Source -and $found.Source -notmatch '(?i)\\Microsoft\\WindowsApps\\') {
                $paths.Add([string]$found.Source)
            }
        }
    }
    foreach ($base in @($env:LOCALAPPDATA,$env:ProgramFiles,$env:ProgramW6432,$env:USERPROFILE)) {
        if (-not $base) { continue }
        foreach ($version in @('Python312','Python311','Python313','Python314','Python315','Python316')) {
            $paths.Add((Join-Path $base ('Programs\Python\' + $version + '\python.exe')))
            $paths.Add((Join-Path $base ($version + '\python.exe')))
        }
    }
    foreach ($base in @('C:\','D:\')) {
        foreach ($version in @('Python312','Python311','Python313','Python314')) {
            $paths.Add((Join-Path $base ($version + '\python.exe')))
        }
    }
    foreach ($path in ($paths | Select-Object -Unique)) {
        if (-not $path -or -not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $candidate = Test-PythonCandidate $path @()
        if ($candidate) { return $candidate }
    }
    return $null
}
function Show-PythonDiagnostics {
    Write-Host 'Python >=3.11 x64 was not found by launch test. Diagnostic commands:' -ForegroundColor Yellow
    foreach ($text in @('where.exe python','py -0p','Get-Command python -All')) {
        Write-Host ('  ' + $text)
    }
    $launcher = Find-App 'py.exe' @((Join-Path $env:WINDIR 'py.exe'))
    if ($launcher) {
        try {
            Write-Host ('py launcher: ' + $launcher)
            & $launcher '-0p'
        } catch { }
    }
    Write-Host ('D:\Python\python.exe exists: ' + (Test-Path -LiteralPath 'D:\Python\python.exe' -PathType Leaf))
    Write-Host 'If an interpreter works, rerun with -PythonPath "C:\full\path\to\python.exe".'
}
# IBS_BUILDER_V4_NODE_PROBE
# Use a single, argument-quoting-safe --version probe. Windows PowerShell 5.1
# can produce misleading results when piping the output of native `-p` commands.
# Inspect PE machine type directly rather than relying on a second JS expression.
function Test-NodeCandidate([string]$Exe, [switch]$Explain) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe -PathType Leaf)) {
        if ($Explain) { Write-Host ('Node executable not found: ' + $Exe) -ForegroundColor Yellow }
        return $null
    }
    $resolved = (Resolve-Path -LiteralPath $Exe).ProviderPath
    # Reading only the PE headers avoids running untrusted data to determine
    # whether the selected executable is genuinely an x64 Windows binary.
    $reader = $null
    try {
        $reader = [System.IO.BinaryReader]::new([System.IO.File]::OpenRead($resolved))
        $stream = $reader.BaseStream
        if ($stream.Length -lt 128 -or $reader.ReadUInt16() -ne 0x5A4D) { throw 'MZ header missing' }
        [void]$stream.Seek(0x3C, [System.IO.SeekOrigin]::Begin)
        $peOffset = $reader.ReadInt32()
        if ($peOffset -lt 0 -or ($peOffset + 6) -gt $stream.Length) { throw 'Invalid PE offset' }
        [void]$stream.Seek($peOffset, [System.IO.SeekOrigin]::Begin)
        if ($reader.ReadUInt32() -ne 0x00004550) { throw 'PE signature missing' }
        $machine = $reader.ReadUInt16()
        if ($machine -ne 0x8664) { 
            if ($Explain) { Write-Host ('Node binary has non-x64 PE machine: 0x{0:X4}' -f $machine) -ForegroundColor Yellow }
            return $null
        }
    } catch {
        if ($Explain) { Write-Host ('Node PE verification failed: ' + $_.Exception.Message) -ForegroundColor Yellow }
        return $null
    } finally {
        if ($reader) { $reader.Dispose() }
    }

    $proc = $null
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $resolved
        $psi.Arguments = '--version'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $proc = New-Object System.Diagnostics.Process
        $proc.StartInfo = $psi
        if (-not $proc.Start()) { throw 'Windows did not start node.exe' }
        if (-not $proc.WaitForExit(20000)) {
            try { $proc.Kill() } catch { }
            throw 'node.exe --version timed out after 20 seconds'
        }
        $exitCode = $proc.ExitCode
        $stdout = $proc.StandardOutput.ReadToEnd().Trim()
        $stderr = $proc.StandardError.ReadToEnd().Trim()
        if ($exitCode -ne 0) {
            if ($Explain) {
                Write-Host ('node.exe --version failed with exit code ' + $exitCode) -ForegroundColor Yellow
                if ($stderr) { Write-Host ('node stderr: ' + $stderr) }
                if ($stdout) { Write-Host ('node stdout: ' + $stdout) }
                if (-not $stderr -and -not $stdout) {
                    Write-Host 'No process output; check Windows Security, AppLocker and missing runtime DLL errors.'
                }
            }
            return $null
        }
        if ($stdout -notmatch '^v(\d+)\.(\d+)\.(\d+)$') {
            if ($Explain) { Write-Host ('Node returned an unexpected --version result: ' + $stdout) -ForegroundColor Yellow }
            return $null
        }
        $major = [int]$Matches[1]
        if ($major -lt 22) {
            if ($Explain) { Write-Host ('Node is older than 22: ' + $stdout) -ForegroundColor Yellow }
            return [pscustomobject]@{ Path=$resolved; Version=$stdout; Major=$major; Arch='x64'; Compatible=$false }
        }
        if ($Explain) { Write-Host ('Node execution successful: ' + $stdout + ' x64 (' + $resolved + ')') -ForegroundColor Green }
        return [pscustomobject]@{ Path=$resolved; Version=$stdout; Major=$major; Arch='x64'; Compatible=$true }
    } catch {
        if ($Explain) {
            Write-Host ('Windows could not execute node.exe: ' + $_.Exception.Message) -ForegroundColor Yellow
            Write-Host ('Checked executable: ' + $resolved)
        }
        return $null
    } finally {
        if ($proc) { $proc.Dispose() }
    }
}

function Get-NodeCandidatePaths([string]$Specified) {
    if ($Specified) { return @($Specified) }
    $paths = New-Object 'System.Collections.Generic.List[string]'
    # Search every PATH candidate, not just the first (which may be an older Node).
    foreach ($found in @(Get-Command 'node.exe' -CommandType Application -All -ErrorAction SilentlyContinue)) {
        if ($found -and $found.Source) { $paths.Add([string]$found.Source) }
    }
    foreach ($base in @($env:ProgramFiles, $env:ProgramW6432, $env:LOCALAPPDATA,
                        $env:APPDATA, $env:USERPROFILE, 'C:\Program Files', 'D:\')) {
        if (-not $base) { continue }
        foreach ($suffix in @('nodejs\node.exe','Programs\nodejs\node.exe','scoop\apps\nodejs\current\node.exe',
                             'scoop\apps\nodejs-lts\current\node.exe', 'AppData\Local\Volta\tools\image\node\22\node.exe')) {
            $paths.Add((Join-Path $base $suffix))
        }
    }
    # Avoid PowerShell 5.1 automatic read-only HOME variable (case-insensitive).
    foreach ($nodeEnvDirectory in @($env:NVM_HOME,$env:NVM_SYMLINK,$env:VOLTA_HOME,$env:FNM_MULTISHELL_PATH)) {
        if (-not $nodeEnvDirectory) { continue }
        $paths.Add((Join-Path $nodeEnvDirectory 'node.exe'))
        $paths.Add((Join-Path $nodeEnvDirectory 'bin\node.exe'))
    }
    # Windows installers often record Node's InstallLocation here.
    foreach ($root in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                       'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
                       'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
        if (-not (Test-Path $root)) { continue }
        foreach ($entry in @(Get-ChildItem -Path $root -ErrorAction SilentlyContinue)) {
            try {
                $record = Get-ItemProperty -LiteralPath $entry.PSPath -ErrorAction Stop
                if ($record.DisplayName -match '(?i)^Node\.js' -and $record.InstallLocation) {
                    $paths.Add((Join-Path ([string]$record.InstallLocation) 'node.exe'))
                }
            } catch { }
        }
    }
    return @($paths | Where-Object { $_ } | Select-Object -Unique)
}
function Find-Node([string]$Specified) {
    foreach ($path in @(Get-NodeCandidatePaths $Specified)) {
        $candidate = Test-NodeCandidate $path
        if ($candidate) {
            if ($candidate.Compatible) {
                Write-Host ('Compatible existing Node: ' + $candidate.Version + ' ' + $candidate.Arch + ' at ' + $candidate.Path)
                return $candidate
            }
            Write-Host ('Skipping incompatible Node: ' + $candidate.Version + ' ' + $candidate.Arch + ' at ' + $candidate.Path) -ForegroundColor Yellow
        }
    }
    return $null
}
function Get-PortableNode([string]$Root) {
    # Download an official verified ZIP into this *project only*. No MSI, winget upgrade,
    # system-wide PATH modification, registry changes or changes to existing Node installs.
    $toolsRoot = Join-Path $Root '.ibs-build-tools'
    $nodeRoot = Join-Path $toolsRoot 'node'
    $markerName = '.ibs-builder-portable-node.marker'
    $markerPath = Join-Path $nodeRoot $markerName
    $script:PortableNodeRoot = $nodeRoot
    $nodeExe = Join-Path $nodeRoot 'node.exe'
    if (Test-Path -LiteralPath $nodeExe -PathType Leaf) {
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
            throw ('Portable Node folder is not managed by this installer; refusing to overwrite: ' + $nodeRoot)
        }
        $reused = Test-NodeCandidate $nodeExe -Explain
        if ($reused -and $reused.Compatible) {
            Write-Host ('Reusing previous project-local Node: ' + $reused.Version + ' (' + $nodeExe + ')')
            $script:PortableNodeCreated = $true
            return $reused
        }
        throw ('Existing project-local Node is unusable. Run Cleanup-IBS-TemporaryApps.ps1 then retry: ' + $nodeRoot)
    }
    if (Test-Path -LiteralPath $nodeRoot -PathType Container) {
        throw ('Directory exists but no valid project-local Node executable was found. Refusing to replace user data: ' + $nodeRoot)
    }
    if ($NoAppInstall) {
        throw 'No compatible Node >=22 x64 found. -NoAppInstall prevents a temporary Node download. Pass -NodePath or rerun without -NoAppInstall.'
    }
    New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null
    $stage = Join-Path $script:WorkingFolder 'node-download'
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    # PowerShell 5.1 can default to obsolete TLS settings on some computers.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host 'Downloading a project-local official Node.js 22 Windows x64 ZIP (not a system app).' -ForegroundColor Yellow
    try {
        $releases = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json' -TimeoutSec 40
        $release = $releases | Where-Object {
            $_.version -match '^v22\.\d+\.\d+$' -and @($_.files) -contains 'win-x64-zip'
        } | Sort-Object { [version]($_.version.TrimStart('v')) } -Descending | Select-Object -First 1
        if (-not $release) { throw 'No official Node v22 Windows x64 ZIP release was listed.' }
        $versionText = [string]$release.version
        $archiveName = 'node-' + $versionText + '-win-x64.zip'
        $base = 'https://nodejs.org/dist/' + $versionText + '/'
        $manifest = (Invoke-WebRequest -Uri ($base + 'SHASUMS256.txt') -UseBasicParsing -TimeoutSec 40).Content
        $matchLine = @(([string]$manifest -split "`r?`n") | Where-Object {
            $_ -match ('(?i)^[0-9a-f]{64}\s+' + [regex]::Escape($archiveName) + '$')
        } | Select-Object -First 1)
        if ($matchLine.Count -ne 1) { throw ('Official SHA256 manifest did not contain ' + $archiveName) }
        $expected = [regex]::Match([string]$matchLine[0], '^[0-9a-fA-F]{64}').Value.ToLowerInvariant()
        $zipPath = Join-Path $stage $archiveName
        Write-Host ('Official Node package: ' + $archiveName)
        Invoke-WebRequest -Uri ($base + $archiveName) -OutFile $zipPath -UseBasicParsing -TimeoutSec 240
        $actual = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw 'Downloaded Node.js ZIP failed official SHA256 verification. No files will be installed.' }
        Write-Host 'Official SHA256 verified.' -ForegroundColor Green
        $unpacked = Join-Path $stage 'expanded'
        Expand-Archive -LiteralPath $zipPath -DestinationPath $unpacked -Force
        $extractedRoot = Join-Path $unpacked ('node-' + $versionText + '-win-x64')
        if (-not (Test-Path -LiteralPath (Join-Path $extractedRoot 'node.exe') -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $extractedRoot 'npm.cmd') -PathType Leaf)) {
            throw 'Verified ZIP did not contain expected Node and npm executables.'
        }
        $test = Test-NodeCandidate (Join-Path $extractedRoot 'node.exe') -Explain
        if (-not $test -or -not $test.Compatible) { throw 'Extracted Node.js failed the detailed x64/version/Windows execution check above. Review its diagnostic output before retrying.' }
        Move-Item -LiteralPath $extractedRoot -Destination $nodeRoot
        Set-Content -LiteralPath $markerPath -Encoding ASCII -Value ('IBS build-tool portable Node ' + $versionText)
        $script:PortableNodeCreated = $true
        Write-Host ('Portable Node ready: ' + $nodeExe) -ForegroundColor Green
        return (Test-NodeCandidate $nodeExe)
    } catch {
        throw ('Could not prepare official portable Node.js: ' + $_.Exception.Message + '. Existing Node.js installation was not changed; or pass -NodePath to use an existing compatible node.exe.')
    }
}
function Cleanup-PortableNode {
    if (-not $script:PortableNodeCreated -or -not $script:PortableNodeRoot) { return }
    $marker = Join-Path $script:PortableNodeRoot '.ibs-builder-portable-node.marker'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        Write-Warning ('Portable Node marker is missing; refusing to delete ' + $script:PortableNodeRoot)
        return
    }
    try {
        Remove-Item -LiteralPath $script:PortableNodeRoot -Recurse -Force -ErrorAction Stop
        Write-Host 'Removed project-local temporary Node.js; existing system Node unchanged.' -ForegroundColor Green
        $parent = Split-Path -Parent $script:PortableNodeRoot
        if ((Test-Path -LiteralPath $parent -PathType Container) -and
            @(Get-ChildItem -LiteralPath $parent -Force).Count -eq 0) {
            Remove-Item -LiteralPath $parent -Force
        }
    } catch { Write-Warning ('Could not remove temporary portable Node: ' + $_.Exception.Message) }
}
function Find-Winget {
    return (Find-App 'winget.exe' @((Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\winget.exe')))
}
function Test-WingetInstalled([string]$Exe, [string]$Id) {
    $output = @(& $Exe 'list' '--id' $Id '--exact' '--source' 'winget' '--accept-source-agreements' 2>&1)
    $code = $LASTEXITCODE
    # WinGet uses this documented exit code when the list query has zero matches.
    if ($code -eq -1978335212) { return $false } # 0x8A150014 (NO_APPLICATIONS_FOUND)
    if ($code -ne 0) { throw ('Unable to query installed package inventory for ' + $Id + ' (exit ' + $code + '). No automatic installation will be attempted.') }
    $escaped = [regex]::Escape($Id)
    foreach ($line in $output) {
        if ([string]$line -match ('\s' + $escaped + '\s+\S')) { return $true }
    }
    return $false
}
function Write-ToolState {
    if (-not $script:StateFile) { return }
    $data = [pscustomobject]@{
        created_at = (Get-Date).ToString('o')
        note = 'ONLY winget apps newly installed by this build. Review before manual cleanup.'
        winget_package_ids = @($script:AddedApps.ToArray())
    }
    $data | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $script:StateFile -Encoding UTF8
}
function Install-TemporaryWinGetApp([string]$Id) {
    if ($NoAppInstall) { throw ('Required tool is missing; auto-install disabled: ' + $Id) }
    $winget = Find-Winget
    if (-not $winget) { throw ('Required tool is missing (' + $Id + '), but winget is unavailable. Install the tool manually or provide its executable path.') }
    if (Test-WingetInstalled $winget $Id) {
        throw ('winget confirms ' + $Id + ' is already installed, but no compatible executable could be run. This installer will NOT reinstall or uninstall that existing app. Locate the executable using the diagnostics above; rerun with -PythonPath or -NodePath.')
    }
    Write-Host ('Installing TEMPORARY missing application: ' + $Id) -ForegroundColor Yellow
    Invoke-Checked $winget @('install','--id',$Id,'--exact','--source','winget',
        '--accept-source-agreements','--accept-package-agreements','--silent')
    # Inventory before install was empty. Record immediately so cleanup can be retried.
    $script:AddedApps.Add($Id)
    Write-ToolState
    Refresh-Path
}
function Assert-HostBuildScript([string]$Root) {
    $hostFile = Join-Path $Root 'scripts\build\Build-Host.ps1'
    $content = [IO.File]::ReadAllText($hostFile, [Text.Encoding]::UTF8)
    if (-not ($content.Contains('IBS_HOST_BUILD_PYTHON311PLUS_BUNDLE_V3') -and
              $content.Contains('function Test-CompatiblePython') -and
              $content.Contains('IBS_BUILD_PYTHON'))) {
        throw 'Build-Host.ps1 is not the integrated version in this package. Copy the complete installer files into the same project or use the bundled full-source edition.'
    }
    Write-Host 'Integrated Build-Host.ps1 verified: Python >=3.11; no source modification needed.' -ForegroundColor Green
}
function Prepare-Venv([string]$Root,[string]$PythonExe) {
    $venv = Join-Path $Root '.build-venv'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if (Test-Path -LiteralPath $venv -PathType Container) {
        $valid = $null
        if (Test-Path -LiteralPath $venvPython -PathType Leaf) { $valid = Test-PythonCandidate $venvPython @() }
        if (-not $valid) {
            $backup = Join-Path $Root ('.build-venv-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
            Write-Host ('Preserving incompatible/broken old venv at ' + $backup)
            Move-Item -LiteralPath $venv -Destination $backup
        }
    }
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Invoke-Checked $PythonExe @('-m','venv',$venv)
        $script:CreatedVenv = $true
    }
    # pytest is installed by Build-Host.ps1 only when the optional test files exist and tests are enabled.
}
function Prepare-Pnpm([string]$NodeExe) {
    $pnpm = Find-App 'pnpm.cmd' @((Join-Path $env:APPDATA 'npm\pnpm.cmd'))
    if ($pnpm) {
        try {
            $v = [string](& $pnpm --version 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $v -match '^10\.') {
                Write-Host ('Using existing pnpm ' + $v)
                return
            }
        } catch { }
    }
    $npm = Join-Path (Split-Path -Parent $NodeExe) 'npm.cmd'
    if (-not (Test-Path -LiteralPath $npm -PathType Leaf)) {
        throw ('npm.cmd was not found beside selected Node.js: ' + $NodeExe)
    }
    $prefix = Join-Path $script:WorkingFolder 'npm-tools'
    New-Item -ItemType Directory -Force -Path $prefix | Out-Null
    Write-Host 'Installing pnpm 10 LOCALLY in the temporary build folder; no global npm installation.'
    Invoke-Checked $npm @('install','--prefix',$prefix,'pnpm@10','--no-audit','--no-fund')
    $bin = Join-Path $prefix 'node_modules\.bin'
    $env:Path = $bin + ';' + $env:Path
    $local = Join-Path $bin 'pnpm.cmd'
    if (-not (Test-Path -LiteralPath $local -PathType Leaf)) { throw 'Temporary pnpm.cmd was not created.' }
    Write-Host ('Temporary pnpm: ' + $local)
}
function Test-Release([string]$Root,[string]$SelectedDiceMode) {
    $required = @('dist\Iron-Bottom-Sound-Host\app\IBSHost.exe',
        'dist\Iron-Bottom-Sound-Host\frontend\dist\index.html',
        'dist\Iron-Bottom-Sound-Host\backend\lan-saves',
        'dist\Iron-Bottom-Sound-Host\backend\reports',
        'dist\Iron-Bottom-Sound-Host\resources\originals\assets\images\岛屿.jpg',
        'dist\Iron-Bottom-Sound-Host\Start_Host.bat',
        'dist\Iron-Bottom-Sound-Host\Start-Host.ps1',
        'dist\IBS-Host-Windows-x64.zip',
        'dist\Iron-Bottom-Sound-Guest\Start_Guest.bat',
        'dist\IBS-Guest-Windows-x64.zip')
    if ($SelectedDiceMode -ne 'os_csprng') {
        $required += 'dist\Iron-Bottom-Sound-Host\app\ibs_cpu_rng.dll'
    }
    foreach ($file in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $file))) { throw ('Release file missing: ' + $file) }
    }
}

# IBS_BUILDER_V5_AUTOCLEANUP
# Only deletes known generated directories at the resolved source project root.
# Call this AFTER both builds and the release-file validation have succeeded.
function Remove-BuildTemporaryFolders([string]$Root, [switch]$PreservePortableNode) {
    $names = @('.build-venv', '.ibs-build-tools', '.pytest_cache', '.pytest-tmp', '__pycache__')
    $failed = New-Object 'System.Collections.Generic.List[string]'
    if (-not $Root -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
        Write-Warning 'Temporary cleanup skipped: project root is invalid.'
        return $false
    }
    $canonicalRoot = (Resolve-Path -LiteralPath $Root).ProviderPath
    foreach ($folderName in $names) {
        if ($PreservePortableNode -and $folderName -eq '.ibs-build-tools') {
            Write-Host ('Retained ' + $folderName + ' because -KeepInstalledApps was requested.') -ForegroundColor Yellow
            continue
        }
        $target = Join-Path $canonicalRoot $folderName
        if (-not (Test-Path -LiteralPath $target)) {
            Write-Host ('Already absent: ' + $folderName)
            continue
        }
        try {
            $entry = Get-Item -LiteralPath $target -Force -ErrorAction Stop
            if (-not $entry.PSIsContainer) {
                throw 'Expected a directory, found a file; refusing to delete.'
            }
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Directory is a link or junction; refusing to follow or remove it.'
            }
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $target) {
                throw 'Directory still exists after deletion attempt.'
            }
            Write-Host ('Removed build directory: ' + $folderName) -ForegroundColor Green
        } catch {
            $failed.Add($folderName)
            Write-Warning ('Could not remove ' + $folderName + ': ' + $_.Exception.Message)
        }
    }
    # IBS_ORGANIZED_RECURSIVE_PYCACHE_V1: remove nested Python caches only after successful build.
    # Never recurse into dist/build, venv, node_modules, symlinks or junctions.
    $skipFolders = @('dist', 'build', '.build-venv', 'node_modules', '.git', '.ibs-build-tools')
    $toScan = New-Object 'System.Collections.Generic.Stack[string]'
    $toScan.Push($canonicalRoot)
    while ($toScan.Count -gt 0) {
        $dir = $toScan.Pop()
        foreach ($sub in @(Get-ChildItem -LiteralPath $dir -Directory -Force -ErrorAction SilentlyContinue)) {
            if (($sub.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            if ($sub.Name -eq '__pycache__') {
                try {
                    Remove-Item -LiteralPath $sub.FullName -Recurse -Force -ErrorAction Stop
                    if (Test-Path -LiteralPath $sub.FullName) { throw 'Still exists' }
                    Write-Host ('Removed nested cache: ' + $sub.FullName) -ForegroundColor Green
                } catch {
                    $failed.Add($sub.FullName)
                    Write-Warning ('Could not remove nested cache ' + $sub.FullName + ': ' + $_.Exception.Message)
                }
            } elseif ($skipFolders -notcontains $sub.Name -and -not $sub.Name.StartsWith('.ibs-setup-temp-')) {
                $toScan.Push($sub.FullName)
            }
        }
    }
    if ($failed.Count -gt 0) {
        Write-Warning ('Build succeeded, but some temporary folders remain: ' + ($failed.ToArray() -join ', '))
    }
    return ($failed.Count -eq 0)
}

function Cleanup-NewApps {
    if ($script:AddedApps.Count -eq 0) { return $true }
    $winget = Find-Winget
    if (-not $winget) {
        Write-Warning 'winget unavailable: temporary installed apps cannot be auto-uninstalled.'
        return $false
    }
    $failed = New-Object 'System.Collections.Generic.List[string]'
    $reverse = @($script:AddedApps.ToArray())
    [array]::Reverse($reverse)
    foreach ($id in $reverse) {
        try {
            Write-Host ('Removing only the app installed THIS RUN: ' + $id) -ForegroundColor Yellow
            Invoke-Checked $winget @('uninstall','--id',$id,'--exact','--silent','--accept-source-agreements')
        } catch {
            Write-Warning ('Uninstall failed for ' + $id + ': ' + $_.Exception.Message)
            $failed.Add($id)
        }
    }
    $script:AddedApps.Clear()
    foreach ($item in $failed) { $script:AddedApps.Add($item) }
    Write-ToolState
    return ($script:AddedApps.Count -eq 0)
}

$project = $null
try {
    if (-not [Environment]::Is64BitOperatingSystem -or [IntPtr]::Size -ne 8) {
        throw 'Run this installer under 64-bit Windows PowerShell 5.1 on x64 Windows.'
    }
    $project = Resolve-ExistingProject $ProjectRoot
    Test-RequiredSource $project
    $script:LogFile = Join-Path $project ('IBS-build-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    $script:StateFile = Join-Path $project 'IBS-temporary-apps.json'
    if (Test-Path -LiteralPath $script:StateFile) {
        $prior = Get-Content -LiteralPath $script:StateFile -Raw | ConvertFrom-Json
        if (@($prior.winget_package_ids).Count -gt 0) {
            throw ('An earlier run has unremoved temporary apps in ' + $script:StateFile + '. Review and clean that list before rerunning, to avoid wrongly treating these apps as pre-existing.')
        }
    }
    Start-Transcript -Path $script:LogFile -ErrorAction Stop | Out-Null
    $script:Transcribing = $true
    Write-Host 'Iron Bottom Sound organized-source builder: build inside extracted folder' -ForegroundColor Green
    Write-Host ('Project root: ' + $project)
    Write-Host ('Build log: ' + $script:LogFile)
    Write-Host 'Existing Node will never be replaced. Missing compatible Node is downloaded as an official ZIP ONLY into this project.'
    Write-Host 'Missing Python may be installed via winget; newly installed apps will be removed after a successful build.'
    Write-Host 'EasyTier, Git, 7-Zip and already installed apps are never removed.'
    Write-Host 'pip/pnpm may download build dependencies; an internet connection may be required.'
    Refresh-Path
    $script:WorkingFolder = Join-Path $project ('.ibs-setup-temp-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $script:WorkingFolder | Out-Null

    Step '1/6 Checking existing Python >=3.11 and Node >=22 (x64)'
    $python = Find-Python $PythonPath
    if (-not $python) {
        Show-PythonDiagnostics
        if ($PythonPath) { throw ('Explicit -PythonPath is not a compatible Python >=3.11 x64: ' + $PythonPath) }
        Install-TemporaryWinGetApp 'Python.Python.3.12'
        $script:TemporaryPython = $true
        $python = Find-Python ''
        if (-not $python) { Show-PythonDiagnostics; throw 'New Python installation completed but no compatible executable could be run. Temporary app record is retained.' }
    }
    Write-Host ('Validated Python ' + $python.Version + ' x64: ' + $python.Path) -ForegroundColor Green

    $node = Find-Node $NodePath
    if (-not $node) {
        if ($NodePath) { throw ('Explicit -NodePath is not a compatible Node >=22 x64: ' + $NodePath) }
        Write-Host 'No compatible existing Node found. An older installed Node will be left untouched.' -ForegroundColor Yellow
        $node = Get-PortableNode $project
    }
    Write-Host ('Node.js ' + $node.Version + ': ' + $node.Path)
    $env:IBS_BUILD_PYTHON = $python.Path
    $env:Path = (Split-Path -Parent $node.Path) + ';' + $env:Path

    # IBS_BUILDER_V6_OPTIONAL_TESTS: tests are optional in trimmed source archives.
    # Never delete or recreate a tests directory; skip ONLY the test phase if files are absent.
    $requiredHostTestFiles = @('tests\test_lan_easytier_lobby.py', 'tests\test_lan_easytier_autofind.py')
    $missingHostTestFiles = New-Object 'System.Collections.Generic.List[string]'
    foreach ($testFile in $requiredHostTestFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $project $testFile) -PathType Leaf)) {
            $missingHostTestFiles.Add($testFile)
        }
    }
    $skipHostTestsEffective = [bool]$SkipTests
    if ($missingHostTestFiles.Count -gt 0) {
        $skipHostTestsEffective = $true
        Write-Warning ('Host tests SKIPPED: missing source file(s): ' + ($missingHostTestFiles.ToArray() -join ', '))
        Write-Warning 'The release may still build, but automated lobby/discovery tests were not run. Manually validate Host/Guest before distribution.'
    } elseif ($SkipTests) {
        Write-Host 'Host tests SKIPPED: -SkipTests was explicitly requested.' -ForegroundColor Yellow
    } else {
        Write-Host 'Host tests ENABLED: both required test files are present.' -ForegroundColor Green
    }

    Step '2/6 Preparing temporary pnpm and Python virtual environment'
    Prepare-Pnpm $node.Path
    Prepare-Venv $project $python.Path

    Step '3/6 Verifying the integrated Host build script (no temporary patching)'
    Assert-HostBuildScript $project

    Step '4/6 Building Host'
    $buildHostPath = Join-Path $project 'scripts\build\Build-Host.ps1'
    Push-Location $project
    try {
        if ($skipHostTestsEffective) { & $buildHostPath -DiceMode $DiceMode -SkipTests }
        else { & $buildHostPath -DiceMode $DiceMode }
    } finally { Pop-Location }

    Step '5/6 Building Guest'
    $buildGuestPath = Join-Path $project 'scripts\build\Build-Guest.ps1'
    Push-Location $project
    try { & $buildGuestPath } finally { Pop-Location }

    Step '6/6 Validating release files'
    Test-Release $project $DiceMode
    $script:BuildSucceeded = $true
    Write-Host 'Host and Guest release files exist.' -ForegroundColor Green
    Write-Host ('Host ZIP: ' + (Join-Path $project 'dist\IBS-Host-Windows-x64.zip'))
    Write-Host ('Guest ZIP: ' + (Join-Path $project 'dist\IBS-Guest-Windows-x64.zip'))
    Write-Host 'NOTE: Actual clean-PC execution, EasyTier peer discovery, sync, and save/load require manual tests.'
} catch {
    Write-Host ("`nINSTALL/BUILD FAILED: " + $_.Exception.Message) -ForegroundColor Red
    if ($script:LogFile) { Write-Host ('Log: ' + $script:LogFile) }
    if ($script:AddedApps.Count -gt 0) {
        Write-Warning ('Installed temporary apps were NOT auto-removed because build failed: ' + ($script:AddedApps.ToArray() -join ', '))
        Write-Warning 'Review IBS-temporary-apps.json and run Cleanup-IBS-TemporaryApps.ps1 to remove them manually, or retry after resolving the build error.'
    }
} finally {
    if ($script:BuildSucceeded -and -not $KeepInstalledApps) {
        # If we installed Python temporarily, the newly created venv would depend on it.
        if ($script:TemporaryPython -and $script:CreatedVenv -and $project) {
            try {
                Remove-Item -LiteralPath (Join-Path $project '.build-venv') -Recurse -Force
                Write-Host 'Removed the newly created venv that depended on temporary Python.'
            } catch { Write-Warning ('Failed to remove temporary-Python venv: ' + $_.Exception.Message) }
        }
        $clean = Cleanup-NewApps
        if ($clean) {
            if ($script:StateFile -and (Test-Path -LiteralPath $script:StateFile)) {
                Remove-Item -LiteralPath $script:StateFile -Force
            }
            Write-Host 'Temporary system applications successfully removed; pre-existing apps untouched.' -ForegroundColor Green
        } else {
            Write-Warning 'The build succeeded but not all new apps could be removed. See IBS-temporary-apps.json.'
        }
    }
    if ($script:BuildSucceeded -and -not $KeepInstalledApps) { Cleanup-PortableNode }
    if ($script:BuildSucceeded -and $KeepInstalledApps) {
        Write-Host 'KeepInstalledApps requested: newly installed apps and portable Node were retained.' -ForegroundColor Yellow
    }
    if (-not $script:BuildSucceeded -and $script:PortableNodeCreated) {
        Write-Host ('Build failed: project-local Node is retained for retry at ' + $script:PortableNodeRoot) -ForegroundColor Yellow
    }
    if ($script:BuildSucceeded -and $project) {
        Step 'Post-build: removing generated build folders'
        try {
            $script:BuildFolderCleanupSucceeded = Remove-BuildTemporaryFolders -Root $project -PreservePortableNode:$KeepInstalledApps
        } catch {
            $script:BuildFolderCleanupSucceeded = $false
            Write-Warning ('Unexpected error during post-build folder cleanup: ' + $_.Exception.Message)
        }
    }
    if ($script:WorkingFolder -and (Test-Path -LiteralPath $script:WorkingFolder)) {
        try { Remove-Item -LiteralPath $script:WorkingFolder -Recurse -Force }
        catch { Write-Warning ('Could not remove temporary build directory: ' + $_.Exception.Message) }
    }
    if ($script:Transcribing) { Stop-Transcript | Out-Null }
}
if (-not $script:BuildSucceeded) { exit 1 }
if ($script:BuildFolderCleanupSucceeded -eq $false) {
    Write-Warning 'Release files passed validation, but temporary-folder cleanup was incomplete. Review the build log.'
}
# IBS_BUILDER_V7_AUTOREMOVE_SUCCESS_LOG
# Stop-Transcript above must complete before attempting to remove the active log.
# Delete only THIS run's log on clean success. Keep logs from failed builds and
# incomplete cleanup; never delete historical IBS-build-*.log files in bulk.
if ($script:BuildFolderCleanupSucceeded -ne $false -and
    ($KeepInstalledApps -or $script:AddedApps.Count -eq 0) -and
    $script:LogFile -and (Test-Path -LiteralPath $script:LogFile -PathType Leaf)) {
    try {
        Remove-Item -LiteralPath $script:LogFile -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $script:LogFile) {
            throw 'Build log still exists after deletion attempt.'
        }
        Write-Host ('Removed successful-build log: ' + (Split-Path -Leaf $script:LogFile)) -ForegroundColor Green
    } catch {
        Write-Warning ('Build succeeded, but the build log could not be removed: ' + $_.Exception.Message)
    }
} elseif ($script:BuildFolderCleanupSucceeded -eq $false -or
          (-not $KeepInstalledApps -and $script:AddedApps.Count -gt 0)) {
    Write-Warning 'Build finished but cleanup was incomplete; keeping the build log for diagnosis.'
}
Write-Host ("`nBUILD FINISHED. Output is in " + (Join-Path $project 'dist')) -ForegroundColor Green
exit 0

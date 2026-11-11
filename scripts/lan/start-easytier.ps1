# EasyTier dual-player entry. Windows PowerShell 5.1+.
# Never reads, prints, embeds or copies network secrets.
[CmdletBinding()]
param(
    [ValidateSet('Host', 'NewRoom', 'Join')]
    [string]$Mode = 'Host',
    [string]$VpnIPv4 = '',
    [string]$AdapterName = '',
    [ValidateRange(1, 65535)] [int]$Port = 8765,
    [ValidateSet('cpu_rdseed', 'cpu_rdrand', 'os_csprng')]
    [string]$DiceMode = 'cpu_rdseed',
    [string]$Scenario = 'IBS-S-03',
    [string]$InviteUrl = '',
    [switch]$StartCore,
    [string]$EasyTierConfig = '',
    [string]$CoreExe = '',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))

function Test-IPv4([string]$Text) {
    $address = $null
    return ([Net.IPAddress]::TryParse($Text, [ref]$address) -and
        $address.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and
        -not $address.Equals([Net.IPAddress]::Parse('0.0.0.0')) -and
        -not $address.Equals([Net.IPAddress]::Parse('255.255.255.255')) -and
        -not $address.ToString().StartsWith('127.') -and
        -not $address.ToString().StartsWith('169.254.'))
}

function Get-EasyTierInterfaces {
    $adapters = @(Get-NetAdapter -IncludeHidden -ErrorAction Stop | Where-Object {
        $_.Status -eq 'Up' -and (
            ($AdapterName -and $_.Name -eq $AdapterName) -or
            (-not $AdapterName -and (($_.Name + ' ' + $_.InterfaceDescription) -match 'EasyTier'))
        )
    })
    foreach ($adapter in $adapters) {
        $addresses = @(Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue)
        foreach ($entry in $addresses) {
            if ((-not $entry.AddressState -or $entry.AddressState -eq 'Preferred') -and (Test-IPv4 $entry.IPAddress)) {
                [PSCustomObject]@{ Address = [string]$entry.IPAddress; Adapter = [string]$adapter.Name }
            }
        }
    }
}

function Resolve-EasyTierAddress {
    $candidates = @(Get-EasyTierInterfaces | Sort-Object Address -Unique)
    if ($VpnIPv4) {
        if (-not (Test-IPv4 $VpnIPv4)) { throw 'VpnIPv4 must be a valid non-loopback IPv4 address.' }
        $matches = @($candidates | Where-Object { $_.Address -eq $VpnIPv4 })
        if ($matches.Count -ne 1) {
            throw 'VpnIPv4 is not on the selected UP EasyTier adapter. Supply -AdapterName with its real Windows adapter name.'
        }
        return $VpnIPv4
    }
    if ($candidates.Count -ne 1) {
        Write-Host 'Detected adapter addresses:'
        $candidates | ForEach-Object { Write-Host ('  ' + $_.Adapter + ': ' + $_.Address) }
        throw 'Expected one EasyTier IPv4 address. Make sure EasyTier is connected. If Windows uses another adapter name, pass -AdapterName and optionally -VpnIPv4.'
    }
    return $candidates[0].Address
}

function Start-EasyTierIfRequested {
    if (-not $StartCore) { return }
    if ([string]::IsNullOrWhiteSpace($EasyTierConfig) -or -not (Test-Path -LiteralPath $EasyTierConfig -PathType Leaf)) {
        throw 'StartCore requires -EasyTierConfig pointing to a private local TOML (outside this Git repo).'
    }
    if (@(Get-EasyTierInterfaces).Count -gt 0) {
        Write-Host 'EasyTier interface already UP: reusing it; no second core process started.'
        return
    }
    $binary = $CoreExe
    if (-not $binary) {
        $command = Get-Command 'easytier-core.exe' -ErrorAction SilentlyContinue
        if ($command) { $binary = $command.Source }
    }
    if (-not $binary -or -not (Test-Path -LiteralPath $binary -PathType Leaf)) {
        throw 'Cannot find easytier-core.exe. Install EasyTier GUI or supply -CoreExe with its full path.'
    }
    # Only the path is passed; the private config content never goes to the command line.
    $quotedConfig = '"' + ([IO.Path]::GetFullPath($EasyTierConfig)) + '"'
    $process = Start-Process -FilePath $binary -ArgumentList @('-c', $quotedConfig) -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (@(Get-EasyTierInterfaces).Count -gt 0) { $ready = $true; break }
        $process.Refresh()
        if ($process.HasExited) { break }
    }
    if (-not $ready) { throw 'EasyTier did not create a usable virtual adapter. Check core logs, permissions, TUN driver and config.' }
}

if ($Mode -ne 'Join' -and -not (Test-Path -LiteralPath (Join-Path $root 'lan_server.py') -PathType Leaf)) {
    throw 'Game root not found (lan_server.py missing).'
}
Start-EasyTierIfRequested

if ($Mode -eq 'Join') {
    $ownIP = Resolve-EasyTierAddress
    Write-Host ('EasyTier online, local IP: ' + $ownIP)
    if (-not $InviteUrl) { $InviteUrl = Read-Host 'Paste the PRIVATE invitation URL from the host (http://VPN_IP:PORT/join#ticket)' }
    $target = $null
    if (-not [Uri]::TryCreate($InviteUrl, [UriKind]::Absolute, [ref]$target) -or
        $target.Scheme -ne 'http' -or $target.AbsolutePath -ne '/join' -or
        -not $target.Fragment -or -not (Test-IPv4 $target.Host)) {
        throw 'Invalid invitation. Ask the host for the full http://VPN_IP:PORT/join#ticket URL.'
    }
    Write-Host ('Checking host reachability at ' + $target.Host + ':' + $target.Port)
    if (-not (Test-NetConnection -ComputerName $target.Host -Port $target.Port -InformationLevel Quiet -WarningAction SilentlyContinue)) {
        throw 'Host TCP port is not reachable. Verify both VPN IPs, host server, Windows firewall and peer link.'
    }
    if (-not $NoBrowser) { Start-Process -FilePath $InviteUrl | Out-Null }
    Write-Host 'Invitation opened; credentials are not printed.'
    return
}

if (-not (Test-Path -LiteralPath (Join-Path $root 'frontend\dist\index.html') -PathType Leaf)) {
    throw 'frontend/dist/index.html missing. Run: cd frontend; pnpm.cmd install; pnpm.cmd run build'
}
if ($DiceMode -eq 'cpu_rdseed' -and -not (Test-Path -LiteralPath (Join-Path $root 'ibs_cpu_rng.dll') -PathType Leaf)) {
    throw 'ibs_cpu_rng.dll missing. RDSEED mode cannot silently fall back.'
}
$address = Resolve-EasyTierAddress
if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count -gt 0) {
    throw ('TCP port ' + $Port + ' is already listening. Stop the existing server first; do not open two rooms.')
}
foreach ($oldPort in @(8000, 5173)) {
    if (@(Get-NetTCPConnection -State Listen -LocalPort $oldPort -ErrorAction SilentlyContinue).Count -gt 0) {
        throw ('Standalone server on TCP ' + $oldPort + ' detected. Stop solo mode with scripts/stop-game.ps1 before hosting online.')
    }
}
$env:IBS_DICE_SOURCE = $DiceMode
$env:IBS_LAN_ADVERTISE_IP = $address
$serverArgs = @('lan_server.py', '--host', $address, '--port', [string]$Port)
if ($Mode -eq 'NewRoom') {
    Write-Warning 'Creating a NEW room rotates all invitation tickets. Saved games are not deleted.'
    $serverArgs += @('--new-room', '--scenario', $Scenario)
}
Write-Host ('Gateway binds ONLY EasyTier IP: http://' + $address + ':' + $Port)
Write-Host 'Two private invite URLs appear below after the server starts. Send each URL only to its player.'
Write-Host 'If remote TCP checks fail, allow inbound TCP on this VPN IP only (see docs/lan/EASYTIER.md).'
Push-Location $root
try {
    & python @serverArgs
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw ('lan_server.py exited: ' + $code) }
} finally {
    Pop-Location
}

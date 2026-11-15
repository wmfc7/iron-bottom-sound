[CmdletBinding()]
param([ValidateSet('cpu_rdseed','cpu_rdrand','os_csprng')][string]$DiceMode='cpu_rdseed')
$ErrorActionPreference='Stop'
$root=(Resolve-Path $PSScriptRoot).Path
$exe=Join-Path $root 'app\IBSHost.exe'
if(-not (Test-Path $exe)){throw 'IBSHost.exe is missing. Rebuild the Host package.'}
$adapters=@(Get-NetAdapter -IncludeHidden | Where-Object {$_.Status -eq 'Up' -and ((($_.Name+' '+$_.InterfaceDescription) -match '(?i)EasyTier') -or ($_.Name -match '(?i)^et[_-]'))})
$addresses=@(foreach($a in $adapters){Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.AddressState -eq 'Preferred' -and -not $_.IPAddress.StartsWith('127.')} })
if($addresses.Count -eq 0){throw 'No connected EasyTier IPv4 adapter found. Connect EasyTier first, then retry.'}
if($addresses.Count -gt 1){Write-Host 'Detected EasyTier addresses:';for($i=0;$i -lt $addresses.Count;$i++){Write-Host "[$($i+1)] $($addresses[$i].IPAddress)"};$n=0;if(-not [int]::TryParse((Read-Host 'Select address number'),[ref]$n) -or $n -lt 1 -or $n -gt $addresses.Count){throw 'Invalid adapter selection.'};$vpn=$addresses[$n-1]}else{$vpn=$addresses[0]}
$prefix=[int]$vpn.PrefixLength;if($prefix -gt 24){$prefix=24};if($prefix -lt 8){throw 'Unexpected EasyTier prefix length.'}
$env:IBS_ROOT=$root
$env:IBS_DB_PATH=(Join-Path $root 'backend\iron-bottom-sound.sqlite3')
$env:IBS_REPORTS_DIR=(Join-Path $root 'backend\reports')
$env:IBS_DICE_SOURCE=$DiceMode
$env:IBS_DICE_CPU_DLL=(Join-Path $root 'app\ibs_cpu_rng.dll')
$env:IBS_LAN_ADVERTISE_IP=$vpn.IPAddress
$env:IBS_LAN_AUTOFIND='1'
$env:IBS_LAN_AUTOFIND_CIDR="$($vpn.IPAddress)/$prefix"
if($DiceMode -in @('cpu_rdseed','cpu_rdrand') -and -not (Test-Path (Join-Path $root 'app\ibs_cpu_rng.dll'))){throw 'CPU RNG DLL is missing. Rebuild with MSVC or explicitly choose os_csprng.'}
$port=8765
if(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue){throw "TCP $port is already in use. Stop the other server first."}
Write-Host "Iron Bottom Sound Host starting on EasyTier $($vpn.IPAddress):$port"
Write-Host "Discovery subnet: $env:IBS_LAN_AUTOFIND_CIDR"
Write-Host 'The room file and SQLite database will be created locally; do not share them.'
$mode=Read-Host 'Enter 1 to resume the local room, or 2 to create a new room'
$serverArgs=@('--host',$vpn.IPAddress,'--port',[string]$port)
if($mode -eq '2'){$serverArgs+=@('--new-room') }elseif($mode -ne '1'){throw 'Invalid selection.'}
Push-Location $root
try { & $exe @serverArgs; if($LASTEXITCODE -ne 0){throw "IBSHost exited with code $LASTEXITCODE"} } finally { Pop-Location }

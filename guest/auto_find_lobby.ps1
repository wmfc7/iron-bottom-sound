# Windows PowerShell 5.1+: zero-room-information Iron Bottom Sound EasyTier discovery.
# Requires EasyTier already connected to the same trusted network as the host.
[CmdletBinding()]
param([ValidateRange(1,65535)][int]$Port=8765, [switch]$NoBrowser)
$ErrorActionPreference='Stop'

function IsIPv4([string]$text) {
    $addr = $null
    return ([Net.IPAddress]::TryParse($text, [ref]$addr) -and
       $addr.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork -and
       -not $addr.IsIPv6LinkLocal -and -not $addr.ToString().StartsWith('127.'))
}
function Test-IbsHost([string]$ip) {
    $req=$null; $res=$null; $reader=$null
    try {
        $req=[Net.HttpWebRequest]::Create(('http://{0}:{1}/lan/discovery' -f $ip,$Port))
        $req.Method='GET'; $req.Proxy=$null; $req.Timeout=1500; $req.ReadWriteTimeout=1500
        $res=$req.GetResponse()
        if ([int]$res.StatusCode -ne 200) { return $false }
        $reader=New-Object IO.StreamReader($res.GetResponseStream())
        $data=($reader.ReadToEnd() | ConvertFrom-Json)
        return ($data.service -eq 'iron-bottom-sound-easytier' -and $data.protocol -eq 1)
    } catch { return $false }
    finally {
        if($reader){$reader.Dispose()}
        if($res){$res.Dispose()}
    }
}
function Test-OpenPort([string]$ip) {
    $tcp=$null; $pending=$null
    try {
        $tcp=New-Object Net.Sockets.TcpClient
        $pending=$tcp.BeginConnect($ip,$Port,$null,$null)
        if(-not $pending.AsyncWaitHandle.WaitOne(950)) { return $false }
        $tcp.EndConnect($pending)
        return $true
    } catch { return $false }
    finally {
        if($pending){$pending.AsyncWaitHandle.Close()}
        if($tcp){$tcp.Dispose()}
    }
}
function Find-OpenPorts([string[]]$list) {
    # Concurrent TCP probes, 64 per batch. No UDP broadcast relay required.
    $result=New-Object 'System.Collections.Generic.List[string]'
    for($idx=0;$idx -lt $list.Count;$idx+=64) {
        $last=[Math]::Min($idx+64,$list.Count)
        $tasks=@()
        for($j=$idx;$j -lt $last;$j++) {
            $tcp=New-Object Net.Sockets.TcpClient
            try {
                $op=$tcp.BeginConnect($list[$j],$Port,$null,$null)
                $tasks+=,[PSCustomObject]@{IP=$list[$j];Tcp=$tcp;Handle=$op}
            } catch { $tcp.Dispose() }
        }
        foreach($t in $tasks){
            try {
                if($t.Handle.AsyncWaitHandle.WaitOne(900)) {
                    $t.Tcp.EndConnect($t.Handle)
                    [void]$result.Add([string]$t.IP)
                }
            } catch {}
            finally { $t.Handle.AsyncWaitHandle.Close();$t.Tcp.Dispose() }
        }
    }
    return $result.ToArray()
}

try {
    $nic=@(Get-NetAdapter -IncludeHidden -ErrorAction Stop | Where-Object {$_.Status -eq 'Up'})
    $vpn=@(foreach($n in $nic){
        if((($n.Name+' '+$n.InterfaceDescription) -match '(?i)EasyTier') -or ($n.Name -match '(?i)^et[_-]')) {
            Get-NetIPAddress -InterfaceIndex $n.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
              Where-Object { (IsIPv4 $_.IPAddress) -and ($_.AddressState -eq 'Preferred') }
        }
    })
    if($vpn.Count -eq 0) { throw '找不到已连接的 EasyTier 虚拟网卡。请先启动 EasyTier 并加入相同网络。' }
    $own=@($vpn | ForEach-Object {$_.IPAddress})
    Write-Host ('已连接 EasyTier：'+($own -join ', '))
    $known=New-Object 'System.Collections.Generic.HashSet[string]'

    # Prefer the EasyTier control plane: works even when peers span different /24s.
    $cli=Get-Command 'easytier-cli.exe' -ErrorAction SilentlyContinue
    if(-not $cli){$cli=Get-Command 'easytier-cli' -ErrorAction SilentlyContinue}
    $bin=$null
    if($cli){$bin=$cli.Source}
    foreach($candidate in @(
       (Join-Path $env:ProgramFiles 'EasyTier\easytier-cli.exe'),
       (Join-Path $env:LOCALAPPDATA 'EasyTier\easytier-cli.exe')
    )) {
       if(-not $bin -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {$bin=$candidate}
    }
    if($bin) {
       Write-Host '读取 EasyTier 在线节点……'
       try {
           $out=(& $bin -o json peer 2>$null) -join "`n"
           foreach($m in [regex]::Matches($out,'(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/[0-9]{1,2})?')) {
               $ip=($m.Value -split '/')[0]
               if((IsIPv4 $ip) -and ($own -notcontains $ip)) {[void]$known.Add($ip)}
           }
       } catch { Write-Host 'EasyTier CLI 不可用，自动改为虚拟网段探测。' }
    }
    $found=New-Object 'System.Collections.Generic.List[string]'
    # The host can use this same universal launcher, without sharing any URL.
    foreach($self in $own){if((Test-OpenPort $self) -and (Test-IbsHost $self)){[void]$found.Add($self)}}
    if($known.Count -gt 0 -and $found.Count -eq 0) {
        $active=@(Find-OpenPorts @($known))
        foreach($ip in $active){if(Test-IbsHost $ip){[void]$found.Add($ip)}}
    }
    if($found.Count -eq 0){
       # A /24 scan is a bounded fallback; never scan physical Wi-Fi/Ethernet ranges.
       $candidates=New-Object 'System.Collections.Generic.HashSet[string]'
       foreach($entry in $vpn) {
           $octets=$entry.IPAddress.Split('.')
           $stem='{0}.{1}.{2}.' -f $octets[0],$octets[1],$octets[2]
           for($i=1;$i -le 254;$i++) {
               $ip=$stem+$i
               if($own -notcontains $ip){[void]$candidates.Add($ip)}
           }
       }
       Write-Host ('正在扫描 EasyTier 虚拟网段，候选地址数：'+$candidates.Count)
       foreach($ip in (Find-OpenPorts @($candidates))){
           if(Test-IbsHost $ip){[void]$found.Add($ip)}
       }
    }
    if($found.Count -eq 0) { throw '未发现可加入的大厅。检查主机是否已启动新版网关、双方是否在同一 EasyTier 网段、主机 TCP 8765 防火墙是否放行。' }
    $unique=@($found | Sort-Object -Unique)
    $selected=$unique[0]
    if($unique.Count -gt 1){
       Write-Host '发现多个大厅，请选择：'
       for($i=0;$i -lt $unique.Count;$i++){Write-Host ('[{0}] {1}' -f ($i+1),$unique[$i])}
       $pick=Read-Host '输入编号'
       $number=0
       if(-not [int]::TryParse($pick,[ref]$number) -or $number -lt 1 -or $number -gt $unique.Count){throw '房间编号无效'}
       $selected=$unique[$number-1]
    }
    $url='http://{0}:{1}/lan/seat?autojoin=1' -f $selected,$Port
    Write-Host ('发现游戏大厅：'+$selected)
    if(-not $NoBrowser){Start-Process $url | Out-Null}
    Write-Host '已找到大厅。浏览器中选择空闲阵营即可，不需要邀请文件。'
} catch {
    Write-Host ('无法加入：'+$_.Exception.Message) -ForegroundColor Red
    exit 1
}

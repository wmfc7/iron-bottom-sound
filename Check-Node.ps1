#requires -Version 5.1
Write-Host 'Node.js diagnostic; does not install or modify anything.'
Write-Host 'PATH matches:'
where.exe node 2>$null
Write-Host 'All resolved Node candidates:'
Get-Command node.exe -All -CommandType Application -ErrorAction SilentlyContinue |
  ForEach-Object {
    $path = $_.Source
    try {
      $version = & $path --version
      $arch = & $path -p 'process.arch'
      Write-Host ($path + ' => ' + $version + ' / ' + $arch)
    } catch { Write-Host ($path + ' => failed: ' + $_.Exception.Message) }
  }

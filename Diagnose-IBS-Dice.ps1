# ASCII-only PowerShell 5.1 compatible diagnostic. Does not modify games or roll dice.
param([int]$Port = 8765)
$ErrorActionPreference = 'Continue'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = Join-Path (Get-Location).Path ('ibs-dice-diagnostic-' + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$log = Join-Path $outDir 'summary.txt'
function Log([string]$message) {
  Write-Host $message
  Add-Content -LiteralPath $log -Value $message -Encoding UTF8
}
Log ('Time: ' + (Get-Date -Format o))
Log ('PowerShell: ' + $PSVersionTable.PSVersion.ToString())
Log ('Port: ' + $Port)
$connections = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
if ($connections.Count -eq 0) {
  Log 'LISTEN: NONE. No process is listening at the specified port.'
} else {
  $serverProcessId = ($connections | Select-Object -First 1).OwningProcess
  Log ('LISTEN: YES; server PID=' + $serverProcessId)
  $proc = Get-Process -Id $serverProcessId -ErrorAction SilentlyContinue
  if ($proc) {
    Log ('PROCESS: ' + $proc.ProcessName + ' CPU=' + $proc.CPU + ' WorkingSetMB=' + [math]::Round($proc.WorkingSet64/1MB, 1))
  }
}
foreach ($endpoint in @('/join', '/lan/dice/health', '/lan/dice/state')) {
  $url = 'http://127.0.0.1:' + $Port + $endpoint
  Log ('REQUEST: ' + $endpoint)
  $answer = & curl.exe --noproxy '*' --max-time 5 --silent --show-error --output NUL --write-out 'HTTP=%{http_code} SECONDS=%{time_total}' $url 2>&1
  Log ('RESULT: ' + (($answer | Out-String).Trim()) + '; curl_exit=' + $LASTEXITCODE)
}
# A 401 from an unauthenticated dice endpoint proves the route responded.
if ($connections.Count -gt 0) {
  $pyspy = Get-Command py-spy.exe -ErrorAction SilentlyContinue
  if ($pyspy) {
    Log 'Trying py-spy thread snapshot (no locals or secret tokens).'
    $stackFile = Join-Path $outDir 'python-stacks.txt'
    & $pyspy.Source dump --pid $serverProcessId 2>&1 | Out-File -LiteralPath $stackFile -Encoding UTF8
    Log ('py-spy exit code: ' + $LASTEXITCODE)
  } else {
    Log 'py-spy not installed. Optional: python -m pip install py-spy'
  }
}
Log ('Diagnostic directory: ' + $outDir)
Log 'Do not share room tokens, cookie values, or logs with --locals without redaction.'

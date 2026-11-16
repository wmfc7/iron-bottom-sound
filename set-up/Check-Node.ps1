#requires -Version 5.1
Write-Host 'IBS Node diagnosis (read-only; no installations).'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = New-Object 'System.Collections.Generic.List[string]'
$portable = Join-Path $root '.ibs-build-tools\node\node.exe'
if (Test-Path -LiteralPath $portable) { $candidates.Add($portable) }
foreach ($item in @(Get-Command node.exe -All -CommandType Application -ErrorAction SilentlyContinue)) {
    if ($item.Source) { $candidates.Add([string]$item.Source) }
}
foreach ($path in @($candidates | Select-Object -Unique)) {
    Write-Host ('Checking: ' + $path)
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $path
        $psi.Arguments = '--version'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        try {
            if (-not $p.WaitForExit(20000)) { $p.Kill(); Write-Host 'Timed out'; continue }
            Write-Host ('Exit code: ' + $p.ExitCode)
            Write-Host ('stdout: ' + $p.StandardOutput.ReadToEnd().Trim())
            Write-Host ('stderr: ' + $p.StandardError.ReadToEnd().Trim())
        } finally { $p.Dispose() }
    } catch { Write-Host ('Launch error: ' + $_.Exception.Message) }
}
if ($candidates.Count -eq 0) { Write-Host 'No Node executable is available on PATH or the managed portable location.' }

[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out=Join-Path $root 'dist\Iron-Bottom-Sound-Guest'
if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path (Join-Path $out 'guest') | Out-Null
Copy-Item (Join-Path $root 'guest\auto_find_lobby.ps1') (Join-Path $out 'guest') -Force
@'
@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0guest\auto_find_lobby.ps1"
if errorlevel 1 (
  echo.
  echo Discovery failed. Connect EasyTier and try again.
  pause
)
'@ | Set-Content (Join-Path $out 'Start_Guest.bat') -Encoding ASCII
@'
Iron Bottom Sound Guest (Windows 10/11)

1. Install EasyTier and join the same trusted network as the host.
2. Run Start_Guest.bat.
3. The launcher searches the EasyTier peer list and, if necessary, the local EasyTier IPv4 subnet. It opens the discovered host lobby in your browser.

Requirements: Windows PowerShell 5.1 (included with Windows 10/11), active EasyTier virtual adapter, and a browser. easytier-cli is optional; without it, discovery uses a bounded /24 scan.

This package contains no host executable, game database, room ticket, invitation secret, EasyTier private configuration or personal save.
'@ | Set-Content (Join-Path $out 'README-Guest.txt') -Encoding UTF8
$zip=Join-Path $root 'dist\IBS-Guest-Windows-x64.zip'
New-Item -ItemType Directory -Force -Path (Split-Path $zip) | Out-Null
if(Test-Path $zip){Remove-Item $zip -Force}
Compress-Archive -Path (Join-Path $out '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Host "Guest package created: $zip"

# Windows Host / Guest distribution

The project now has two independent Windows x64 package builders:

- `scripts/build/Build-Host.ps1`: builds the Vite frontend, runs the LAN gateway tests, packages `lan_server.py` with PyInstaller, stages runtime resources and produces `dist/IBS-Host-Windows-x64.zip`.
- `scripts/build/Build-Guest.ps1`: stages only the PowerShell discovery client and its CMD launcher, producing `dist/IBS-Guest-Windows-x64.zip`.

## Build prerequisites

Host build: Windows 10/11 x64, Python 3.11, Node.js 22, pnpm 10, and PowerShell 5.1 or later. The default CPU dice modes use the supplied prebuilt Windows x64 `ibs_cpu_rng.dll`; Visual Studio / C++ Build Tools are not required. They are needed only if you explicitly request `-RebuildCpuRng` to compile a replacement DLL. The Host build uses PyInstaller `--onedir`; it does not require Python or Node.js on the receiving player's computer.

Guest build: Windows PowerShell 5.1 or later. Guest runtime needs EasyTier connected to the same trusted network as the Host. `easytier-cli` is optional; the existing discovery client falls back to bounded /24 probing on the EasyTier adapter.

## Build locally

Run from PowerShell (no Visual Studio or C++ Build Tools required when using the supplied DLL):

```powershell
./scripts/build/Build-Guest.ps1
./scripts/build/Build-Host.ps1 -DiceMode cpu_rdseed  # uses the supplied prebuilt x64 DLL
```

Only when rebuilding the native DLL after changing `ibs_cpu_rng.c`, use an MSVC x64 Native Tools prompt and add `-RebuildCpuRng`:

```powershell
./scripts/build/Build-Host.ps1 -DiceMode cpu_rdseed -RebuildCpuRng
```

For a host which intentionally uses the operating-system CSPRNG instead of the CPU instruction DLL:

```powershell
./scripts/build/Build-Host.ps1 -DiceMode os_csprng
```

The Host package creates its runtime state locally under `backend/`: SQLite database, room file, saves, reports and dice audit. These are deliberately not copied from the developer's checkout. Do not distribute those runtime files or private EasyTier TOML/key material.

## Runtime layout

`IBS_ROOT` selects the portable package root; `IBS_DB_PATH` and `IBS_REPORTS_DIR` point to writable runtime locations. The Host launcher sets these before starting the frozen executable. This keeps persistent state outside the PyInstaller application directory and lets the package be upgraded without overwriting saves.

The checked-in `ibs_cpu_rng.dll` is a prebuilt PE32+ AMD64 DLL and exports `ibs_cpu_rng_supported` / `ibs_cpu_rng_byte`; it imports only the Windows `KERNEL32.dll` system library. The builder verifies the PE machine field is AMD64 before staging it. This validates file format and architecture, not whether a particular host CPU exposes RDSEED/RDRAND; the DLL performs that runtime CPUID check.

The Host binds only to the selected EasyTier IPv4 address on TCP 8765. Windows Defender Firewall may need an inbound TCP 8765 rule scoped to the EasyTier adapter/network. Do not expose the service to the public Internet.

## Release automation

Pushing a tag matching `v*` runs `.github/workflows/release-windows.yml` on `windows-latest` and attaches both ZIP files to the GitHub Release. The workflow requires Git LFS checkout because some game resources are tracked through LFS.

## Validation limits

A successful package build does not prove that EasyTier peers can communicate across every network topology. Validate on two Windows PCs joined to the same private EasyTier network: start Host, confirm `http://HOST_EASYTIER_IP:8765/lan/discovery` returns the service metadata from Guest, then run `Start_Guest.bat` and claim a seat in the browser. Check firewall scope and ensure TCP 8765 is reachable only over the intended private network.

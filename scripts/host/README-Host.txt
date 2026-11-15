Iron Bottom Sound Host (Windows x64)

1. Install and connect EasyTier to your trusted private network.
2. Run Start_Host.bat.
3. Choose 1 to resume the room on this computer, or 2 to create a new room.
4. Keep this console open while hosting. Players on the same EasyTier network run the Guest launcher.

The package does not include personal room files, SQLite saves, audit logs, EasyTier credentials or private TOML files. The first run creates local data under backend\.

Default dice mode is cpu_rdseed. The CPU must support RDSEED. The package includes the supplied prebuilt Windows x64 ibs_cpu_rng.dll; players do not need Visual Studio or C++ Build Tools. To explicitly use the operating-system CSPRNG mode, run Start-Host.ps1 -DiceMode os_csprng.

Allow inbound TCP 8765 on the EasyTier virtual adapter in Windows Defender Firewall if Windows blocks remote players. Do not expose this service to the public Internet.

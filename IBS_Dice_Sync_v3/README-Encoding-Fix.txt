Windows PowerShell 5.1 compatible (ASCII-only) installer.

1. Put the IBS_Dice_Sync_v3 folder beside lan_server.py.
2. Stop LAN server and back up your saves.
3. In PowerShell, run:
   powershell -NoProfile -ExecutionPolicy Bypass -File .\IBS_Dice_Sync_v3\Install-Dice-Sync-v3.ps1
4. Restart server using CPU RDSEED and press Ctrl+F5 on both client browsers.
The script backs up lan_dice.py and lan_dice_client.js before changing them.

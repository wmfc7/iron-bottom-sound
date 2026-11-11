"""Safe, ASCII-only installer for the standalone LAN dice console.

Run from the repository root only while the 8765 server is stopped.
No databases, room records, or RNG DLLs are modified.
"""
from __future__ import annotations
import ast
import datetime
import shutil
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / 'lan_dice.py'
TARGET = ROOT / 'lan_dice.py'
SERVER = ROOT / 'lan_server.py'
CLIENT = ROOT / 'lan_dice_client.js'


def main():
    if not (SERVER.is_file() and TARGET.is_file() and CLIENT.is_file()):
        raise SystemExit('Missing lan_server.py, lan_dice.py, or lan_dice_client.js in repository root.')
    server = SERVER.read_text(encoding='utf-8')
    existing = TARGET.read_text(encoding='utf-8')
    replacement = SOURCE.read_text(encoding='utf-8')
    if 'from lan_dice import DiceBridge' not in server or '_dice_bridge.register(app, get_player, origin_ok)' not in server:
        raise SystemExit('LAN dice integration missing in lan_server.py; refusing to install.')
    if ('class DiceBridge:' not in existing or "@app.get('/lan/dice/health')" not in existing or
            "'protocol': 4" not in existing):
        raise SystemExit('Expected v4 lan_dice.py not found; refusing to overwrite an unknown version.')
    if 'no_blocking_game_polls' in existing:
        print('The unblock v5 patch appears to be installed already.')
        return
    with socket.socket() as sock:
        sock.settimeout(0.3)
        if sock.connect_ex(('127.0.0.1', 8765)) == 0:
            raise SystemExit('Server port 8765 is still active. Finish/backup current roll, then stop the server before installing.')
    ast.parse(replacement, filename=str(SOURCE))
    import py_compile
    py_compile.compile(str(SOURCE), doraise=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = ROOT / ('lan_dice.py.pre-unblock-v5-' + stamp + '.bak')
    shutil.copy2(TARGET, backup)
    try:
        shutil.copy2(SOURCE, TARGET)
        py_compile.compile(str(TARGET), doraise=True)
    except Exception:
        shutil.copy2(backup, TARGET)
        raise
    print('Dice unblock v5 installed. Backup:', backup)
    print('Start the LAN server using its existing cpu_rdseed configuration.')
    print('Each authorized player can use http://SERVER_IP:8765/lan/dice/standalone')

if __name__ == '__main__':
    main()

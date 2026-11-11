"""Install v6 dice privacy and gunnery report modifications atomically.

Run in the patch's folder under the repository root, with server stopped.
Does not read/write game saves, rooms, audit records or RNG DLL.
"""
from __future__ import annotations
import ast
import datetime as dt
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from patch_app_v6 import patch_app
from patch_gateway_v6 import patch_gateway


def main():
    server = ROOT / 'lan_server.py'
    dice = ROOT / 'lan_dice.py'
    client = ROOT / 'lan_dice_client.js'
    app = ROOT / 'frontend' / 'src' / 'App.tsx'
    files = (server, dice, client, app)
    for f in files:
        if not f.is_file():
            raise SystemExit(f'Missing required file: {f}')
    with socket.socket() as sock:
        sock.settimeout(.4)
        if sock.connect_ex(('127.0.0.1', 8765)) == 0:
            raise SystemExit('Port 8765 is active. Stop and back up the LAN server first.')
    original = {path: path.read_bytes() for path in files}
    server_src = original[server].decode('utf8')
    dice_src = original[dice].decode('utf8')
    app_src = original[app].decode('utf8')
    if 'no_blocking_game_polls' not in dice_src or 'class DiceBridge:' not in dice_src:
        raise SystemExit('v5 dice module not detected; do not overwrite an unknown version.')
    if "_dice_bridge.register(app, get_player, origin_ok)" not in server_src:
        raise SystemExit('Existing dice gateway integration is missing.')
    if '# IBS_LAN_GUNNERY_REPORT_CHECKPOINT_V6' in server_src:
        raise SystemExit('v6 server appears already installed. No files changed.')
    new_data = {
        server: patch_gateway(server_src).encode('utf8'),
        dice: (HERE / 'lan_dice.py').read_bytes(),
        client: (HERE / 'lan_dice_client.js').read_bytes(),
        app: patch_app(app_src).encode('utf8'),
    }
    ast.parse(new_data[server].decode('utf8'), filename=str(server))
    ast.parse(new_data[dice].decode('utf8'), filename=str(dice))
    # Validate JS before touching the original source.
    node = shutil.which('node')
    if node:
        subprocess.run([node, '--check', str(HERE / 'lan_dice_client.js')], check=True)
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = ROOT / ('ibs-dice-v6-backup-' + stamp)
    backup.mkdir(exist_ok=False)
    for path, data in original.items():
        stored = backup / path.relative_to(ROOT)
        stored.parent.mkdir(parents=True, exist_ok=True)
        stored.write_bytes(data)
    changed = []
    try:
        for path, data in new_data.items():
            temp = path.with_name(path.name + '.v6-installing.tmp')
            temp.write_bytes(data)
            temp.replace(path)
            changed.append(path)
    except Exception:
        for path in changed:
            path.write_bytes(original[path])
        raise
    print('Installed v6. Original files are in:', backup)
    print('Now run: cd frontend && pnpm.cmd run build && cd ..')
    print('Then start your existing CPU RDSEED LAN server.')

if __name__ == '__main__':
    main()

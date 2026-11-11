"""Atomic Windows-friendly installation of IBS LAN Dice Sync v4.
Source is ASCII-only so terminal script encoding cannot corrupt it.
Run from any directory: python IBS_Dice_Sync_v4/Install-Dice-Sync-v4.py
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
FILES = ('lan_dice.py', 'lan_dice_client.js')


def validate_files() -> None:
    if not (ROOT / 'lan_server.py').is_file():
        raise RuntimeError('lan_server.py not found in the parent game directory')
    server_text = (ROOT / 'lan_server.py').read_text(encoding='utf-8')
    if 'from lan_dice import DiceBridge' not in server_text:
        raise RuntimeError('LAN dice is not installed in lan_server.py. Refusing partial upgrade.')
    for name in FILES:
        if not (ROOT / name).is_file():
            raise RuntimeError(f'Existing game file not found: {name}')
        if not (PACKAGE / name).is_file():
            raise RuntimeError(f'Upgrade package file not found: {name}')
    ast.parse((PACKAGE / 'lan_dice.py').read_text(encoding='utf-8'))
    js_cmd = shutil.which('node') or shutil.which('node.exe')
    if js_cmd:
        check = subprocess.run([js_cmd, '--check', str(PACKAGE / 'lan_dice_client.js')],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        if check.returncode:
            raise RuntimeError('New JavaScript file fails syntax check: ' + (check.stderr or check.stdout))
    else:
        print('WARNING: Node not found. JavaScript syntax pre-check was skipped.')


def main() -> None:
    validate_files()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = ROOT / 'backups' / f'dice-sync-v4-{stamp}'
    backup.mkdir(parents=True, exist_ok=False)
    for name in FILES:
        shutil.copy2(ROOT / name, backup / name)
    print('BACKUP:', backup)
    changed = []
    try:
        for name in FILES:
            dest = ROOT / name
            staging = dest.with_name('.' + name + '.dice-v4-upgrade')
            shutil.copy2(PACKAGE / name, staging)
            os.replace(staging, dest)
            changed.append(name)
        # Verify byte-for-byte and Python syntax after installation.
        for name in FILES:
            if (ROOT / name).read_bytes() != (PACKAGE / name).read_bytes():
                raise RuntimeError('Post-install mismatch: ' + name)
        ast.parse((ROOT / 'lan_dice.py').read_text(encoding='utf-8'))
    except Exception:
        for name in changed:
            shutil.copy2(backup / name, ROOT / name)
        raise
    finally:
        for name in FILES:
            (ROOT / ('.' + name + '.dice-v4-upgrade')).unlink(missing_ok=True)
    print('IBS Dice Sync v4 installed successfully.')
    print('Restart server, then Ctrl+F5 on BOTH browsers.')
    print('Check: http://HOST-IP:8765/lan/dice/health  (authenticated browser)')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', str(exc), file=sys.stderr)
        raise SystemExit(1)

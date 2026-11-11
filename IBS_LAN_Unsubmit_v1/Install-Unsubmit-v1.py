"""Transactional installer. Python 3.11+; run from the repository root."""
from pathlib import Path
from datetime import datetime
import ast
import shutil
import subprocess
import sys

from patch_unsubmit import patch_server, patch_frontend


def main():
    root = Path(__file__).resolve().parent.parent
    if not (root / 'pyproject.toml').is_file():
        raise SystemExit('Extract package into the iron-bottom-sound repository root')
    paths = [root / 'lan_server.py', root / 'frontend/src/App.tsx']
    payloads = {}
    for p in paths:
        if not p.is_file():
            raise SystemExit(f'Missing required file: {p}')
        original = p.read_bytes()
        edited = (patch_server if p.name == 'lan_server.py' else patch_frontend)(original.decode('utf-8')).encode('utf-8')
        payloads[p] = (original, edited)
    ast.parse(payloads[paths[0]][1].decode('utf-8'))
    ast.parse((Path(__file__).parent / 'lan_unseal.py').read_text(encoding='utf-8'))
    changed = [p for p in paths if payloads[p][0] != payloads[p][1]]
    module = root / 'lan_unseal.py'
    module_original = module.read_bytes() if module.exists() else None
    module_new = (Path(__file__).parent / 'lan_unseal.py').read_bytes()
    if not changed and module_original == module_new:
        print('Already installed. No files changed.')
        return
    backup = root / ('ibs-unsubmit-v1-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(exist_ok=False)
    for p in paths:
        if p in changed:
            dst = backup / p.relative_to(root)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    if module_original is not None:
        shutil.copy2(module, backup / 'lan_unseal.py')
    try:
        for p in changed:
            p.write_bytes(payloads[p][1])
        module.write_bytes(module_new)
    except BaseException:
        for p in changed:
            p.write_bytes(payloads[p][0])
        if module_original is None:
            module.unlink(missing_ok=True)
        else:
            module.write_bytes(module_original)
        raise
    gitignore = root / '.gitignore'
    entry = '/backend/lan-unseal-checkpoint.json'
    existing = gitignore.read_text(encoding='utf-8') if gitignore.exists() else ''
    if entry not in existing.splitlines():
        gitignore.write_text(existing.rstrip() + '\n' + entry + '\n', encoding='utf-8')
    print('LAN UNSEAL v1 installed. Backups:', backup)
    print('Run: cd frontend && pnpm.cmd run build')
    print('Do NOT run installer while the LAN server is running.')


if __name__ == '__main__':
    main()

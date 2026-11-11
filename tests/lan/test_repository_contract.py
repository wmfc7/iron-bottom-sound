"""Non-invasive repository-layout checks; no game data or DLL is loaded."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]


def test_lan_runtime_entrypoints_remain_in_place():
    required = [
        'lan_server.py', 'lan_dice.py', 'lan_dice_client.js',
        'lan_unseal.py', 'lan_lobby.html', 'ibs_cpu_rng.c',
        'build_cpu_rng.bat', 'frontend/src/App.tsx',
    ]
    assert all((ROOT / rel).is_file() for rel in required)


def test_lan_python_sources_compile_without_importing():
    for name in ('lan_server.py', 'lan_dice.py', 'lan_unseal.py'):
        ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)


def test_new_docs_and_launcher_exist():
    assert (ROOT / 'docs/lan/README.md').is_file()
    assert (ROOT / 'scripts/lan/start-lan.ps1').is_file()

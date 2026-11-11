"""Install collapsible dice UI v2.1 for the existing IBS LAN Dice v2.

Only replaces the JavaScript client, leaves backend/engine/RDSEED untouched.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import shutil


def main() -> None:
    patch_dir = Path(__file__).resolve().parent
    root = patch_dir.parent
    source = patch_dir / 'lan_dice_client.js'
    target = root / 'lan_dice_client.js'
    if not (root / 'lan_server.py').is_file() or not (root / 'lan_dice.py').is_file():
        raise SystemExit('请把补丁文件夹放在游戏根目录下（与 lan_server.py、lan_dice.py 同级）。')
    if not target.is_file():
        raise SystemExit('找不到原版 lan_dice_client.js，请确认已经安装骰子 v2 补丁。')
    old = target.read_text(encoding='utf-8')
    new = source.read_text(encoding='utf-8')
    if 'ibs-dice-screen' not in old or '__ibsDiceAttached' not in old:
        raise SystemExit('当前骰子前端文件与预期不匹配；已停止，没有修改文件。')
    if 'ibs-dice-mini' not in new or 'ibs-dice-collapse' not in new:
        raise SystemExit('新版骰子脚本不完整，已停止。')
    if new == old:
        print('骰子 UI v2.1 已安装，无需重复操作。')
        return
    backup = root / f'lan_dice_client.js.before-collapse-{datetime.now():%Y%m%d-%H%M%S}.bak'
    if backup.exists():
        raise SystemExit(f'备份文件已存在：{backup}；请重新运行。')
    shutil.copy2(target, backup)
    target.write_text(new, encoding='utf-8')
    print('骰子 UI v2.1 安装完成。')
    print('已备份原脚本：', backup)
    print('此次仅修改前端 JS，不需要重新编译 CPU DLL、React 或修改数据库。')
    print('请重启 lan_server.py，并让双方浏览器 Ctrl+F5 强制刷新。')

if __name__ == '__main__':
    main()

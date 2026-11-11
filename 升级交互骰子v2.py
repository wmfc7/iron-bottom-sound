"""Install/upgrade LAN dice v2. Safe anchored edits; idempotent.

For an already-installed v1 this only changes LAN request completion:
orders return immediately while the server handles dice in a background coordinator.
Never modifies the upstream engine or player SQLite saves.
"""
from pathlib import Path
from datetime import datetime
import shutil

OLD_MARK = '# IBS_LAN_INTERACTIVE_DICE_V1'
NEW_MARK = '# IBS_LAN_INTERACTIVE_DICE_V2_ASYNC_SUBMIT'


def upgrade(source: str) -> str:
    if NEW_MARK in source:
        return source
    if OLD_MARK not in source:
        from install_online_dice import install
        source = install(source)
    if source.count('_dice_bridge.advance(call_engine') != 2:
        raise RuntimeError('找不到双推进调用锚点：请确认已安装上一版联机骰子补丁')
    if '<script src="/lan/dice/client.js" defer></script>' not in source:
        raise RuntimeError('未找到旧骰子脚本入口，拒绝修改')
    old = """            if res.status_code < 400:
                await settle_after_submit()"""
    if source.count(old) != 1:
        raise RuntimeError('旧提交阶段锚点数量不为1，拒绝修改：请提供 lan_server.py 以适配')
    new = """            if res.status_code < 400:
                # IBS_LAN_INTERACTIVE_DICE_V2_ASYNC_SUBMIT
                # Do NOT wait for a multi-roll battle in a browser's orders POST.
                # The coordinator acquires _guard after this request releases it.
                asyncio.create_task(reconcile_once())"""
    return source.replace(old, new)


def main():
    root = Path(__file__).resolve().parent
    gateway = root / 'lan_server.py'
    if not gateway.exists():
        raise SystemExit('请把补丁全部放到游戏根目录（必须存在 lan_server.py）')
    for f in ('lan_dice.py','lan_dice_client.js','ibs_cpu_rng.c','build_cpu_rng.bat'):
        if not (root / f).exists():
            raise SystemExit(f'缺少 {f}，请完整解压本补丁')
    original = gateway.read_text(encoding='utf-8')
    changed = upgrade(original)
    if changed == original:
        print('lan_server.py 已经是 v2；直接使用更新的 lan_dice.py/lan_dice_client.js。')
        return
    backup = root / ('lan_server.py.before-dice-v2-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.bak')
    shutil.copy2(gateway, backup)
    gateway.write_text(changed, encoding='utf-8')
    print('安装成功；服务器备份：', backup)
    print('请在 x64 Native Tools 命令提示符运行 build_cpu_rng.bat 生成本机专用 DLL。')

if __name__ == '__main__':
    main()

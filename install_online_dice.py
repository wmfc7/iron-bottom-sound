"""Idempotent installer for wmfc7/iron-bottom-sound `online` lan_server.py.

Run in game repo root: python install_online_dice.py
Writes backup and modifies only exact checked anchors. Does not modify engine.py.
"""
from pathlib import Path
import shutil
import sys

MARKER = '# IBS_LAN_INTERACTIVE_DICE_V1'


def install(text: str) -> str:
    if MARKER in text:
        return text

    def replace_once(old: str, new: str):
        nonlocal text
        found = text.count(old)
        if found != 1:
            raise RuntimeError(f'源码与 online 分支不匹配，预期唯一锚点却找到 {found} 处：{old[:85]!r}；未覆盖文件')
        text = text.replace(old, new)

    old = "async def call_engine(method: str, path: str, side: str | None = None, data: bytes | None = None, query: str = '') -> httpx.Response:"
    replace_once(old, f'''{MARKER}
from lan_dice import DiceBridge
_dice_bridge = DiceBridge(ROOT / 'backend' / 'lan-dice-audit.jsonl')
_dice_bridge.install(upstream_api.engine.__class__)
_dice_bridge.register(app, get_player, origin_ok)

{old}''')

    advance = '''result = await call_engine('POST', f'/games/{_room["game_id"]}/advance', 'axis')'''
    n = text.count(advance)
    if n != 2:
        raise RuntimeError(f'advance 锚点预期2处实际{n}处；拒绝改写')
    text = text.replace(advance, '''result = await _dice_bridge.advance(call_engine, f'/games/{_room["game_id"]}/advance')''')

    replace_once("html = html.replace('</body>', shortcut + '</body>')", "html = html.replace('</body>', shortcut + '<script src=\"/lan/dice/client.js\" defer></script></body>')")

    replace_once("timeout=90) as client:", "timeout=(None if method == 'POST' and path.endswith('/advance') else 90)) as client:")

    # Fail closed if dedicated external HRNG was requested but isn't available.
    # DiceBridge construction occurs at import and validates its configured source.
    return text


def main() -> None:
    target = Path('lan_server.py')
    if not target.is_file():
        sys.exit('请在源码根目录运行安装程序，根目录必须存在 lan_server.py')
    source = target.read_text(encoding='utf-8')
    output = install(source)
    if output == source:
        print('已安装此版本的联机骰子补丁，无需重复安装。')
        return
    for fn in ('lan_dice.py', 'lan_dice_client.js'):
        if not Path(fn).is_file():
            sys.exit(f'缺少 {fn}，请先将补丁全部解压到根目录')
    backup = target.with_name('lan_server.py.before-interactive-dice.bak')
    if backup.exists():
        sys.exit(f'备份已存在：{backup}。请人工核对，程序拒绝覆盖备份')
    shutil.copy2(target, backup)
    target.write_text(output, encoding='utf-8')
    print('已安装。备份:', backup)
    print('注意：必须明确配置随机数来源；默认严格 HRNG 模式要求硬件实时字节流。')


if __name__ == '__main__':
    main()

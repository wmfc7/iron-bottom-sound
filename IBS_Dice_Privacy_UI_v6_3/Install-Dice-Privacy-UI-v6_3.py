"""Incremental privacy/UI fix for the IBS LAN v6 dice bundle.

Only modifies lan_dice.py and lan_dice_client.js. No engine, room, save or RNG edits.
Fails closed on unknown versions and creates timestamped backups.
"""
from __future__ import annotations
import ast
import datetime
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / 'lan_dice.py'
CLIENT = ROOT / 'lan_dice_client.js'
MARK_PY = '# IBS_DICE_STRUCTURED_PRIVACY_V6_3'
MARK_JS = '/* IBS_DICE_MODAL_CONTROLS_V6_3 */'


def exact(source: str, old: str, new: str, label: str) -> str:
    n = source.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected exactly one source anchor, found {n}. No files changed.')
    return source.replace(old, new, 1)


def patch_backend(src: str) -> str:
    if MARK_PY in src:
        return src
    required = ("def _viewer_projection(", "def _context_from_frame(", "def request_roll(", "'_actors': actors, '_rule_private_side': table_private_side")
    if not all(r in src for r in required):
        raise RuntimeError('Expected dice v6 privacy functions not found. No files changed.')

    # Trusted engine objects, never browser-supplied roles, are the source of ship identities.
    needle = "    return {'owner': owner, 'reason': reason, 'detail': detail, 'rule': table,\n            '_actors': actors, '_rule_private_side': table_private_side}"
    repl = """    # IBS_DICE_STRUCTURED_PRIVACY_V6_3: preserve role / side mappings only in RAM.
    actor_roles = {}
    for role, candidate in (('attacker', attacker), ('target', target),
                            ('subject', owner_obj), ('ship', ship)):
        candidate_side = _side(candidate)
        if candidate_side in SIDES:
            actor_roles[role] = {'name': _ship_label(candidate), 'side': candidate_side}
    return {'owner': owner, 'reason': reason, 'detail': detail, 'rule': table,
            '_actors': actors, '_rule_private_side': table_private_side,
            '_actor_roles': actor_roles}"""
    src = exact(src, needle, repl, 'trusted actor role metadata')

    anchor = "                 'detail': context['detail'], 'rule': context['rule'],"
    replacement = """                 'detail': context['detail'], 'rule': context['rule'],
                 # Metadata remains server-only and is never returned verbatim.
                 '_actors': context.get('_actors', []),
                 '_actor_roles': context.get('_actor_roles', {}),
                 '_rule_private_side': context.get('_rule_private_side'),"""
    src = exact(src, anchor, replacement, 'pending roll metadata transfer')

    a = src.index('def _viewer_projection(')
    b = src.index('\n\nclass RandomSource:', a)
    new_projection = '''def _viewer_projection(p: dict, side: str) -> tuple[str, dict, bool]:
    """Construct the viewer's description from trusted, structured actor roles.

    Never send enemy ship names/IDs in any response field. Do not rely on client
    side masking. When actor metadata is unavailable, fail closed.
    """
    if side not in SIDES:
        raise ValueError('Unsupported viewer side')

    # These templates are authored here, not supplied by clients or by a
    # full-state detail string that might contain undiscovered secret names.
    templates = {
        '炮击命中判定': '{attacker} 舰炮击 {target} 舰 · 命中数判定',
        '炮击毁伤判定': '{target} 舰的炮击结果判定（攻击舰：{attacker}）',
        '鱼雷毁伤判定': '{target} 舰的鱼雷效果判定（发射舰：{attacker}）',
        '鱼雷命中判定': '{attacker} 舰鱼雷对 {target} 舰的接触命中检定',
        '火灾检定': '{subject} 舰的火灾持续及损伤判定',
        '特殊损伤判定': '{target} 舰的特殊损伤判定',
        '炮组故障判定': '{attacker} 舰的66故障判定',
        '照明弹判定': '{ship} 舰的照明弹检定',
        '碰撞损伤判定': '{ship} 舰的碰撞损伤判定',
        '碰撞发生判定': '{subject} 舰的碰撞检定',
        '随机受损炮组': '{ship} 舰的随机炮组毁伤判定',
    }
    reason = str(p.get('reason', '规则检定'))
    actors = p.get('_actor_roles')
    if isinstance(actors, dict) and actors:
        own = {}
        for role, actor in actors.items():
            if not isinstance(actor, dict) or actor.get('side') not in SIDES:
                own[role] = '***'
            else:
                own[role] = str(actor.get('name', '***'))[:96] if actor['side'] == side else '***'
        template = templates.get(reason)
        if template:
            # Only fixed internal templates are interpolated; unknown roles stay hidden.
            detail = template.format_map({role: own.get(role, '***') for role in
                                          ('attacker', 'target', 'subject', 'ship')})
        else:
            own_names = sorted({v for v in own.values() if v != '***'})
            detail = reason + ' · 本方舰船：' + ('、'.join(own_names) if own_names else '***')
            if any(v == '***' for v in own.values()):
                detail += '；其他舰船：***'
    else:
        # Older roll records may have names/sides but no structured role map.
        # Display only independently tagged friendly names, never the raw text.
        own_names = sorted({str(a.get('name', ''))[:96] for a in p.get('_actors', [])
                            if isinstance(a, dict) and a.get('side') == side and a.get('name')})
        detail = reason + ' · 本方舰船：' + ('、'.join(own_names) if own_names else '***')
        if any(isinstance(a, dict) and a.get('side') in SIDES and a.get('side') != side
               for a in p.get('_actors', [])):
            detail += '；其他舰船：***'

    rule = p.get('rule') or {}
    sensitive = p.get('_rule_private_side')
    # For known private rules without privacy metadata, hide rather than guess.
    require_private_metadata = reason in {
        '炮击命中判定', '鱼雷毁伤判定', '碰撞损伤判定', '特殊损伤判定',
        '鱼雷命中判定', '火灾检定', '炮组故障判定', '随机受损炮组'}
    private_missing = '_rule_private_side' not in p and require_private_metadata
    rule_hidden = private_missing or (sensitive in SIDES and sensitive != side)
    if rule_hidden:
        return detail, {'title': '对应规则表 · ***',
                        'note': '涉及未授权的舰船参数，已隐藏（***）',
                        'rows': [], 'kind': 'direct', 'modifier': 0, 'band': ''}, True
    return detail, {'title': str(rule.get('title', '相关规则')),
                    'note': str(rule.get('note', '')),
                    'rows': [dict(row) for row in rule.get('rows', [])],
                    'kind': rule.get('kind', 'direct'),
                    'modifier': rule.get('modifier', 0),
                    'band': rule.get('band', '')}, False
'''
    src = src[:a] + new_projection + src[b:]
    ast.parse(src)
    return src


def patch_client(src: str) -> str:
    if MARK_JS in src:
        return src
    if '#ibs-dice-restore' not in src or 'ibs-dice-toggle' not in src:
        raise RuntimeError('Expected dice v6 modal not found. No files changed.')
    src = exact(src,
        "#ibs-dice-screen {position:fixed;inset:0;z-index:2147483646;background:rgba(3,10,21,.93);display:none;align-items:center;justify-content:center;color:#f8f5e9;font-family:system-ui,\"Microsoft YaHei\",sans-serif;backdrop-filter:blur(6px)}",
        "#ibs-dice-screen {position:fixed;inset:0;z-index:2147483646;background:rgba(3,10,21,.93);display:none;align-items:flex-start;justify-content:center;padding:3vh 2vw;box-sizing:border-box;color:#f8f5e9;font-family:system-ui,\"Microsoft YaHei\",sans-serif;backdrop-filter:blur(6px)}",
        'centered modal root')
    src = exact(src,
        "#ibs-dice-screen.ibs-collapsed #ibs-dice-shell {display:none}",
        "#ibs-dice-screen.ibs-collapsed #ibs-dice-shell {height:0;min-height:0;max-height:none;overflow:visible;background:transparent;border:0;box-shadow:none;pointer-events:none}\n    #ibs-dice-screen.ibs-collapsed #ibs-dice-shell > :not(#ibs-dice-restore) {display:none}",
        'collapsed dialog behavior')
    src = exact(src,
        "#ibs-dice-restore {display:none;position:fixed;right:18px;top:16px;z-index:2147483647;pointer-events:auto;",
        "#ibs-dice-restore {display:none;position:absolute;right:14px;top:14px;z-index:1;pointer-events:auto;",
        'expand button modal positioning')
    src = exact(src,
        "#ibs-dice-toggle {position:absolute;right:18px;top:16px;",
        "#ibs-dice-toggle {position:absolute;right:14px;top:14px;z-index:1;",
        'collapse button modal positioning')
    src = exact(src,
        "#ibs-dice-shell {width:min(1080px,96vw);",
        "#ibs-dice-shell {position:relative;width:min(1080px,100%);",
        'modal shell anchor')
    src = exact(src,
        "#ibs-dice-banner {text-align:center;padding:22px 18px 8px;",
        "#ibs-dice-banner {position:relative;text-align:center;padding:22px 135px 8px;",
        'header positioning')
    src = exact(src,
        "@media(max-width:700px){#ibs-dice-shell",
        "@media(max-width:700px){#ibs-dice-banner{padding:54px 12px 8px}#ibs-dice-shell",
        'mobile header control protection')
    src = exact(src,
        "root.innerHTML = `<button id=\"ibs-dice-restore\" type=\"button\">展开投骰 · 等待判定</button><div id=\"ibs-dice-shell\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"ibs-dice-side\">",
        "root.innerHTML = `<div id=\"ibs-dice-shell\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"ibs-dice-side\"><button id=\"ibs-dice-restore\" type=\"button\">展开投骰 · 等待判定</button>",
        'move expand button inside dialog')
    src = src.replace('/* IBS LAN dice v4', MARK_JS + '\n/* IBS LAN dice v4', 1)
    return src


def main():
    for path in (BACKEND, CLIENT):
        if not path.is_file():
            raise SystemExit(f'Missing required file: {path}')
    with socket.socket() as probe:
        probe.settimeout(.3)
        if probe.connect_ex(('127.0.0.1', 8765)) == 0:
            raise SystemExit('Server port 8765 is active. Stop the LAN server before installing.')
    original = {p: p.read_bytes() for p in (BACKEND, CLIENT)}
    # Python text mode normalizes CRLF; ensure checks are performed on raw bytes.
    backend_text = original[BACKEND].decode('utf-8-sig').replace('\r\n', '\n')
    client_text = original[CLIENT].decode('utf-8-sig').replace('\r\n', '\n')
    if MARK_PY in backend_text and MARK_JS in client_text:
        print('Privacy/UI v6.3 already installed; no changes necessary.')
        return
    if MARK_PY in backend_text or MARK_JS in client_text:
        raise SystemExit('Partial v6.3 installation detected; refusing overwrite. Restore paired backups first.')
    changed = {
        BACKEND: patch_backend(backend_text).encode('utf-8'),
        CLIENT: patch_client(client_text).encode('utf-8'),
    }
    # Follow the existing original newline scheme for each file.
    for path in changed:
        if original[path].count(b'\r\n') > original[path].count(b'\n') // 2:
            changed[path] = changed[path].replace(b'\n', b'\r\n')
    if shutil.which('node'):
        # Test our exact JS contents, not the original file.
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            check_js = Path(temp_dir) / 'lan_dice_client.js'
            check_js.write_bytes(changed[CLIENT])
            subprocess.run(['node', '--check', str(check_js)], check=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_dir = ROOT / ('ibs-dice-privacy-ui-v6_3-backup-' + stamp)
    backup_dir.mkdir(exist_ok=False)
    for path, raw in original.items():
        (backup_dir / path.name).write_bytes(raw)
    completed = []
    try:
        for path, raw in changed.items():
            temp = path.with_name(path.name + '.v6_3.tmp')
            temp.write_bytes(raw)
            temp.replace(path)
            completed.append(path)
    except Exception:
        for path in completed:
            path.write_bytes(original[path])
        raise
    print('IBS Dice privacy / modal controls v6.3 installed successfully.')
    print('Backups:', backup_dir)
    print('Restart lan_server.py; hard-refresh BOTH browser tabs (Ctrl+F5).')
    print('No frontend build required.')


if __name__ == '__main__':
    main()

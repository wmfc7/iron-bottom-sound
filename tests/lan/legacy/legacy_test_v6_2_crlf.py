"""Regression tests for CRLF line endings in v6 gateway patching."""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'IBS_Dice_Gunnery_Privacy_v6'))
from patch_gateway_v6 import patch_gateway


def source_fixture():
    return '''from lan_dice import DiceBridge
_dice_bridge.register(app, get_player, origin_ok)
async def advance_until_order_phase() -> None:
    global _last_error
    pass
async def settle_after_submit() -> None:
    """Advance a sealed phase once. Caller must hold _guard."""
    global _last_error
    try:
        response = await observation()
        if response.get('phase') not in ORDER_PHASES or not response.get('both_orders_submitted', False):
            return
        before = f"回合{response.get('turn')} / {response.get('phase')}"
        print(f'[LAN DUEL] 双方封存 {before}，正在推进', flush=True)
        result = await _dice_bridge.advance(call_engine, f'/games/{_room["game_id"]}/advance')
        if result.status_code >= 400:
            print(f'[LAN DUEL] 原版引擎拒绝：HTTP {result.status_code} {result.text[:1000]}', flush=True)
            raise RuntimeError(f'规则引擎拒绝推进（HTTP {result.status_code}）')
        await advance_until_order_phase()
        after = await observation()
        print(f"[LAN DUEL] 推进成功：{before} → 回合{after.get('turn')} / {after.get('phase')}", flush=True)
        _last_error = ''
    except Exception as exc:
        _last_error = str(exc)
async def reconcile_once() -> None:
    global _last_error
    async with _guard:
        try:
            state = await observation()
        except Exception:
            pass
async def recovery_watchdog():
    pass
@app.get('/lan/control', response_class=HTMLResponse)
async def control():
    pass
'''


def check(source, ending):
    # Simulate the actual installer's source path: read_bytes().decode('utf8').
    read_from_bytes = source.encode('utf8').decode('utf8')
    patched = patch_gateway(read_from_bytes)
    ast.parse(patched)
    assert patched.count('# IBS_LAN_GUNNERY_REPORT_CHECKPOINT_V6') == 1
    assert "@app.get('/lan/gunnery/checkpoint')" in patched
    assert patch_gateway(patched) == patched
    if ending:
        assert patched.count('\r\n') == patched.count('\n')
    return patched


def test_lf():
    check(source_fixture(), False)


def test_crlf():
    check(source_fixture().replace('\n', '\r\n'), True)


def test_mixed_endings():
    s = source_fixture().replace('\n', '\r\n')
    s = s.replace('        await advance_until_order_phase()\r\n',
                  '        await advance_until_order_phase()\n')
    check(s, True)


def test_extra_diagnostics_between_calls():
    s = source_fixture().replace('        after = await observation()',
        '        print("extra logging")\n        after = await observation()')
    result = check(s.replace('\n', '\r\n'), True)
    assert 'extra logging' in result


def test_unknown_transition_still_rejected():
    s = source_fixture().replace('        await advance_until_order_phase()',
                                  '        await custom_advance()')
    try:
        patch_gateway(s.replace('\n', '\r\n'))
    except ValueError as e:
        assert 'after-gunnery transition' in str(e)
    else:
        raise AssertionError('Unknown transition must fail safely')


def test_idempotency_without_line_ending_conversion():
    text = source_fixture().replace('\n', '\r\n')
    result = patch_gateway(text)
    assert patch_gateway(result) == result

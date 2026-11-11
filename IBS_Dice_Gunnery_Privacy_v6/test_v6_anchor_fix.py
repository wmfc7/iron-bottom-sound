"""Portable tests for the v6.1 LAN gunnery gateway patch matcher."""
from __future__ import annotations

import ast
from patch_gateway_v6 import patch_gateway


def fixture_gateway() -> str:
    return '''from lan_dice import DiceBridge
_dice_bridge.register(app, get_player, origin_ok)
async def advance_until_order_phase():
    global _last_error
    for _ in range(24):
        pass
async def settle_after_submit():
    global _last_error
    response = await observation()
    result = await _dice_bridge.advance(call_engine, '/games/1/advance')
    if result.status_code >= 400:
        raise RuntimeError('advance failed')
    await advance_until_order_phase()
    after = await observation()
async def reconcile_once():
    global _last_error
    if not _room:
        return
    async with _guard:
        try:
            state = await observation()
        except Exception:
            pass
async def recovery_watchdog():
    pass
@app.get('/lan/control', response_class=HTMLResponse)
async def lan_control():
    pass
'''


def test_original_matching_layout():
    result = patch_gateway(fixture_gateway())
    assert result.count('# IBS_LAN_GUNNERY_REPORT_CHECKPOINT_V6') == 1
    assert "@app.post('/lan/gunnery/ack')" in result
    assert patch_gateway(result) == result
    ast.parse(result)


def test_allows_extra_code_between_advance_and_observe():
    source = fixture_gateway().replace(
        '    await advance_until_order_phase()\n    after = await observation()',
        '    await advance_until_order_phase()\n    print("custom diagnostic")\n    after = await observation()')
    result = patch_gateway(source)
    assert 'print("custom diagnostic")' in result
    assert result.index("if response.get('phase') == 'gunnery':") < result.index('    await advance_until_order_phase()')
    ast.parse(result)


def test_unknown_advance_structure_rejected():
    source = fixture_gateway().replace(
        '    await advance_until_order_phase()\n    after',
        '    await custom_stage_transition()\n    after')
    try:
        patch_gateway(source)
    except ValueError as exc:
        assert 'within settle_after_submit' in str(exc)
    else:
        raise AssertionError('Unrecognized stage transition must fail safely')

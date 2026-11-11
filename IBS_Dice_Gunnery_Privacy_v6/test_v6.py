import asyncio
import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from lan_dice import _context_from_frame, _viewer_projection, DiceBridge
from patch_gateway_v6 import patch_gateway
from patch_app_v6 import patch_app

class Rules:
    def gunnery_result(self, v):
        return {'hull': 1} if v==35 else {'kind':'no_effect'}
    def hit_count(self, fp, v):
        return fp % 3

class Ship:
    def __init__(self, name, side, ident):
        self.name = name; self.side = side; self.id = ident


def test_gunnery_damage_same_owner_as_hit():
    axis = Ship('青叶','axis','JPN-01')
    allies = Ship('旧金山','allies','USA-02')
    engine=SimpleNamespace(rules=Rules())
    # Use linecache to reproduce an engine call site named result_roll.
    frame=SimpleNamespace(f_code=SimpleNamespace(co_filename='/fake-engine-v6.py'), f_lineno=1)
    import linecache
    linecache.cache['/fake-engine-v6.py']=(0,None,['            result_roll, _ = self._roll_d66(state)\n'],'/fake-engine-v6.py')
    context=_context_from_frame('_resolve_gunnery', {'self':engine,'attacker':allies,'target':axis},frame,'D66',None)
    assert context['owner']=='allies'
    assert context['reason']=='炮击毁伤判定'
    a,r,hidden=_viewer_projection(context,'axis')
    assert '青叶' in a and '旧金山' not in a and '***' in a
    assert '炮击结果表' in r['title'] and not hidden
    a,r,hidden=_viewer_projection(context,'allies')
    assert '旧金山' in a and '青叶' not in a and '***' in a


def test_secret_rule_information_never_in_enemy_response():
    # Gun hit table GF is information about the FIRING side.
    p={'detail':'旧金山 炮击 青叶',
       '_actors':[{'name':'旧金山','side':'allies'},{'name':'青叶','side':'axis'}],
       '_rule_private_side':'allies',
       'rule':{'title':'炮击命中表 GF=37', 'note':'GF37 距离1',
               'rows':[{'key':'35','value':'12发'}], 'kind':'d66_step','modifier':4}}
    detail, rule, hidden=_viewer_projection(p,'axis')
    assert hidden is True
    assert '旧金山' not in detail and '青叶' in detail
    assert '37' not in str(rule) and '12发' not in str(rule)
    assert rule['rows']==[]
    detail2, rule2, hidden2=_viewer_projection(p,'allies')
    assert not hidden2 and '青叶' not in detail2 and rule2['rows']


def test_server_public_redacts_context_and_preserves_role(tmp_path):
    class FakeSource:
        mode='cpu_rdseed'
    b=DiceBridge(tmp_path/'audit.jsonl', source=FakeSource())
    b.current_started=0
    b.current={'id':'X', 'seq':1, 'notation':'D66','owner':'allies',
        'reason':'炮击毁伤判定','detail':'旧金山 炮击 青叶',
        'rule':{'title':'炮击毁伤表','note':'', 'rows':[{'key':'35','value':'舰艉损伤'}], 'kind':'direct','modifier':0},
        '_actors':[{'name':'旧金山','side':'allies'},{'name':'青叶','side':'axis'}],
        '_rule_private_side':None,
        'turn':1,'phase':'gunnery','status':'waiting','source':'cpu_rdseed',
        'animation_start_ms':None}
    viewed=b.public('axis')
    assert viewed['may_roll'] is False
    assert '旧金山' not in viewed['detail'] and '青叶' in viewed['detail']
    viewed=b.public('allies')
    assert viewed['may_roll'] is True
    assert '旧金山' in viewed['detail'] and '青叶' not in viewed['detail']
    assert '_actors' not in viewed


def test_gateway_checkpoint_anchored_changes():
    # Mimic the online branch with the patched dice integration.
    baseline='''from lan_dice import DiceBridge
_dice_bridge.register(app, get_player, origin_ok)
async def advance_until_order_phase():
    global _last_error
    for _ in range(24): pass
async def settle_after_submit():
    response = await observation()
    if response.get('phase') not in ORDER_PHASES:
        return
    result = await call_engine('POST','/games/1/advance')
    if result.status_code >= 400:
        raise RuntimeError('x')
        await advance_until_order_phase()
        after = await observation()
async def reconcile_once():
    global _last_error
    if not _room: return
    async with _guard:
        try:
            state = await observation()
        except Exception: pass
async def recovery_watchdog(): pass
@app.get('/lan/control', response_class=HTMLResponse)
async def control(): pass
'''
    res=patch_gateway(baseline)
    assert "if response.get('phase') == 'gunnery':" in res
    assert "@app.get('/lan/gunnery/checkpoint')" in res
    assert "@app.post('/lan/gunnery/ack')" in res
    assert "if _room.get('gunnery_checkpoint')" in res
    assert patch_gateway(res)==res
    ast.parse(res)


def test_app_uses_original_modal_and_retries_checkpoint():
    source='''import { useEffect, useMemo, useState } from "react";
const LAN_MODE = true;
function GunneryOutcomeModal(){}
function App() {
  const llmConfig: LLMConnectionConfig = {};
  return <div>{gunneryOutcome && <GunneryOutcomeModal onClose={() => setGunneryOutcome(null)} />}{gunneryOutcome && <GunneryOutcomeModal onClose={() => setGunneryOutcome(null)} />}</div>
}
'''
    patched=patch_app(source)
    assert 'IBS_LAN_GUNNERY_OUTCOME_V6' in patched
    assert '/lan/gunnery/checkpoint' in patched
    assert 'gameEvents(game, side, 0)' in patched
    assert patched.count('onClose={() => { void closeGunneryOutcome(); }}') == 2
    assert patch_app(patched)==patched

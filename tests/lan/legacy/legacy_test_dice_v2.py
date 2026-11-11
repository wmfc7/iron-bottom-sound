import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lan_dice import DiceBridge, _effective, _rule, RandomSource
from 升级交互骰子v2 import upgrade


class FixedSource:
    mode = 'cpu_rdseed'
    def dice(self, n):
        return [3] if n == 1 else [3, 5]


class Rules:
    def hit_count(self, firepower, roll): return 1 if roll <= 31 else 0
    def gunnery_result(self, roll): return {'hull': 1} if roll != 66 else 'miss'
    def special_damage_result(self, roll, band): return {'hull': 2}
    def torpedo_effect(self, roll, band): return '1H'
    fire_table = {'modifiers': {'ship_did_not_fire': 1, 'ignore_results_if_ship_did_not_fire': [7, 12]}}
    fire_results = {i: {'hull': 1} for i in range(2, 13)}
    malfunction_results = {i: {'hull': 1} for i in range(2, 13)}
    def table_2d6(self, table, roll): return table[roll]


class Engine:
    def __init__(self): self.rules = Rules()
    def _roll_d6(self, state): return 1, 1
    def _roll_2d6(self, state): return 2, [1, 1]
    def _roll_d66(self, state): return 11, [1, 1]
    def _resolve_gunnery(self, state):
        attacker, target = state.ships['A'], state.ships['B']
        modifier, firepower = 1, 10
        raw, dice = self._roll_d66(state)  # attacker (axis)
        result_roll, result_dice = self._roll_d66(state)  # defender (allies)
        return (raw, dice), (result_roll, result_dice)


def make_state():
    return SimpleNamespace(
        turn=2, phase=SimpleNamespace(value='gunnery'), rng_counter=0, game_id='dummy',
        ships={
            'A': SimpleNamespace(name='攻击舰', side=SimpleNamespace(value='axis'), displacement_band='C'),
            'B': SimpleNamespace(name='防御舰', side=SimpleNamespace(value='allies'), displacement_band='D'),
        },
    )


async def wait_for(bridge, side, status='waiting', seq=None):
    for _ in range(500):
        await asyncio.sleep(.003)
        info = bridge.public(side)
        if info['status'] == status and (seq is None or info.get('seq') == seq):
            return info
    raise AssertionError(f'timeout waiting for {status}/{seq}; saw {bridge.public(side)}')


@pytest.mark.asyncio
async def test_owner_handoff_and_rule_highlight(tmp_path):
    bridge = DiceBridge(tmp_path/'dice.jsonl', FixedSource(), animation_seconds=.02, hold_seconds=.02)
    bridge.install(Engine)
    engine, state = Engine(), make_state()
    async def handler(*_): return engine._resolve_gunnery(state)
    task = asyncio.create_task(bridge.advance(handler, '/games/dummy/advance'))
    first = await wait_for(bridge, 'axis', seq=1)
    assert first['owner'] == 'axis' and first['may_roll']
    assert '攻击舰' in first['detail']
    assert '炮击命中表' in first['rule']['title'] and len(first['rule']['rows']) == 36
    with pytest.raises(HTTPException) as e:
        bridge.roll('allies', first['id'])
    assert e.value.status_code == 403
    bridge.roll('axis', first['id'])
    with pytest.raises(HTTPException) as e:
        bridge.roll('axis', first['id'])
    assert e.value.status_code == 409
    shown = await wait_for(bridge, 'allies', 'revealed', seq=1)
    assert shown['raw'] == 35
    assert shown['adjusted'] == 36  # base-6 step 35 +1 => 36
    assert shown['outcome'] == '0 发'
    second = await wait_for(bridge, 'allies', seq=2)
    assert second['owner'] == 'allies' and second['may_roll']
    assert not bridge.public('axis')['may_roll']
    assert '防御舰' in second['detail'] and '炮击结果表' in second['rule']['title']
    bridge.roll('allies', second['id'])
    a,b = await asyncio.wait_for(task, 3)
    assert a == (35, [3,5]) and b == (35, [3,5])
    assert state.rng_counter == 2
    events = [json.loads(t) for t in (tmp_path/'dice.jsonl').read_text(encoding='utf8').splitlines()]
    assert [v['owner'] for v in events] == ['axis','allies']
    assert all(v['source'] == 'cpu_rdseed' for v in events)


@pytest.mark.asyncio
async def test_disconnect_does_not_drop_pending_roll(tmp_path):
    class E:
        def _roll_d6(self, state): return 1,1
        def _roll_2d6(self, state): return 2,[1,1]
        def _roll_d66(self, state): return 11,[1,1]
        def _move_squalls(self, state): return self._roll_d6(state)
    e, s = E(), make_state()
    bridge=DiceBridge(tmp_path/'audit.jsonl', FixedSource(), animation_seconds=.01, hold_seconds=.01)
    bridge.install(E)
    async def handler(*_): return e._move_squalls(s)
    req = asyncio.create_task(bridge.advance(handler, '/games/dummy/advance'))
    pending=await wait_for(bridge,'axis')
    assert pending['owner']=='axis'
    req.cancel()
    with pytest.raises(asyncio.CancelledError): await req
    assert bridge.busy
    assert bridge.public('axis')['id']==pending['id']
    bridge.roll('axis',pending['id'])
    for _ in range(500):
        await asyncio.sleep(.005)
        if not bridge.busy: break
    assert not bridge.busy
    assert json.loads((tmp_path/'audit.jsonl').read_text().splitlines()[0])['raw']==3


def test_dice_math_and_fail_closed():
    assert _effective(35,'D66',_rule([], 'hit', kind='d66_step', modifier=1)) == 36
    assert _effective(66,'D66',_rule([], 'hit', kind='d66_step', modifier=10)) == 66
    assert _effective(10,'2D6',_rule([], 'fire',kind='cap12',modifier=4)) == 12
    assert _effective(4,'2D6',_rule([], 'torpedo',kind='clamp2d6',modifier=-5)) == 2
    assert _effective(10,'2D6',_rule([], 'hit',kind='add',modifier=5)) == 15
    assert len(RandomSource('os_csprng').dice(2)) == 2
    with pytest.raises(RuntimeError, match='IBS_DICE_SOURCE'):
        RandomSource('not-a-real-mode')


def test_installer_matches_saved_online_snapshot():
    path = ROOT / 'lan_server.py'
    if not path.is_file():
        pytest.skip('test requires game root lan_server.py')
    text = path.read_text(encoding='utf-8')
    modified = upgrade(text)
    assert 'IBS_LAN_INTERACTIVE_DICE_V2_ASYNC_SUBMIT' in modified
    assert modified.count('_dice_bridge.advance(call_engine') == 2
    assert 'asyncio.create_task(reconcile_once())' in modified
    assert upgrade(modified) == modified
    from install_online_dice import install
    v1 = install(text)
    assert upgrade(v1) == modified

@pytest.mark.asyncio
async def test_actual_fastapi_sync_route_passes_context_and_switches_owner(tmp_path):
    import httpx
    from fastapi import FastAPI
    state=make_state()
    class E2:
        __init__ = Engine.__init__
        _resolve_gunnery = Engine._resolve_gunnery
        def _roll_d6(self,state): return 1,1
        def _roll_2d6(self,state): return 2,[1,1]
        def _roll_d66(self,state): return 11,[1,1]
    engine=E2()
    bridge=DiceBridge(tmp_path/'fastapi.jsonl', FixedSource(), animation_seconds=.01, hold_seconds=.01)
    bridge.install(E2)
    app=FastAPI()
    @app.post('/advance')
    def engine_handler():
        # FastAPI sync handler runs in AnyIO threadpool and must inherit ACTIVE_DICE.
        (raw,_), (damage,_) = engine._resolve_gunnery(state)
        return {'raw':raw,'damage':damage}
    async def upstream(method, path, side):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local') as c:
            return await c.post('/advance')
    task=asyncio.create_task(bridge.advance(upstream,'/games/dummy/advance'))
    a=await wait_for(bridge,'axis',seq=1)
    bridge.roll('axis',a['id'])
    b=await wait_for(bridge,'allies',seq=2)
    bridge.roll('allies',b['id'])
    r=await asyncio.wait_for(task,2)
    assert r.status_code==200 and r.json()=={'raw':35,'damage':35}
    assert state.rng_counter==2

@pytest.mark.asyncio
async def test_torpedo_hit_then_damage_handover(tmp_path):
    class TorpedoEngine:
        def __init__(self): self.rules = Rules()
        def _roll_d6(self,s): return 1,1
        def _roll_2d6(self,s): return 2,[1,1]
        def _roll_d66(self,s): return 11,[1,1]
        def _torpedo_modifier(self, state, attacker, target, distance): return 2
        def _resolve_torpedoes(self, state):
            attacker, target = state.ships['A'], state.ships['B']
            definition = {'damage_modifier': 1}
            distance, contact_target = 4, target
            roll, dice = self._roll_2d6(state)
            raw_damage_roll, damage_dice = self._roll_2d6(state)
            return roll, raw_damage_roll
    state=make_state(); eng=TorpedoEngine()
    bridge=DiceBridge(tmp_path/'torpedo.jsonl', FixedSource(), animation_seconds=.01, hold_seconds=.01)
    bridge.install(TorpedoEngine)
    async def upstream(*_): return eng._resolve_torpedoes(state)
    task=asyncio.create_task(bridge.advance(upstream,'/advance'))
    hit=await wait_for(bridge,'axis',seq=1)
    assert hit['owner']=='axis' and hit['reason']=='鱼雷命中判定'
    assert hit['rule']['modifier']==2
    bridge.roll('axis',hit['id'])
    damage=await wait_for(bridge,'allies',seq=2)
    assert damage['owner']=='allies' and damage['reason']=='鱼雷毁伤判定'
    assert damage['rule']['modifier']==1 and '排水量级 D' in damage['rule']['title']
    bridge.roll('allies',damage['id'])
    assert await asyncio.wait_for(task,2)==(8,8)


@pytest.mark.asyncio
async def test_fire_table_owner_and_rule_highlight(tmp_path):
    class FireEngine:
        def __init__(self): self.rules=Rules()
        def _roll_d6(self,s):return 1,1
        def _roll_2d6(self,s):return 2,[1,1]
        def _roll_d66(self,s):return 11,[1,1]
        def _resolve_fire(self,state):
            for ship in [state.ships['B']]:
                raw,dice=self._roll_2d6(state)
                return raw
    state=make_state();state.ships['B'].fired=False
    eng=FireEngine();bridge=DiceBridge(tmp_path/'fire.jsonl',FixedSource(),animation_seconds=.01,hold_seconds=.01)
    bridge.install(FireEngine)
    async def upstream(*_):return eng._resolve_fire(state)
    task=asyncio.create_task(bridge.advance(upstream,'/advance'))
    info=await wait_for(bridge,'allies',seq=1)
    assert info['owner']=='allies' and info['reason']=='火灾检定'
    assert info['rule']['modifier']==1
    bridge.roll('allies',info['id'])
    displayed=await wait_for(bridge,'allies','revealed',seq=1)
    assert displayed['raw']==8 and displayed['adjusted']==9
    assert displayed['outcome']=='船体：1'
    assert await asyncio.wait_for(task,2)==8

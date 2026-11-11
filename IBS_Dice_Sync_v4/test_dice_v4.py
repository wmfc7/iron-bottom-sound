"""Focused regression tests for responsive dice HTTP, CPU read, and audit on slow disks.
These use fake dice for testing ONLY. Production uses the configured hardware source.
"""
import asyncio
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from lan_dice import DiceBridge

class Fixed:
    mode = 'cpu_rdseed'  # test double; does not claim actual CPU RNG use
    def dice(self, count): return [3, 5][:count]

class E:
    def _roll_d6(self, s): return (1,1)
    def _roll_2d6(self, s): return (2,[1,1])
    def _roll_d66(self, s): return (11,[1,1])

def engine_type():
    class Engine:
        def _roll_d6(self, s): return (1, 1)
        def _roll_2d6(self, s): return (2, [1, 1])
        def _roll_d66(self, s): return (11, [1, 1])
    return Engine

class SlowSource(Fixed):
    def __init__(self, started, release): self.started, self.release = started, release
    def dice(self, count):
        self.started.set()
        if not self.release.wait(timeout=3): raise RuntimeError('test timeout')
        return super().dice(count)

class SlowAudit(DiceBridge):
    def __init__(self, *args, started=None, release=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit_started = started
        self.audit_release = release
    def _persist(self, row):
        self.audit_started.set()
        if not self.audit_release.wait(timeout=3): raise RuntimeError('test audit timeout')
        super()._persist(row)

def state():
    return SimpleNamespace(turn=1, phase=SimpleNamespace(value='gunnery'),
                           rng_counter=0, game_id='test')

async def poll(bridge, status, timeout=2):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        s=await asyncio.to_thread(bridge.public, 'axis')
        if s['status']==status: return s
        await asyncio.sleep(.006)
    raise AssertionError((status,await asyncio.to_thread(bridge.public,'axis')))

@pytest.mark.asyncio
async def test_slow_cpu_source_does_not_hold_state_lock(tmp_path):
    started, release = threading.Event(), threading.Event()
    src = SlowSource(started,release)
    bridge = DiceBridge(tmp_path/'audit.jsonl', src, animation_seconds=.02,
                        hold_seconds=.01, max_ack_wait_seconds=.2)
    Engine=engine_type();bridge.install(Engine)
    s=state()
    async def handler(*_): return Engine()._roll_2d6(s)
    job=asyncio.create_task(bridge.advance(handler,'/advance'))
    waiting=await poll(bridge,'waiting')
    send=asyncio.create_task(asyncio.to_thread(bridge.roll,'axis',waiting['id']))
    await asyncio.wait_for(asyncio.to_thread(started.wait),1)
    t=time.monotonic()
    d=await asyncio.wait_for(asyncio.to_thread(bridge.public,'allies'),.25)
    assert d['status']=='generating' and d['may_roll'] is False
    assert time.monotonic()-t<.25
    with pytest.raises(HTTPException) as exc: bridge.roll('axis',waiting['id'])
    assert exc.value.status_code==409
    release.set()
    await asyncio.wait_for(send,1)
    assert await asyncio.wait_for(job,2)==(8,[3,5])
    assert s.rng_counter==1

@pytest.mark.asyncio
async def test_slow_fsync_does_not_block_http_state(tmp_path):
    started, release = threading.Event(), threading.Event()
    bridge=SlowAudit(tmp_path/'audit.jsonl',Fixed(),animation_seconds=.01,
                     hold_seconds=.01,max_ack_wait_seconds=.1,
                     started=started,release=release)
    Engine=engine_type();bridge.install(Engine)
    s=state()
    async def handler(*_): return Engine()._roll_2d6(s)
    task=asyncio.create_task(bridge.advance(handler,'/advance'))
    r=await poll(bridge,'waiting')
    bridge.roll('axis',r['id'])
    await asyncio.wait_for(asyncio.to_thread(started.wait),1)
    # In v3 _persist holds the CV; both players and the event loop can freeze.
    app=FastAPI()
    bridge.register(app,lambda req: req.headers['x-side'],lambda req: True)
    @app.get('/heartbeat')
    async def heartbeat(): return {'ok':True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as cli:
        start=time.monotonic()
        both=await asyncio.wait_for(asyncio.gather(
            cli.get('/lan/dice/state',headers={'x-side':'axis'}),
            cli.get('/lan/dice/state',headers={'x-side':'allies'}),
            cli.get('/lan/dice/health',headers={'x-side':'axis'}),
            cli.get('/heartbeat')),.35)
        assert time.monotonic()-start<.35
        assert all(x.status_code==200 for x in both)
        assert all(x.json()['status']=='committing' for x in both[:2])
        assert both[2].json()['protocol']==4
        assert both[3].json()['ok'] is True
    release.set()
    assert await asyncio.wait_for(task,2)==(8,[3,5])
    assert s.rng_counter==1
    assert (tmp_path/'audit.jsonl').exists()

@pytest.mark.asyncio
async def test_both_acks_missing_still_progresses(tmp_path):
    bridge=DiceBridge(tmp_path/'audit.jsonl',Fixed(),animation_seconds=.01,
                      hold_seconds=.02,max_ack_wait_seconds=.12)
    Engine=engine_type();bridge.install(Engine)
    s=state()
    async def handler(*_): return Engine()._roll_2d6(s)
    job=asyncio.create_task(bridge.advance(handler,'/advance'))
    r=await poll(bridge,'waiting')
    bridge.roll('axis',r['id'])
    assert await asyncio.wait_for(job,.8)==(8,[3,5])
    assert bridge.public('axis')['status']=='idle'

@pytest.mark.asyncio
async def test_second_side_is_authorized_next(tmp_path):
    class E2:
        def _roll_d6(self, state): return 1,1
        def _roll_2d6(self, state): return 2,[1,1]
        def _roll_d66(self, state): return 11,[1,1]
        def _resolve_torpedoes(self,state):
            attacker,target=state.ships['A'],state.ships['B']
            distance,contact_target=4,target
            first=self._roll_2d6(state)
            definition={'damage_modifier':0}
            raw_damage_roll,damage_dice=self._roll_2d6(state)
            return first,(raw_damage_roll,damage_dice)
        def _torpedo_modifier(self,*args): return 0
    bridge=DiceBridge(tmp_path/'audit.jsonl',Fixed(),animation_seconds=.01,
                      hold_seconds=.01,max_ack_wait_seconds=.1)
    bridge.install(E2)
    s=state();s.ships={'A':SimpleNamespace(side='axis',name='A'),
                       'B':SimpleNamespace(side='allies',name='B')}
    async def handler(*_): return E2()._resolve_torpedoes(s)
    task=asyncio.create_task(bridge.advance(handler,'/advance'))
    a=await poll(bridge,'waiting')
    assert a['owner']=='axis'
    bridge.roll('axis',a['id'])
    for _ in range(100):
        await asyncio.sleep(.01)
        b=bridge.public('allies')
        if b.get('seq')==2 and b.get('status')=='waiting':break
    else: raise AssertionError('No next roll')
    assert b['owner']=='allies' and b['may_roll']
    assert not bridge.public('axis')['may_roll']
    bridge.roll('allies',b['id'])
    await asyncio.wait_for(task,1)

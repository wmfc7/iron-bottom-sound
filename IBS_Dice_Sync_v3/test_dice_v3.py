"""Regression tests for LAN dice result handoff and concurrent browsers."""
from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from lan_dice import DiceBridge

class DeterministicForTestOnly:
    mode = 'cpu_rdseed'  # fake source deliberately replaces hardware in tests
    def dice(self, count):
        return [3, 5][:count]

def make_engine_type():
  class Engine:
    def _roll_d6(self, state): return 1, 1
    def _roll_2d6(self, state): return 2, [1, 1]
    def _roll_d66(self, state): return 11, [1, 1]
    def _resolve_gunnery(self, state):
        return self._roll_2d6(state), self._roll_d66(state)
  return Engine

def state():
    return SimpleNamespace(game_id='test',turn=1,phase=SimpleNamespace(value='gunnery'),rng_counter=0)

async def state_wait(bridge, expected, seq=1, timeout=2):
    until = time.monotonic() + timeout
    while time.monotonic()<until:
        info=bridge.public('axis')
        if info['status']==expected and info.get('seq')==seq:
            return info
        await asyncio.sleep(.005)
    raise AssertionError(f'expected {expected}/{seq} got {bridge.public("axis")}')

@pytest.mark.asyncio
async def test_ack_handoff_prevents_old_new_split(tmp_path):
    bridge=DiceBridge(tmp_path/'audit.jsonl', DeterministicForTestOnly(), animation_seconds=.02,
                      hold_seconds=.10, max_ack_wait_seconds=.8)
    Engine=make_engine_type();bridge.install(Engine)
    engine=Engine();s=state()
    async def handler(*args):return engine._resolve_gunnery(s)
    task=asyncio.create_task(bridge.advance(handler,'/games/test/advance'))
    first=await state_wait(bridge,'waiting')
    bridge.roll('axis',first['id'])
    shown=await state_wait(bridge,'revealed')
    assert shown['dice']==[3,5] and shown['raw']==8
    bridge.acknowledge('axis',first['id'])
    bridge.acknowledge('axis',first['id'])  # idempotent duplicate from one browser
    await asyncio.sleep(.14)
    # Although enough min time elapsed, we do not advance to the next roll
    # while the other player's result receipt has not been confirmed.
    assert bridge.public('allies')['seq']==1
    bridge.acknowledge('allies',first['id'])
    second=await state_wait(bridge,'waiting',seq=2)
    assert second['id']!=first['id']
    with pytest.raises(HTTPException) as err:
        bridge.acknowledge('allies',first['id'])
    assert err.value.status_code==409
    bridge.roll('axis',second['id'])
    await state_wait(bridge,'revealed',seq=2)
    bridge.acknowledge('axis',second['id'])
    bridge.acknowledge('allies',second['id'])
    await asyncio.wait_for(task,1)
    assert s.rng_counter==2
    rows=[json.loads(x) for x in (tmp_path/'audit.jsonl').read_text().splitlines()]
    assert [r['seq'] for r in rows]==[1,2]

@pytest.mark.asyncio
async def test_automatic_release_when_second_browser_offline(tmp_path):
    bridge=DiceBridge(tmp_path/'audit.jsonl', DeterministicForTestOnly(), animation_seconds=.01,
                      hold_seconds=.025, max_ack_wait_seconds=.14)
    Engine=make_engine_type();bridge.install(Engine)
    async def handler(*args):return Engine()._roll_2d6(state())
    task=asyncio.create_task(bridge.advance(handler,'/advance'))
    r=await state_wait(bridge,'waiting')
    bridge.roll('axis',r['id'])
    await state_wait(bridge,'revealed')
    bridge.acknowledge('axis',r['id'])
    assert await asyncio.wait_for(task,1)==(8,[3,5])
    assert not bridge.busy

@pytest.mark.asyncio
async def test_ack_http_security_and_state_clock(tmp_path):
    bridge=DiceBridge(tmp_path/'audit.jsonl', DeterministicForTestOnly(), animation_seconds=.01,
                      hold_seconds=.03,max_ack_wait_seconds=.3)
    Engine=make_engine_type();bridge.install(Engine)
    app=FastAPI()
    bridge.register(app, lambda req: req.headers['x-side'],lambda req: req.headers.get('origin')!='https://evil')
    async def handler(*args):return Engine()._roll_2d6(state())
    task=asyncio.create_task(bridge.advance(handler,'/advance'))
    roll=await state_wait(bridge,'waiting')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        premature=await client.post('/lan/dice/ack',json={'id':roll['id']},headers={'x-side':'allies'})
        assert premature.status_code==409
        forbidden=await client.post('/lan/dice/roll',json={'id':roll['id']},headers={'x-side':'allies'})
        assert forbidden.status_code==403
        evil=await client.post('/lan/dice/roll',json={'id':roll['id']},headers={'x-side':'axis','origin':'https://evil'})
        assert evil.status_code==403
        ok=await client.post('/lan/dice/roll',json={'id':roll['id']},headers={'x-side':'axis'})
        assert ok.status_code==200
        await state_wait(bridge,'revealed')
        reply=await client.get('/lan/dice/state',headers={'x-side':'allies'})
        assert reply.status_code==200
        data=reply.json()
        assert isinstance(data['server_time_ms'],int)
        assert isinstance(data['animation_start_ms'],int)
        assert data['status']=='revealed' and data['dice']==[3,5]
        ack1=await client.post('/lan/dice/ack',json={'id':roll['id']},headers={'x-side':'axis'})
        ack2=await client.post('/lan/dice/ack',json={'id':roll['id']},headers={'x-side':'allies'})
        assert ack1.status_code==ack2.status_code==200
    await asyncio.wait_for(task,1)

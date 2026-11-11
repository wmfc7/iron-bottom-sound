import asyncio
import sys
from pathlib import Path
import pytest
import httpx
from fastapi import FastAPI, HTTPException

sys.path.insert(0,str(Path(__file__).resolve().parent))
from lan_dice import DiceBridge

class FixedSource:
    mode = 'cpu_rdseed'
    def dice(self, count):
        return [2] * count

@pytest.mark.asyncio
async def test_heartbeat_available_even_when_game_lock_busy(tmp_path):
    app=FastAPI()
    bridge=DiceBridge(tmp_path/'audit.jsonl', FixedSource(),animation_seconds=.01,hold_seconds=.01,max_ack_wait_seconds=.02)
    def player(req):
        s=req.headers.get('x-side')
        if s not in ('axis','allies'): raise HTTPException(401,'unauthenticated')
        return s
    bridge.register(app,player,lambda req: True)
    @app.get('/api/games/test/view')
    async def game():
        return {'ok':True}
    @app.get('/lan/status')
    async def status():
        return {'ok':True}
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,base_url='http://local',timeout=2.0) as client:
        bridge.busy=True
        args={'headers':{'x-side':'allies'}}
        assert (await client.get('/api/games/test/view',**args)).status_code==503
        assert (await client.get('/lan/status',**args)).status_code==503
        state=await client.get('/lan/dice/state',**args)
        assert state.status_code==200 and state.json()['status']=='calculating'
        page=await client.get('/lan/dice/standalone',**args)
        assert page.status_code==200
        assert '<script src="/lan/dice/client.js" defer>' in page.text
        assert page.headers['cache-control']=='no-store'
        unauth=await client.get('/lan/dice/standalone')
        assert unauth.status_code==401
        bridge.busy=False
        assert (await client.get('/api/games/test/view',**args)).json()=={'ok':True}
        assert (await client.get('/lan/status',**args)).json()=={'ok':True}

@pytest.mark.asyncio
async def test_same_roll_only_owner_can_roll_with_gateway_busy(tmp_path):
    from types import SimpleNamespace
    bridge=DiceBridge(tmp_path/'audit.jsonl',FixedSource(),animation_seconds=.01,hold_seconds=.01,max_ack_wait_seconds=.02)
    # Avoid engine patching: simulate a paused 2D6 request with the same public model.
    context=__import__('lan_dice')
    original=context._identify_roll
    context._identify_roll=lambda notation,state: {'owner':'allies','reason':'collision','detail':'damage','rule':{'title':'collision','note':'','rows':[],'kind':'direct','modifier':0,'band':''}}
    try:
        state=SimpleNamespace(turn=1,phase='movement_resolution',game_id='test',rng_counter=0)
        task=asyncio.create_task(asyncio.to_thread(bridge.request_roll,'2D6',state))
        for _ in range(100):
            if bridge.public('allies')['status']=='waiting': break
            await asyncio.sleep(.005)
        pending=bridge.public('allies')
        assert pending['may_roll'] is True
        assert bridge.public('axis')['may_roll'] is False
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ex:
            await asyncio.to_thread(bridge.roll,'axis',pending['id'])
        assert ex.value.status_code==403
        await asyncio.to_thread(bridge.roll,'allies',pending['id'])
        assert await asyncio.wait_for(task,2)==(4,[2,2])
        assert state.rng_counter==1
        assert bridge.public('allies')['status']=='idle'
    finally:
        context._identify_roll=original

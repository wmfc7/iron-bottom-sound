import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent))
from lan_dice import DiceBridge, RandomSource
from install_online_dice import install

class State:
    def __init__(self):
        self.game_id='mock-game'; self.turn=1; self.phase=SimpleNamespace(value='gunnery')
        self.rng_counter=0; self.ships={}

class Engine:
    def _roll_d6(self,state): return 1,1
    def _roll_2d6(self,state): return 2,[1,1]
    def _roll_d66(self,state): return 11,[1,1]

@pytest.fixture
def bridge(tmp_path):
    b=DiceBridge(tmp_path/'rolls.jsonl',RandomSource('os_csprng'),animation_seconds=.06,hold_seconds=.06)
    original={name: getattr(Engine,name) for name in ('_roll_d6','_roll_2d6','_roll_d66')}
    b.install(Engine)
    yield b
    for name, fn in original.items(): setattr(Engine,name,fn)

@pytest.mark.asyncio
async def test_server_waits_and_only_correct_side_can_roll(bridge):
    state=State(); engine=Engine()
    assert engine._roll_d66(state)==(11,[1,1]) # normal play is unaffected
    async def api(method,path,side):
        return engine._roll_d66(state)
    task=asyncio.create_task(bridge.advance(api,'/games/mock-game/advance'))
    for _ in range(200):
        await asyncio.sleep(.01)
        cur=bridge.public('axis')
        if cur['status']=='waiting':break
    assert cur['status']=='waiting'
    assert cur['notation']=='D66' and cur['owner']=='axis'
    assert 'dice' not in cur
    with pytest.raises(HTTPException) as err:
        bridge.roll('allies',cur['id'])
    assert err.value.status_code==403
    assert not task.done()
    bridge.roll('axis',cur['id'])
    assert bridge.public('axis')['status']=='rolling'
    assert 'dice' not in bridge.public('allies')
    with pytest.raises(HTTPException) as err:
        bridge.roll('axis',cur['id'])
    assert err.value.status_code==409
    for _ in range(200):
        await asyncio.sleep(.005)
        d=bridge.public('allies')
        if d['status']=='revealed':break
    assert d['status']=='revealed' and len(d['dice'])==2
    got=await task
    assert got[0]==got[1][0]*10+got[1][1]
    assert state.rng_counter==1
    logfile=bridge.audit_file.read_text(encoding='utf-8').splitlines()
    assert json.loads(logfile[0])['raw']==got[0]

@pytest.mark.asyncio
async def test_1d6_and_2d6(bridge):
    state=State();engine=Engine()
    for method in ('_roll_d6','_roll_2d6'):
        async def api(*args): return getattr(engine,method)(state)
        task=asyncio.create_task(bridge.advance(api,'/games/mock-game/advance'))
        for _ in range(200):
            await asyncio.sleep(.005)
            s=bridge.public('axis')
            if s['status']=='waiting':break
        bridge.roll('axis',s['id'])
        v=await task
        assert 1<=v[0]<=(6 if method=='_roll_d6' else 12)
    assert state.rng_counter==2

@pytest.mark.skipif(os.name=='nt',reason='FIFO test needs POSIX')
def test_hrng_strict_and_unbiased_rejection(tmp_path):
    with pytest.raises(RuntimeError, match='IBS_DICE_HRNG_PATH'):
        RandomSource('hrng','')
    reg=tmp_path/'captured.bin';reg.write_bytes(b'\x00')
    with pytest.raises(RuntimeError, match='普通文件'):
        RandomSource('hrng',str(reg))
    pipe=tmp_path/'rng';os.mkfifo(pipe)
    rng=RandomSource('hrng',str(pipe))
    def produce():
        with open(pipe,'wb', buffering=0) as f:
            f.write(bytes([252, 0, 5]))
    t=threading.Thread(target=produce);t.start()
    assert rng.dice(2)==[1,6]
    t.join(2)

def test_patch_anchors_against_previous_v3_snapshot():
    src=Path(__file__).parent.joinpath('lan_server.py').read_text(encoding='utf-8')
    mod=install(src)
    assert mod.count('_dice_bridge.advance(call_engine')==2
    assert mod.count('/lan/dice/client.js')==1
    assert install(mod)==mod
    assert "timeout=(None if method == 'POST'" in mod
    with pytest.raises(RuntimeError):
        install(src.replace('timeout=90) as client:', 'timeout=30) as client:'))

@pytest.mark.asyncio
async def test_context_survives_fastapi_sync_handler(tmp_path):
    """ASGITransport -> FastAPI sync endpoint -> threadpool must retain ContextVar."""
    import httpx
    from fastapi import FastAPI
    class E:
        def _roll_d6(self,state): return 1,1
        def _roll_2d6(self,state): return 2,[1,1]
        def _roll_d66(self,state): return 11,[1,1]
    state=State(); eng=E()
    bridge=DiceBridge(tmp_path/'audit.jsonl',RandomSource('os_csprng'),animation_seconds=.03,hold_seconds=.03)
    bridge.install(E)
    app=FastAPI()
    @app.post('/advance')
    def api_advance():
        a,b=eng._roll_d6(state)
        return {'raw':a,'die':b}
    async def call_engine(method,path,side):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            return await c.post('/advance')
    task=asyncio.create_task(bridge.advance(call_engine,'/games/mock-game/advance'))
    for _ in range(100):
        await asyncio.sleep(.01)
        data=bridge.public('axis')
        if data['status']=='waiting':break
    assert data['status']=='waiting', 'ContextVar did not propagate to FastAPI threadpool'
    bridge.roll('axis',data['id'])
    response=await task
    assert response.status_code==200
    body=response.json()
    assert 1<=body['raw']<=6 and body['die']==body['raw']

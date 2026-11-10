"""Contract tests run without the upstream repository (upstream integration needs actual source)."""
import importlib
import json
import sys
import types

import httpx
import pytest
from fastapi.testclient import TestClient

# Replace unavailable upstream package with a stub at test time.
pkg = types.ModuleType('iron_bottom_sound')
pkg.api = types.SimpleNamespace(app=None)
sys.modules.setdefault('iron_bottom_sound', pkg)
server = importlib.import_module('lan_server')
patch = importlib.import_module('patch_frontend')


@pytest.fixture
def simulated(monkeypatch):
    state = {'phase': 'formation_setup', 'turn': 1, 'submitted': set(), 'advance': 0}
    ticket = {'axis': 'axis-test-ticket', 'allies': 'allies-test-ticket'}
    server._room = {'game_id': 'game-test', 'hashes': {k: server.token_digest(v) for k, v in ticket.items()}, 'tickets': ticket}
    server._last_error = ''

    async def fake_call(method, path, side=None, data=None, query=''):
        def response(status, obj):
            return httpx.Response(status, json=obj)
        if path == '/games/game-test/view':
            return response(200, {'phase': state['phase'], 'turn': state['turn'],
                                  'own_orders_submitted': side in state['submitted'],
                                  'both_orders_submitted': len(state['submitted']) == 2})
        if path == '/games/game-test/orders' and method == 'POST':
            order = json.loads(data)
            if order['side'] != side:
                return response(403, {'detail': 'side invalid'})
            state['submitted'].add(side)
            return response(200, {'valid': True, 'both_submitted': len(state['submitted']) == 2})
        if path == '/games/game-test/advance':
            if len(state['submitted']) != 2:
                return response(409, {'detail': 'waiting'})
            state['advance'] += 1
            state['phase'] = 'contact_setup'
            state['submitted'].clear()
            return response(200, [])
        if path == '/games/game-test/legal-actions':
            return response(200, [{'own_side': side}])
        return response(404, {'detail': 'missing'})

    monkeypatch.setattr(server, 'call_engine', fake_call)
    with TestClient(server.app) as client:
        yield client, state, ticket


def join(client, token):
    res = client.post('/lan/claim', json={'ticket': token}, headers={'Origin': 'http://testserver'})
    assert res.status_code == 200, res.text
    return res.json()


def test_join_and_side_lock(simulated):
    client, state, tickets = simulated
    assert client.get('/api/games/game-test/view').status_code == 401
    assert join(client, tickets['axis'])['side'] == 'axis'
    res = client.get('/api/games/game-test/legal-actions', headers={'X-Player-Side': 'allies'})
    assert res.json() == [{'own_side': 'axis'}]
    assert client.get('/api/games/other-game/view').status_code == 403
    assert client.get('/api/games/game-test/save').status_code == 403
    assert client.get('/api/games/game-test/view?debug=true').status_code == 403
    assert client.post('/api/games/game-test/ai-opponent', json={}).status_code == 403
    assert client.post('/api/games', json={'mode': 'hotseat'}).status_code == 403


def test_one_advance_after_both_seal(simulated):
    client, state, tokens = simulated
    join(client, tokens['axis'])
    assert client.post('/api/games/game-test/orders', json={'side':'allies'}).status_code == 403
    first = client.post('/api/games/game-test/orders', json={'side':'axis','phase':'formation_setup'})
    assert first.status_code == 200, first.text
    assert state['advance'] == 0
    assert client.get('/lan/status').json()['own_submitted'] is True
    assert client.post('/api/games/game-test/orders', json={'side':'axis'}).status_code == 409
    join(client, tokens['allies'])
    second = client.post('/api/games/game-test/orders', json={'side':'allies','phase':'formation_setup'})
    assert second.status_code == 200, second.text
    assert state['advance'] == 1
    assert state['phase'] == 'contact_setup'
    assert client.post('/api/games/game-test/advance', json={}).status_code == 403


def test_csrf_origin_check(simulated):
    client, _, tickets = simulated
    assert client.post('/lan/claim', json={'ticket':tickets['axis']},
                       headers={'Origin': 'http://evil.example'}).status_code == 403
    join(client, tickets['axis'])
    assert client.post('/api/games/game-test/orders', json={'side':'axis'},
                       headers={'Origin':'http://evil.example'}).status_code == 403


def test_source_patch_is_idempotent():
    # Sufficiently representative structural anchors from upstream App.tsx.
    base = '''const ACTIVE_GAME_KEY = "ibs.active-game.v1";
export default function App() {
  const start = async (scenario:string) => {};
  const toggleDebug = async () => {};
  const act = async () => {
    if (!game || !view || acting) return;
    setActing(true);
    try {
      if (orderPhases.has(view.phase)) await submitOrders(game,side,JSON.parse(draft));
      if (mode === "llm") {
        try { await callLLM(); } finally { setLlmBusy(false); }
      }
    } catch (e) {} finally {setActing(false);}
  };
  const unlock = async () => {};
}
'''
    changed = patch.patch(base)
    assert 'if (LAN_MODE)' in changed
    assert 'window.setInterval' in changed
    assert changed == patch.patch(changed)
    assert 'await refresh(game, side)' in changed


def test_recovery_of_previous_both_sealed(simulated):
    """Final POST can be lost: recovery must advance already persisted orders."""
    import asyncio
    client, state, tokens = simulated
    state['submitted'].update(('axis', 'allies'))
    asyncio.run(server.reconcile_once())
    assert state['advance'] == 1
    assert state['phase'] == 'contact_setup'
    assert state['submitted'] == set()
    # Rechecking a fresh phase must not accidentally advance it again.
    asyncio.run(server.reconcile_once())
    assert state['advance'] == 1


def test_advance_failure_is_visible_and_retry_preserves_orders(simulated, monkeypatch):
    client, state, tokens = simulated
    engine = server.call_engine
    rejected = {'count': 0}

    async def transient_failure(method, path, side=None, data=None, query=''):
        if method == 'POST' and path.endswith('/advance') and rejected['count'] == 0:
            rejected['count'] += 1
            return httpx.Response(409, json={'detail': '规则阻断（测试故障）'})
        return await engine(method, path, side, data, query)

    monkeypatch.setattr(server, 'call_engine', transient_failure)
    join(client, tokens['axis'])
    assert client.post('/api/games/game-test/orders', json={'side':'axis'}).status_code == 200
    join(client, tokens['allies'])
    submitted = client.post('/api/games/game-test/orders', json={'side':'allies'})
    assert submitted.status_code == 200
    assert submitted.headers.get('X-LAN-Advance-Error') == '1'
    assert state['advance'] == 0
    assert state['submitted'] == {'axis', 'allies'}
    assert '409' in client.get('/lan/status').json()['last_error']
    retry = client.post('/lan/retry')
    assert retry.status_code == 200
    assert retry.json()['last_error'] == ''
    assert state['advance'] == 1
    assert state['submitted'] == set()

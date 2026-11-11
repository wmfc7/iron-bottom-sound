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
def simulated(monkeypatch, tmp_path):
    state = {'phase': 'formation_setup', 'turn': 1, 'submitted': set(), 'advance': 0,
             'games_created': [], 'game_id': 'game-test'}
    monkeypatch.setattr(server, 'ROOMFILE', tmp_path / 'room.json')
    ticket = {'axis': 'axis-test-ticket', 'allies': 'allies-test-ticket'}
    server._room = {'game_id': 'game-test', 'scenario': 'IBS-S-03', 'hashes': {k: server.token_digest(v) for k, v in ticket.items()}, 'tickets': ticket,
                     'lobby': server.fresh_lobby('IBS-S-03')}
    server._last_error = ''

    async def fake_call(method, path, side=None, data=None, query=''):
        def response(status, obj):
            return httpx.Response(status, json=obj)
        if path == '/scenarios' and method == 'GET':
            return response(200, [{'id':'IBS-S-03','title':'通道行动','turns':10}, {'id':'IBS-S-01','title':'埃斯佩兰斯角','turns':12}])
        if path == '/custom-scenarios' and method == 'GET':
            return response(200, [])
        if path == '/scenarios/IBS-S-01/briefing':
            return response(200, {'title':'埃斯佩兰斯角','special_rules':[]})
        if path == '/games' and method == 'POST':
            payload=json.loads(data)
            state['games_created'].append(payload)
            state['game_id']='created-' + str(len(state['games_created']))
            return response(201, {'game_id':state['game_id']})
        if path == '/games/game-test/view' or path == f"/games/{state['game_id']}/view":
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


def test_lobby_requires_cookie_and_scopes_origin(simulated):
    client, _, tokens = simulated
    assert client.get('/lan/lobby/state').status_code == 401
    join(client, tokens['axis'])
    assert client.get('/lan/lobby/state').status_code == 200
    assert client.get('/lan/lobby/scenarios').json()[0]['id'] == 'IBS-S-03'
    assert client.post('/lan/lobby/ready', json={'revision':1,'ready':True},
                       headers={'Origin':'http://malicious.invalid'}).status_code == 403
    assert client.get('/', follow_redirects=False).status_code == 303
    assert client.get('/', follow_redirects=False).headers['location'] == '/lan/lobby'


def test_lobby_two_ready_creates_once_and_preserves_previous(simulated):
    client, state, tokens = simulated
    join(client, tokens['axis'])
    base = client.get('/lan/lobby/state').json()
    newconfig = {**base['config'], 'scenario_id':'IBS-S-01', 'seed':247,
                 'optional_rules':{**base['config']['optional_rules'],'radar':True,'smoke':True},
                 'radar_1942_variant': True}
    cfg = client.post('/lan/lobby/config', json={'revision':base['revision'], 'config':newconfig})
    assert cfg.status_code == 200, cfg.text
    rev = cfg.json()['revision']
    assert cfg.json()['ready'] == {'axis': False, 'allies': False}
    first = client.post('/lan/lobby/ready', json={'revision':rev,'ready':True})
    assert first.status_code == 200
    assert len(state['games_created']) == 0
    join(client, tokens['allies'])
    second = client.post('/lan/lobby/ready', json={'revision':rev,'ready':True})
    assert second.status_code == 200, second.text
    assert second.json()['game_id'] == 'created-1'
    assert second.json()['game_url'].startswith('/?game=created-1&side=allies&lan=1')
    assert state['games_created'] == [{
        'scenario_id':'IBS-S-01','seed':247,
        'options': {'mode':'hotseat','ruleset_version':'night-v2','battle_report':False,
                    'realistic_command':False,'optional_rules':newconfig['optional_rules'],
                    'squall_hexes':[], 'radar_1942_variant':True, 'command_delay_mode':False},
        'research_consent':{'allow':False}}]
    assert server._room['previous_game_ids'] == ['game-test']
    # A stale browser cannot accidentally create another match.
    assert client.post('/lan/lobby/ready',json={'revision':rev,'ready':True}).status_code == 409
    assert len(state['games_created']) == 1
    assert server.ROOMFILE.is_file()
    assert json.loads(server.ROOMFILE.read_text(encoding='utf-8'))['game_id'] == 'created-1'


def test_lobby_edit_cancels_both_readiness_and_optimistic_lock(simulated):
    client, state, tokens = simulated
    join(client, tokens['axis'])
    original = client.get('/lan/lobby/state').json()
    assert client.post('/lan/lobby/ready',json={'revision':original['revision'],'ready':True}).status_code == 200
    join(client, tokens['allies'])
    cfg={**original['config'],'seed':22}
    res = client.post('/lan/lobby/config',json={'revision':original['revision'],'config':cfg})
    assert res.status_code == 200, res.text
    assert res.json()['ready']=={'axis':False,'allies':False}
    assert client.post('/lan/lobby/config',json={'revision':original['revision'],'config':cfg}).status_code==409
    assert client.post('/lan/lobby/ready',json={'revision':original['revision'],'ready':True}).status_code==409
    assert state['games_created']==[]


def test_lobby_invalid_options_do_not_create_match(simulated):
    client, state, tokens = simulated
    join(client, tokens['axis'])
    current=client.get('/lan/lobby/state').json()
    for changes in ({'scenario_id':'fake-scenario'}, {'seed':True},
                    {'optional_rules':{'radar':True}},
                    {'squall_hexes':['A1']}, {'battle_report':'true'}):
        cfg={**current['config'],**changes}
        r=client.post('/lan/lobby/config',json={'revision':current['revision'],'config':cfg})
        assert r.status_code == 422, (changes,r.text)
    assert state['games_created']==[]


def test_new_room_config_has_no_default_game_and_original_login_tickets_persist(simulated):
    client, _, tickets = simulated
    server._room['game_id'] = None
    join(client,tickets['axis'])
    assert client.get('/lan/status').json()['phase'] == 'lobby'
    assert client.post('/lan/retry').status_code == 409
    assert client.get('/api/games/game-test/view').status_code == 403
    assert client.get('/lan/lobby').status_code == 200


def test_game_page_contains_lobby_shortcut_and_cross_side_denied(simulated, monkeypatch, tmp_path):
    client, _, tokens = simulated
    (tmp_path / 'index.html').write_text('<html><body><div id="root"></div></body></html>', encoding='utf-8')
    monkeypatch.setattr(server, 'FRONTEND', tmp_path)
    join(client, tokens['axis'])
    assert client.get('/?game=game-test&side=allies&lan=1', follow_redirects=False).status_code == 303
    game = client.get('/?game=game-test&side=axis&lan=1')
    assert game.status_code == 200
    assert 'href="/lan/lobby"' in game.text
    assert client.get('/lan/lobby').status_code == 200


def test_game_creation_failure_keeps_existing_match_and_clears_ready(simulated, monkeypatch):
    client, state, tickets = simulated
    original = server.call_engine

    async def fail_create(method, path, side=None, data=None, query=''):
        if method == 'POST' and path == '/games':
            return httpx.Response(422, json={'detail':'incompatible game rules'})
        return await original(method, path, side, data, query)

    monkeypatch.setattr(server, 'call_engine', fail_create)
    join(client, tickets['axis'])
    assert client.post('/lan/lobby/ready',json={'revision':1,'ready':True}).status_code == 200
    join(client, tickets['allies'])
    res = client.post('/lan/lobby/ready',json={'revision':1,'ready':True})
    assert res.status_code == 422
    assert '422' in res.json()['error']
    assert res.json()['ready'] == {'axis':False,'allies':False}
    assert server._room['game_id'] == 'game-test'
    assert state['games_created'] == []

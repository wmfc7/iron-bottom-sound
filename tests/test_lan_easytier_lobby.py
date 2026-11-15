"""Live HTTP contract tests with a deterministic in-process fake upstream API.

No source rule tables or native RDSEED DLL needed for these gateway-only tests.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse


def stub_gateway(monkeypatch, tmp_path):
    os.environ['IBS_DICE_SOURCE'] = 'os_csprng'
    upstream = FastAPI()
    games = {'initial': {'game_id': 'initial', 'scenario_id': 'IBS-S-03',
                         'scenario_title': 'Test scenario', 'turn': 3,
                         'phase': 'formation_setup', 'options': {'mode': 'hotseat'}}}
    imported_ids = []

    class FakeEngine:
        def _roll_d6(self, state): return 1
        def _roll_2d6(self, state): return 2
        def _roll_d66(self, state): return 11

    @upstream.get('/games/{game_id}/view')
    def view(game_id: str):
        if game_id not in games:
            return JSONResponse({'detail': 'missing'}, status_code=404)
        row = games[game_id]
        return {'phase': row['phase'], 'turn': row['turn'], 'both_orders_submitted': False}

    @upstream.get('/games/{game_id}/save')
    def save(game_id: str):
        return {'format': 'iron-bottom-sound-save', 'state': games[game_id],
                'events': [{'sequence': 1, 'type': 'game_created'}], 'snapshots': [], 'checksum': 'test'}

    @upstream.post('/games/import')
    def load(bundle: dict):
        if bundle.get('checksum') != 'test':
            return JSONResponse({'detail': 'invalid'}, status_code=422)
        new_id = f'loaded-{len(imported_ids) + 1}'
        games[new_id] = {**bundle['state'], 'game_id': new_id}
        imported_ids.append(new_id)
        return JSONResponse({'game_id': new_id}, status_code=201)

    @upstream.get('/scenarios')
    def scenarios(): return [{'id': 'IBS-S-03', 'title': 'Test', 'turns': 7}]
    @upstream.get('/custom-scenarios')
    def custom(): return []

    stub = types.ModuleType('iron_bottom_sound')
    stub.api = types.SimpleNamespace(app=upstream, engine=FakeEngine(), repository=None)
    monkeypatch.setitem(sys.modules, 'iron_bottom_sound', stub)
    sys.modules.pop('lan_server', None)
    # tests run from repo root with lan_server importable
    gateway = importlib.import_module('lan_server')
    gateway.ROOMFILE = tmp_path / 'backend' / 'room.json'
    from lan_lobby_storage import LobbySaveStore
    gateway._lobby_saves = LobbySaveStore(tmp_path / 'backend' / 'lan-saves')
    gateway._room = {
        'game_id': 'initial', 'scenario': 'IBS-S-03',
        'tickets': {'axis': 'side-a', 'allies': 'side-b'},
        'hashes': {'axis': gateway.token_digest('side-a'), 'allies': gateway.token_digest('side-b')},
        'entry_ticket': 'shared-invite', 'entry_hash': gateway.token_digest('shared-invite'),
        'seat_claims': {}, 'previous_game_ids': [],
        'lobby': gateway.fresh_lobby('IBS-S-03')}
    return gateway, games, imported_ids


@pytest.fixture
def env(monkeypatch, tmp_path):
    return stub_gateway(monkeypatch, tmp_path)


def enter(client):
    assert client.post('/lan/entry', json={'ticket': 'shared-invite'}).status_code == 200


def test_both_choose_seats_and_rejoin(env):
    gateway, _, _ = env
    with TestClient(gateway.app) as axis, TestClient(gateway.app) as allies:
        assert axis.get('/lan/lobby/state').status_code == 401
        assert axis.get('/lan/seat').status_code == 200
        assert axis.post('/lan/entry', json={'ticket': 'wrong'}).status_code == 401
        enter(axis); enter(allies)
        assert axis.post('/lan/seat/claim', json={'side': 'axis'}).status_code == 200
        assert axis.get('/lan/lobby/state').json()['side'] == 'axis'
        assert axis.post('/lan/seat/claim', json={'side': 'allies'}).status_code == 409
        assert allies.post('/lan/seat/claim', json={'side': 'axis'}).status_code == 409
        assert allies.post('/lan/seat/claim', json={'side': 'allies'}).status_code == 200
        assert allies.get('/lan/lobby/state').json()['side'] == 'allies'
        assert axis.get('/lan/seat').status_code == 200  # client follows redirect
        assert gateway._room['seat_claims']['axis'] != gateway._room['seat_claims']['allies']
        # A stolen legacy side invitation cannot bypass a claimed seat.
        with TestClient(gateway.app) as attacker:
            attacker.cookies.set('ibs_lan_ticket', 'side-a')
            assert attacker.get('/lan/lobby/state').status_code == 401
        assert 'tickets' not in axis.get('/lan/lobby/state').text


def test_save_and_mutual_load_and_no_hidden_state_leak(env):
    gateway, games, imported = env
    with TestClient(gateway.app) as axis, TestClient(gateway.app) as allies:
        enter(axis); enter(allies)
        assert axis.post('/lan/seat/claim', json={'side': 'axis'}).status_code == 200
        assert allies.post('/lan/seat/claim', json={'side': 'allies'}).status_code == 200
        saved = axis.post('/lan/lobby/save', json={'label': '第3回合战场'}).json()
        assert saved['game_id'] == 'initial'
        items = allies.get('/lan/lobby/saves').json()
        assert len(items) == 1 and items[0]['id'] == saved['id']
        assert 'events' not in str(items)
        assert 'state' not in str(items)
        assert allies.get('/api/games/initial/save').status_code == 403
        assert allies.post('/lan/lobby/load', json={'revision': 1, 'save_id': saved['id']}).status_code == 200
        assert gateway._room['game_id'] == 'initial' and not imported
        assert axis.post('/lan/lobby/load', json={'revision': 1, 'save_id': saved['id']}).status_code == 200
        assert gateway._room['game_id'] == 'loaded-1'
        assert len(imported) == 1
        assert gateway._room['previous_game_ids'] == ['initial']
        assert gateway._room['lobby']['load_pending'] is None
        assert axis.get('/lan/lobby/state').json()['game_url'].startswith('/?game=loaded-1')
        assert gateway._lobby_saves.read(saved['id'])['state']['game_id'] == 'initial'


def test_invalid_file_id_and_no_auth(env):
    gateway, _, _ = env
    with TestClient(gateway.app) as client:
        assert client.get('/lan/lobby/saves').status_code == 401
        assert client.post('/lan/lobby/save', json={'label': ''}).status_code == 401
        enter(client)
        assert client.get('/lan/lobby/saves').status_code == 401
        client.post('/lan/seat/claim', json={'side': 'axis'})
        assert client.post('/lan/lobby/load', json={'revision': 1, 'save_id': '../../room'}).status_code == 404
        assert client.post('/lan/lobby/save', json={'label': 'x' * 61}).status_code == 422


def test_seat_persists_in_roomfile(env):
    gateway, _, _ = env
    with TestClient(gateway.app) as c:
        enter(c)
        assert c.post('/lan/seat/claim', json={'side': 'allies'}).status_code == 200
        saved = json.loads(gateway.ROOMFILE.read_text(encoding='utf8'))
        assert saved['seat_claims'] == gateway._room['seat_claims']
        assert saved['seat_claims']['allies'] != 'shared-invite'
        assert saved['entry_ticket'] == 'shared-invite'


def test_save_list_does_not_reveal_full_bundle(env):
    gateway, _, _ = env
    with TestClient(gateway.app) as player:
        enter(player)
        player.post('/lan/seat/claim', json={'side': 'axis'})
        row = player.post('/lan/lobby/save', json={'label': '<img src=x onerror=alert(1)>'}).json()
        assert row['label'] == '<img src=x onerror=alert(1)>'
        listing = player.get('/lan/lobby/saves').json()
        assert 'snapshots' not in str(listing) and 'checksum' not in str(listing)
        raw = gateway._lobby_saves.read(row['id'])
        assert raw['checksum'] == 'test'  # original full snapshot on host disk only


def test_different_save_requires_second_mutual_approval(env):
    gateway, _, imported = env
    with TestClient(gateway.app) as a, TestClient(gateway.app) as b:
        enter(a); enter(b)
        a.post('/lan/seat/claim', json={'side': 'axis'})
        b.post('/lan/seat/claim', json={'side': 'allies'})
        first = a.post('/lan/lobby/save', json={'label': 'a'}).json()['id']
        second = a.post('/lan/lobby/save', json={'label': 'b'}).json()['id']
        a.post('/lan/lobby/load', json={'revision': 1, 'save_id': first})
        b.post('/lan/lobby/load', json={'revision': 1, 'save_id': second})
        assert imported == [] and gateway._room['game_id'] == 'initial'
        assert gateway._room['lobby']['load_pending']['acks'] == {'axis': False, 'allies': True}
        a.post('/lan/lobby/load', json={'revision': 1, 'save_id': second})
        assert imported == ['loaded-1']


def test_host_prepares_room_without_url_shortcut(env, monkeypatch, tmp_path):
    import asyncio
    gateway, _, _ = env
    root = tmp_path / 'game'
    dist = root / 'frontend' / 'dist'
    dist.mkdir(parents=True)
    (dist / 'index.html').write_text('<!doctype html>', encoding='utf8')
    gateway.ROOT = root
    gateway.FRONTEND = dist
    gateway.ROOMFILE = root / 'backend' / 'lan-duel-room.json'
    monkeypatch.setattr(gateway, 'lan_address', lambda: '10.88.1.10')
    asyncio.run(gateway.prepare_room('IBS-S-03', 1, True, 8765))
    assert gateway.ROOMFILE.exists()
    assert gateway._room['entry_ticket']
    assert not (tmp_path / '铁底湾-双击加入联机大厅.url').exists()


def test_path_traversal_rejected(env):
    gateway, _, _ = env
    from lan_lobby_storage import LobbySaveStore
    for bad in ('../x', 'a' * 33, 'a' * 31 + 'Z', '', '..\\\\evil'):
        with pytest.raises(ValueError):
            gateway._lobby_saves.read(bad)


def test_legacy_cookie_does_not_hide_new_picker(env):
    gateway, _, _ = env
    with TestClient(gateway.app) as legacy:
        legacy.cookies.set('ibs_lan_ticket', 'side-a')
        assert legacy.get('/lan/lobby/state').status_code == 200  # old route remains compatible
        page = legacy.get('/lan/seat')
        assert page.status_code == 200 and 'id="seats"' in page.text
        enter(legacy)
        legacy.post('/lan/seat/claim', json={'side': 'axis'})
        assert 'id="seats"' not in legacy.get('/lan/seat').text

"""Auto-discovery contract tests. Never require a real EasyTier adapter or private network key."""
from __future__ import annotations
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lan_easytier_lobby import stub_gateway


@pytest.fixture
def env(monkeypatch, tmp_path):
    gateway, games, imports = stub_gateway(monkeypatch, tmp_path)
    monkeypatch.setenv('IBS_LAN_AUTOFIND', '1')
    monkeypatch.setenv('IBS_LAN_ADVERTISE_IP', '10.144.144.1')
    monkeypatch.setenv('IBS_LAN_AUTOFIND_CIDR', '10.144.144.1/24')
    return gateway


def test_discovery_advertises_only_public_metadata_and_no_tickets(env):
    with TestClient(env.app, client=('10.144.144.2', 5555)) as c:
        resp = c.get('/lan/discovery')
        assert resp.status_code == 200
        assert resp.json() == {'service':'iron-bottom-sound-easytier', 'protocol':1,
                               'title':'铁底湾的回响 IV', 'open_seats':['axis','allies']}
        assert 'shared-invite' not in resp.text
        assert 'side-a' not in resp.text and 'side-b' not in resp.text
        assert resp.headers['cache-control'] == 'no-store'


def test_autojoin_creates_session_while_preserving_seat_claim_constraints(env):
    with TestClient(env.app, client=('10.144.144.2', 1001)) as player, TestClient(
        env.app, client=('10.144.144.3', 1001)) as other:
        assert player.get('/lan/seat').status_code == 200
        assert player.get('/lan/seat/state').status_code == 401
        assert player.post('/lan/auto-entry').status_code == 200
        assert other.post('/lan/auto-entry').status_code == 200
        assert player.get('/lan/seat/state').json()['mine'] is None
        assert player.post('/lan/seat/claim', json={'side':'axis'}).status_code == 200
        assert other.post('/lan/seat/claim', json={'side':'axis'}).status_code == 409
        assert other.post('/lan/seat/claim', json={'side':'allies'}).status_code == 200
        assert other.get('/lan/discovery').json()['open_seats'] == []
        assert player.post('/lan/auto-entry').status_code == 200  # rejoin, retains identity
        assert player.get('/lan/seat/state').json()['mine'] == 'axis'


def test_outside_overlay_subnet_never_gets_autojoin(env):
    with TestClient(env.app, client=('192.168.1.8', 1001)) as outsider:
        assert outsider.get('/lan/discovery').status_code == 404
        assert outsider.post('/lan/auto-entry').status_code == 404
        assert outsider.get('/lan/seat/state').status_code == 401
    with TestClient(env.app, client=('10.144.145.9', 1001)) as other_network:
        assert other_network.get('/lan/discovery').status_code == 404


def test_autojoin_requires_opt_in_and_no_bypass_of_old_invites(env, monkeypatch):
    monkeypatch.delenv('IBS_LAN_AUTOFIND')
    with TestClient(env.app, client=('10.144.144.2', 1001)) as client:
        assert client.get('/lan/discovery').status_code == 404
        assert client.post('/lan/auto-entry').status_code == 404
        assert client.post('/lan/entry', json={'ticket':'shared-invite'}).status_code == 200
        assert client.post('/lan/seat/claim', json={'side':'axis'}).status_code == 200


def test_autojoin_rejects_cross_site_request(env):
    with TestClient(env.app, client=('10.144.144.2', 1001)) as client:
        assert client.post('/lan/auto-entry', headers={'Origin': 'http://hostile.example'}).status_code == 403
        assert client.get('/lan/seat/state').status_code == 401


def test_malformed_config_fails_closed(env, monkeypatch):
    monkeypatch.setenv('IBS_LAN_AUTOFIND_CIDR', 'not-a-cidr')
    with TestClient(env.app, client=('10.144.144.2', 1001)) as client:
        assert client.get('/lan/discovery').status_code == 404
        assert client.post('/lan/auto-entry').status_code == 404

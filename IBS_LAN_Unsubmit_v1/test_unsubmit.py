import sys
from pathlib import Path
from types import SimpleNamespace
from dataclasses import dataclass, field
import copy
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lan_unseal import PendingSubmissionStore, UnsealError
from patch_unsubmit import patch_server, patch_frontend

BASE = Path(__file__).resolve().parent.parent / 'lan_server.py'


@dataclass
class FakeEvent:
    type: str
    payload: dict
    sequence: int


class FakeState:
    model_fields = {'game_id': None, 'turn': None, 'phase': None, 'submitted_orders': None,
                    'ships': None, 'events': None}

    def __init__(self, game_id='g1', turn=3, phase='gunnery'):
        self.game_id = game_id
        self.turn = turn
        self.phase = SimpleNamespace(value=phase)
        self.submitted_orders = {}
        self.ships = {'s1': {'command_status': 'attached'}}
        self.events = [FakeEvent('game_created', {}, 1)]

    def model_dump(self, mode='json'):
        return dict(game_id=self.game_id, turn=self.turn, phase=self.phase.value,
                    submitted_orders=copy.deepcopy(self.submitted_orders),
                    ships=copy.deepcopy(self.ships), events=[vars(e).copy() for e in self.events])

    @classmethod
    def model_validate(cls, raw):
        s = cls(raw['game_id'], raw['turn'], raw['phase'])
        s.submitted_orders = copy.deepcopy(raw['submitted_orders'])
        s.ships = copy.deepcopy(raw['ships'])
        s.events = [FakeEvent(**e) for e in raw['events']]
        return s


class Engine:
    def _event(self, state, event_type, message, payload):
        state.events.append(FakeEvent(event_type, payload, len(state.events)+1))


class Repository:
    def __init__(self):
        self.saved = []
    def save(self, state):
        self.saved.append(state.model_dump())


def test_restore_only_unilateral(tmp_path):
    state = FakeState()
    store = PendingSubmissionStore(tmp_path / 'backend' / 'snapshot.json')
    draft = {'side': 'allies', 'movement': [{'ship_id': 's1', 'plan': '1'}]}
    store.prepare(state, 'allies', draft)
    state.submitted_orders['allies'] = draft
    state.ships['s1']['command_status'] = 'detaching'
    state.events.append(FakeEvent('orders_submitted', {'secret_side': 'allies'}, 2))
    assert store.can_retract(state, 'allies')
    assert not store.can_retract(state, 'axis')
    state.submitted_orders['axis'] = {'side':'axis'}
    assert not store.can_retract(state, 'allies')
    state.submitted_orders.pop('axis')
    repo = Repository()
    result = store.retract(state, 'allies', Engine(), repo)
    assert state.submitted_orders == {}
    assert state.ships['s1']['command_status'] == 'attached'
    assert [e.type for e in state.events] == ['game_created','orders_submitted','orders_retracted']
    assert result['draft'] == draft
    assert len(repo.saved) == 1
    assert not store.path.exists()


def test_reject_stale_stage_and_event(tmp_path):
    store=PendingSubmissionStore(tmp_path/'checkpoint')
    state=FakeState()
    store.prepare(state, 'axis', {'side':'axis'})
    state.submitted_orders['axis']={'side':'axis'}
    state.events.append(FakeEvent('orders_submitted', {'secret_side':'axis'}, 2))
    state.phase=SimpleNamespace(value='fire_end')
    assert not store.can_retract(state,'axis')
    try:
        store.retract(state,'axis',Engine(),Repository())
    except UnsealError:
        pass
    else: assert False


def test_patch_gateway_idempotent_and_crlf():
    if not BASE.exists():
        return
    base=BASE.read_text(encoding='utf8')
    for orig in (base, base.replace('\n','\r\n')):
        patched=patch_server(orig)
        assert patched.count("@app.post('/lan/retract-orders')") == 1
        assert patched==patch_server(patched)
        assert "_unseal_store.prepare" in patched
        if '\r\n' in orig: assert '\r\n' in patched


def test_patch_frontend():
    example='''import { useEffect, useMemo, useState } from "react";
const LAN_MODE = true;
export default function App() {
  const [draft, setDraft] = useState("");
    if (view && game && orderPhases.has(view.phase) && !view.own_orders_submitted) {
        setDraft("");
      suggestedOrders(game, side, guideProfiles[side])
        .then((batch) => {
          if (active) setDraft(JSON.stringify(batch, null, 2));
        })
        .catch(() => {
          if (active)
            setDraft(JSON.stringify(defaultBatch(view, side), null, 2));
        });
      legalActions(game, side)
    }
  const act = async () => {
  };
  return (<header>
              : "执行引擎裁决"}
          </button>
        )}
      </header>);
}
'''
    patched=patch_frontend(example)
    assert '取消封存' in patched
    assert 'retractedDraftRef.current' in patched
    assert patched==patch_frontend(patched)


def test_file_not_published(tmp_path):
    store=PendingSubmissionStore(tmp_path/'backend'/'lan-unseal-checkpoint.json')
    store.prepare(FakeState(),'axis',{'side':'axis'})
    assert not (tmp_path/'frontend'/'dist'/'lan-unseal-checkpoint.json').exists()


def test_realistic_detach_audit_and_restore(tmp_path):
    state=FakeState()
    store=PendingSubmissionStore(tmp_path/'checkpoint.json')
    store.prepare(state,'axis',{'side':'axis'})
    state.ships['s1']['command_status']='retreating'
    state.events.append(FakeEvent('ship_detached', {'ship_id':'s1'}, 2))
    state.events.append(FakeEvent('orders_submitted', {'secret_side':'axis'}, 3))
    state.submitted_orders['axis']={'side':'axis'}
    assert store.can_retract(state,'axis')
    store.retract(state,'axis',Engine(),Repository())
    assert state.ships['s1']['command_status']=='attached'
    assert [e.type for e in state.events][-2:]==['orders_submitted','orders_retracted']
    assert state.events[-1].sequence==4


def test_save_failure_does_not_modify_live_state(tmp_path):
    state=FakeState()
    store=PendingSubmissionStore(tmp_path/'checkpoint.json')
    store.prepare(state, 'axis', {'side':'axis'})
    state.submitted_orders['axis']={'side':'axis'}
    state.events.append(FakeEvent('orders_submitted', {'secret_side':'axis'}, 2))
    before=state.model_dump()
    class BrokenRepository:
        def save(self, value):
            raise OSError('disk full')
    try:
        store.retract(state,'axis',Engine(),BrokenRepository())
    except OSError:
        pass
    else: assert False
    assert state.model_dump()==before
    assert store.path.exists()

"""Online-test reinforcement regression tests against the uploaded source.

The minimal source upload intentionally omits the original PDF and full rules
CSV set. This test shell uses real engine phase, ship/order and YAML logic.
S10 night-v2 is a synthetic state-machine fixture; Q024 is never fabricated.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend/src'),str(ROOT)]
from iron_bottom_sound.engine import IronBottomEngine
from iron_bottom_sound.models import GameOptions,GameState,HexCoord,OrderBatch,Phase,ReinforcementOrder,Side
from iron_bottom_sound import savo,vela
from iron_bottom_sound.data import load_scenario,read_yaml,STRUCTURED


def game(sid, optional=False):
    e=object.__new__(IronBottomEngine)
    e.games={};e.initial_states={};e._base_rules=None;e._snapshot_tables={};e._gunnery_expect_cache={}
    opts=GameOptions();opts.optional_rules.s13_axis_apd_reinforcements=optional
    return e,e.reset('IBS-S-'+sid,options=opts)

def batch(side,s,entries=(),choice=None):
    return OrderBatch(side=Side(side),phase=s.phase,reinforcements=list(entries),reinforcement_entry_choice=HexCoord.from_label(choice) if choice else None)

def order(sid,loc,speed=0,heading=2):
    return ReinforcementOrder(ship_id=sid,entry_hex=HexCoord.from_label(loc),speed=speed,heading=heading)

def send(e,s,ally=None,axis=None):
    for o in (axis or batch('axis',s),ally or batch('allies',s)):
        v=e.submit_orders(s.game_id,o)
        assert v.valid,v.errors
    return e.advance(s.game_id)

def prepare(e,s,turn,dice=None):
    s.turn=turn;s.phase=Phase.REINFORCEMENT
    if dice:
        kind,val=dice
        setattr(e,'_roll_2d6' if kind=='2d6' else '_roll_d6',lambda _:val)
    e._prepare_guaranteed_reinforcements(s)

def start_s13(e,s,choice='L27'):
    send(e,s,ally=batch('allies',s,choice=choice))
    assert s.scenario_state['s13_entry_hex']==choice

def orders13(s,coords=('L27','M27','N27'),speed=5):
    return batch('allies',s,[order(sid,p,speed) for sid,p in zip(vela.ship_ids(s),coords)])

@pytest.mark.parametrize('sid,turn,passing', [('01',3,1),('02',4,1),('04',4,2),('08',4,1)])
def test_once_before_order(sid,turn,passing):
    e,s=game(sid);seen=[]
    def roll(_):seen.append(passing);return passing,passing
    e._roll_d6=roll;prepare(e,s,turn)
    assert len(seen)==1 and s.reinforcement_available and s.reinforcement_roll_done
    e._prepare_guaranteed_reinforcements(s)
    assert len(seen)==1
    assert e._reinforcement_candidates(s,Side.AXIS)['group_available']

@pytest.mark.parametrize('sid,turn,failure', [('01',3,2),('02',4,3),('04',4,3),('08',4,2)])
def test_failed_roll(sid,turn,failure):
    e,s=game(sid);prepare(e,s,turn,('d6',(failure,failure)))
    assert not s.reinforcement_available
    assert e.validate_orders(s.game_id,batch('axis',s)).valid

@pytest.mark.parametrize('sid,turn', [('05',2),('06',3)])
def test_guaranteed_no_die(sid,turn):
    e,s=game(sid);e._roll_d6=lambda _:pytest.fail('guaranteed die request')
    prepare(e,s,turn)
    assert s.reinforcement_available and s.reinforcement_roll_done
    assert any(ev.type=='reinforcement_available' for ev in s.events)


def test_s04_source_has_r6():
    d=load_scenario('IBS-S-04')
    assert d['reinforcements']['rule_id']=='IBS-S-04-R6'
    assert any(r['id']=='IBS-S-04-R6' for r in d['special_rules'])
    assert [r['name'] for r in d['reinforcements']['ships']]==['浜风','望月','三日月']


def test_ordered_column_and_printed_row_corridor():
    e,s=game('04');prepare(e,s,4,('d6',(1,1)))
    ids=[x['ship_id'] for x in e._reinforcement_candidates(s,Side.AXIS)['ships']]
    assert ids==[r['id'] for r in load_scenario('IBS-S-04')['reinforcements']['ships']]
    assert e._reinforcement_entry_legal(s,HexCoord.from_label('H27'))
    assert not e._reinforcement_entry_legal(s,HexCoord.from_label('H26'))
    assert not e._reinforcement_entry_legal(s,HexCoord.from_label('H28'))
    assert not e.validate_orders(s.game_id,batch('axis',s,[order(i,x) for i,x in zip(ids,['G27','I27','K27'])])).valid
    good=[order(i,x) for i,x in zip(ids,['G27','H27','I27'])]
    assert e.validate_orders(s.game_id,batch('axis',s,good)).valid
    good[1].heading=4
    assert not e.validate_orders(s.game_id,batch('axis',s,good)).valid
    e,s=game('05')
    assert e._reinforcement_entry_legal(s,HexCoord.from_label('HH12'))
    assert not e._reinforcement_entry_legal(s,HexCoord.from_label('GG12'))


def test_s13_optional_apds_only_when_selected():
    e,s=game('13')
    assert 'IBS-U-IJN-YUNAGI' not in s.ships
    e,optional=game('13',True)
    ids=('IBS-U-IJN-YUNAGI','IBS-U-IJN-FUMIZUKI','IBS-U-IJN-MATSU-KAZE')
    assert [optional.ships[i].position.label for i in ids]==['E3','E2','E1']
    with pytest.raises(ValueError,match='only be enabled'):
        game('04',True)


def test_s13_secret_precommit_and_enemy_observation():
    e,s=game('13')
    allies=e._reinforcement_candidates(s,Side.ALLIES)
    assert allies['needs_secret_choice'] and len(allies['entry_hexes'])==11
    assert 'needs_secret_choice' not in e._reinforcement_candidates(s,Side.AXIS)
    assert not e.validate_orders(s.game_id,batch('allies',s)).valid
    assert not e.validate_orders(s.game_id,batch('allies',s,choice='K27')).valid
    start_s13(e,s)
    event=next(ev for ev in s.events if ev.type=='reinforcement_entry_sealed')
    assert event.payload['secret_side']=='allies'
    assert not any(x.type=='reinforcement_entry_sealed' for x in e.observe(s.game_id,Side.AXIS).recent_events)
    assert any(x.type=='reinforcement_entry_sealed' for x in e.observe(s.game_id,Side.ALLIES).recent_events)

@pytest.mark.parametrize('optional,rolled,success',[(False,9,False),(False,10,True),(False,11,True),(False,12,False),(True,8,False),(True,9,True),(True,10,True),(True,11,True),(True,12,True)])
def test_s13_dice_variations(optional,rolled,success):
    e,s=game('13',optional);start_s13(e,s);calls=[]
    def rng(_):calls.append(rolled);return rolled,[1,rolled-1]
    e._roll_2d6=rng;prepare(e,s,2)
    assert s.reinforcement_available is success
    assert bool(s.scenario_state.get('s13_arrival_turn')) is success
    e._prepare_guaranteed_reinforcements(s)
    assert len(calls)==1


def test_s13_repeated_failures_then_eighth_guarantee():
    e,s=game('13');start_s13(e,s);calls=[]
    def rng(_):calls.append(1);return 3,[1,2]
    e._roll_2d6=rng
    for turn in range(2,8):
        prepare(e,s,turn)
        assert not s.reinforcement_available
    assert len(calls)==6
    e._roll_2d6=lambda _:pytest.fail('no eighth turn die')
    prepare(e,s,8)
    assert s.reinforcement_available and s.scenario_state['s13_arrival_turn']==8
    assert all(s.ships[sid].reinforcement_turn==8 for sid in vela.ship_ids(s))


def test_s13_early_entry_seal_validation_and_persistence():
    e,s=game('13');start_s13(e,s);prepare(e,s,2,('2d6',(10,[4,6])))
    ids=[row['ship_id'] for row in e._reinforcement_candidates(s,Side.ALLIES)['ships']]
    assert ids==vela.ship_ids(s)
    assert e.validate_orders(s.game_id,orders13(s)).valid
    for wrong in (orders13(s,('M27','N27','O27')),orders13(s,speed=4),orders13(s,('L27','M27','O27'))):
        assert not e.validate_orders(s.game_id,wrong).valid
    send(e,s,ally=orders13(s))
    assert s.scenario_state['s13_arrived'] and s.phase==Phase.MOVEMENT_PLANNING
    assert [s.ships[sid].position.label for sid in ids]==['L27','M27','N27']
    assert [s.ships[sid].current_speed for sid in ids]==[5]*3
    restored=GameState.model_validate_json(s.model_dump_json())
    assert restored.scenario_state['s13_arrived']
    assert [restored.ships[sid].position.label for sid in ids]==['L27','M27','N27']


def test_s13_reverse_edge_column():
    e,s=game('13');start_s13(e,s,choice='V27');prepare(e,s,8)
    assert e.validate_orders(s.game_id,orders13(s,('V27','U27','T27'))).valid
    assert not e.validate_orders(s.game_id,orders13(s,('V27','U27','S27'))).valid


def test_no_roll_after_seal():
    e,s=game('04');prepare(e,s,4,('d6',(1,1)))
    ids=[row['ship_id'] for row in e._reinforcement_candidates(s,Side.AXIS)['ships']]
    e._roll_d6=lambda _:pytest.fail('post-seal roll')
    send(e,s,axis=batch('axis',s,[order(i,x) for i,x in zip(ids,['G27','H27','I27'])]))
    assert [s.ships[sid].position.label for sid in ids]==['G27','H27','I27']


def synthetic_savo():
    e,s=game('10');s.options.ruleset_version='night-v2'
    cfg=json.loads(json.dumps(read_yaml(STRUCTURED/'rules/night-v2.yaml'),default=str))
    s.rule_snapshot={'night':cfg,'scenario':load_scenario('IBS-S-10')}
    savo.initialize(s)
    return e,s


def test_savo_canonical_blocker_kept():
    e,s=synthetic_savo()
    blockers=s.rule_snapshot['night']['savo']['blockers']
    assert blockers[0]['id']=='IBS-Q-024'
    s.scenario_state['rule_blockers']=blockers
    with pytest.raises(ValueError,match='IBS-Q-024'):
        e.advance(s.game_id)

@pytest.mark.parametrize('rolled,groups',[(2,['australia','eastern','talbot']),(3,['australia','eastern','blue']),(4,['australia','eastern','blue']),(5,[]),(6,[]),(7,[]),(8,[]),(9,[]),(10,['australia']),(11,['australia','talbot']),(12,['talbot','blue'])])
def test_savo_2d6_all_outcomes(rolled,groups):
    e,s=synthetic_savo();prepare(e,s,2,('2d6',(rolled,[1,rolled-1])))
    assert s.scenario_state['savo_available_groups']==groups
    e._prepare_guaranteed_reinforcements(s)
    assert len([ev for ev in s.events if ev.type=='savo_reinforcement_roll'])==1


def test_savo_no_reappearing_group_and_eastern_uniform():
    e,s=synthetic_savo();s.scenario_state['savo_arrived_groups']=['australia','talbot']
    prepare(e,s,2,('2d6',(2,[1,1])))
    assert s.scenario_state['savo_available_groups']==['eastern']
    ids=[row['ship_id'] for row in e._reinforcement_candidates(s,Side.ALLIES)['ships']]
    assert len(ids)==4
    good=[order(i,'HH'+str(j),3) for i,j in zip(ids,[3,4,5,6])]
    assert e.validate_orders(s.game_id,batch('allies',s,good)).valid
    good[2].speed=4
    assert not e.validate_orders(s.game_id,batch('allies',s,good)).valid
    good[2].speed=3;good[2].entry_hex=HexCoord.from_label('HH8')
    assert not e.validate_orders(s.game_id,batch('allies',s,good)).valid


def test_savo_multiple_tulagi_sources():
    e,s=synthetic_savo()
    s.scenario_state['tulagi_triggers']=[{'ship_id':name,'turn':3,'position':HexCoord.from_label(p).model_dump()} for name,p in [('A','A1'),('B','A26')]]
    prepare(e,s,3,('2d6',(7,[3,4])))
    assert s.scenario_state['savo_available_groups']==['tulagi']
    rows=e._reinforcement_candidates(s,Side.ALLIES)['ships']
    assert len(rows)==3
    assert {'A1','A26'}<=set(rows[0]['entry_hexes'])


def test_generic_bridge_correct_owner():
    from lan_dice import _identify_roll
    e,s=game('04');contexts=[]
    def rng(_):contexts.append(_identify_roll('1D6',s));return 2,2
    e._roll_d6=rng;prepare(e,s,4)
    assert contexts[0]['owner']=='axis'
    assert 'IBS-S-04-R6' in contexts[0]['rule']['title']


def test_s13_bridge_2d6_correct_owner():
    from lan_dice import _identify_roll
    e,s=game('13',True);start_s13(e,s);contexts=[]
    def rng(_):contexts.append(_identify_roll('2D6',s));return 9,[3,6]
    e._roll_2d6=rng;prepare(e,s,2)
    assert contexts[0]['owner']=='allies'
    assert 'IBS-S-13-R2' in contexts[0]['rule']['title']


def test_yaml_source_rule_ids():
    for sid,rid in [('01','R5'),('02','R4'),('04','R6'),('05','R4'),('06','R2'),('08','R3'),('13','R2')]:
        d=load_scenario('IBS-S-'+sid)
        assert d['reinforcements']['rule_id']==f'IBS-S-{sid}-{rid}'
        assert any(row['id']==d['reinforcements']['rule_id'] for row in d['special_rules'])


def test_s13_optional_success_values_are_consistent_with_live_state():
    _,normal=game('13');_,optional=game('13',True)
    assert normal.reinforcement_succeeds_on==(10,11)
    assert optional.reinforcement_succeeds_on==(9,10,11,12)
    assert 's13_axis_apd_reinforcements' in load_scenario('IBS-S-13')['available_optional_rules']


def test_savo_cross_side_conflicting_edge_order_rejected_before_seal():
    e,s=synthetic_savo()
    axis=next(ship for ship in s.ships.values() if ship.side==Side.AXIS and ship.position)
    axis.position=None
    s.scenario_state['savo_exits']={axis.id:{'turn':0,'kind':'reward_exit','position':HexCoord.from_label('A21').model_dump()}}
    prepare(e,s,2,('2d6',(12,[6,6])))
    allied=e._reinforcement_candidates(s,Side.ALLIES)['ships']
    allied_orders=[order(row['ship_id'],'A21' if row['group']=='blue' else 'A1') for row in allied]
    japanese_orders=[order(axis.id,'A21')]
    assert e.submit_orders(s.game_id,batch('axis',s,japanese_orders)).valid
    assert e.submit_orders(s.game_id,batch('allies',s,allied_orders)).valid
    with pytest.raises(ValueError,match='same reinforcement entry hex'):
        e.advance(s.game_id)
    assert not s.sealed_orders
    assert s.ships[axis.id].position is None


def test_s13_early_success_does_not_reroll_next_turn():
    e,s=game('13');start_s13(e,s)
    prepare(e,s,2,('2d6',(11,[5,6])))
    assert s.reinforcement_arrival_turn==2
    e._roll_2d6=lambda _:pytest.fail('no future rolls after success')
    prepare(e,s,3)
    assert s.scenario_state['s13_arrival_turn']==2


@pytest.mark.parametrize('style', ['deterministic', 'random', 'tactical'])
def test_ai_seals_s13_secret_entry(style):
    from iron_bottom_sound.llm import DeterministicCommander
    from iron_bottom_sound.randomai import RandomCommander
    from iron_bottom_sound.tactical import TacticalCommander
    cls={'deterministic':DeterministicCommander,'random':RandomCommander,'tactical':TacticalCommander}[style]
    e,s=game('13')
    _, orders, _ = cls().choose_plan(e,s.game_id,Side.ALLIES)
    assert not orders.reinforcements
    assert orders.reinforcement_entry_choice is not None
    assert e.validate_orders(s.game_id,orders).valid
    e.submit_orders(s.game_id,orders)
    e.submit_orders(s.game_id,batch('axis',s))
    e.advance(s.game_id)
    prepare(e,s,2,('2d6',(10,[4,6])))
    _, orders, _ = cls().choose_plan(e,s.game_id,Side.ALLIES)
    assert len(orders.reinforcements)==3
    assert e.validate_orders(s.game_id,orders).valid
    assert all(x.speed==5 for x in orders.reinforcements)


@pytest.mark.parametrize('style', ['deterministic', 'random', 'tactical'])
def test_ai_ordered_column_s04(style):
    from iron_bottom_sound.llm import DeterministicCommander
    from iron_bottom_sound.randomai import RandomCommander
    from iron_bottom_sound.tactical import TacticalCommander
    cls={'deterministic':DeterministicCommander,'random':RandomCommander,'tactical':TacticalCommander}[style]
    e,s=game('04');prepare(e,s,4,('d6',(2,2)))
    _, orders, _=cls().choose_plan(e,s.game_id,Side.AXIS)
    assert len(orders.reinforcements)==3
    assert e.validate_orders(s.game_id,orders).valid


def test_ai_savo_eastern_group_correct():
    from iron_bottom_sound.reinforcement_orders import propose
    import random
    e,s=synthetic_savo()
    s.scenario_state['savo_arrived_groups']=['australia','talbot']
    prepare(e,s,2,('2d6',(2,[1,1])))
    for rng in (None,random.Random(57)):
        orders,choice=propose(e,s,Side.ALLIES,rng)
        assert choice is None and len(orders)==4
        assert e.validate_orders(s.game_id,batch('allies',s,orders)).valid


def _lan_config_normalizer():
    # Source-only upload has no complete production rules tables, so importing
    # lan_server would boot the API prematurely. Extract the pure validator AST.
    import ast
    import re
    from fastapi import HTTPException
    tree=ast.parse((ROOT/'lan_server.py').read_text(encoding='utf-8'))
    optional=next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OPTIONAL_RULES' for t in node.targets))
    target=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='normalize_configuration')
    module=ast.Module(body=[target],type_ignores=[])
    ast.fix_missing_locations(module)
    scope={'OPTIONAL_RULES':optional,'HTTPException':HTTPException,'re':re}
    exec(compile(module,'lan_server.py','exec'),scope)
    return scope['normalize_configuration'],optional


def test_lan_old_options_backward_compatible():
    normalize,options=_lan_config_normalizer()
    request={'scenario_id':'IBS-S-13','seed':11,'optional_rules':{key:False for key in options[:-1]},
             'squall_hexes':[],'radar_1942_variant':False,'realistic_command':False,'battle_report':False}
    normalized=normalize(request)
    assert normalized['optional_rules']['s13_axis_apd_reinforcements'] is False
    normalized['optional_rules']['s13_axis_apd_reinforcements']=True
    assert normalize(normalized)['optional_rules']['s13_axis_apd_reinforcements'] is True
    normalized['scenario_id']='IBS-S-04'
    with pytest.raises(Exception,match='日军APD'):
        normalize(normalized)


def test_generic_candidates_never_offer_occupied_or_impassable_cells():
    e, state = game('04')
    prepare(e, state, 4, ('d6', (1, 1)))
    baseline = set(e._reinforcement_candidates(state, Side.AXIS)['entry_hexes'])
    assert baseline
    occupied = next(iter(sorted(baseline)))
    ship = next(ship for ship in state.ships.values() if ship.position is not None)
    ship.position = HexCoord.from_label(occupied)
    choices = e._reinforcement_candidates(state, Side.AXIS)['entry_hexes']
    assert occupied not in choices
    assert all(not e._terrain_impassable(state, HexCoord.from_label(label)) for label in choices)


def test_s13_corrupt_saved_anchor_fails_validation_without_exception():
    e, state = game('13')
    start_s13(e, state)
    state.scenario_state['s13_entry_hex'] = 'XX27'
    prepare(e, state, 8)
    result = e.validate_orders(state.game_id, orders13(state))
    assert not result.valid
    assert any('pre-committed secret hex' in error for error in result.errors)


def test_s01_trigger_turn_is_not_arrival_turn():
    e, state = game('01')
    calls = []
    def roll(_):
        calls.append(1)
        return 1, 1
    e._roll_d6 = roll
    prepare(e, state, 3)
    assert not e._reinforcement_candidates(state, Side.AXIS)['ships']
    prepare(e, state, 4)
    assert len(calls) == 1
    assert len(e._reinforcement_candidates(state, Side.AXIS)['ships']) == 8
    assert state.reinforcement_available

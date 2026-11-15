"""Scenario 13 (IBS-S-13-R2/R3) reinforcement state machine.

The Allies seal the entry anchor in the first reinforcement phase, before any
reinforcement roll.  A 2D6 check runs at the *start* of turns 2..7; turn 8 is
guaranteed.  All parameters and ship order come from the scenario definition.
"""
from __future__ import annotations

from .data import load_scenario
from .models import DiceRoll, HexCoord, Phase, Side


def enabled(state):
    return state.scenario_id == "IBS-S-13"


def rules(state):
    return (state.rule_snapshot.get("scenario") or load_scenario(state.scenario_id))["reinforcements"]


def ship_ids(state):
    return [ship["id"] for ship in rules(state)["ships"]]


def corridor(engine, state):
    start, end = [HexCoord.from_label(x) for x in rules(state)["arrival"]["entry_hex_range"]]
    # Printed L27–V27 is a *map-row edge*, not the cube-linear interpolation
    # (which drifts into O28/S28 on odd columns).
    start_row, end_row = start.r + start.q // 2, end.r + end.q // 2
    if start_row != end_row:
        raise ValueError("S-13 source entry range must be a single printed edge row")
    return [HexCoord(q=q, r=start_row - q // 2)
            for q in range(min(start.q, end.q), max(start.q, end.q) + 1)]


def prepare(engine, state):
    if not enabled(state) or state.phase != Phase.REINFORCEMENT:
        return
    if state.scenario_state.get("s13_arrived"):
        state.reinforcement_available = False
        return
    cfg = rules(state)
    trigger = cfg["trigger"]
    if state.scenario_state.get("s13_roll_turn") == state.turn:
        return
    if state.scenario_state.get("s13_arrival_turn"):
        # Once rolled successfully, the group enters in that same turn.
        return
    if state.turn == int(trigger["guaranteed_turn"]):
        state.reinforcement_available = state.reinforcement_roll_done = True
        state.scenario_state["s13_arrival_turn"] = state.turn
        state.reinforcement_arrival_turn = state.turn
        for sid in ship_ids(state):
            state.ships[sid].reinforcement_turn = state.turn
        engine._event(state, "reinforcement_available", "韦拉拉韦拉：第8回合增援必达（不掷骰）",
            payload={"available": True, "arrival_turn": state.turn, "automatic": True},
            rule=engine._scenario_rule(cfg["rule_id"], 14, "第8回合保底入场"))
        return
    if not int(trigger["from_turn"]) <= state.turn <= int(trigger["through_turn"]):
        return
    raw, dice = engine._roll_2d6(state)
    successes = (trigger["optional_succeeds_on"] if state.options.optional_rules.s13_axis_apd_reinforcements
                 else trigger["succeeds_on"])
    success = raw in successes
    state.scenario_state["s13_roll_turn"] = state.turn
    state.reinforcement_roll_done = True
    state.reinforcement_available = success
    if success:
        state.scenario_state["s13_arrival_turn"] = state.turn
        state.reinforcement_arrival_turn = state.turn
        for sid in ship_ids(state):
            state.ships[sid].reinforcement_turn = state.turn
    engine._event(state, "reinforcement_roll", f"韦拉拉韦拉第{state.turn}回合 2D6：{raw}（{'成功' if success else '未到达'}）",
        payload={"roll": raw, "available": success, "successes": list(successes)},
        dice=DiceRoll(dice=dice, notation="2D6", raw=raw),
        rule=engine._scenario_rule(cfg["rule_id"], 14, "逐回合2D6增援"))


def candidates(engine, state, side, base):
    if not enabled(state) or side != Side.ALLIES:
        return base
    trigger = rules(state)["trigger"]
    base["succeeds_on"] = list(trigger["optional_succeeds_on"] if state.options.optional_rules.s13_axis_apd_reinforcements
                                  else trigger["succeeds_on"])
    if state.turn == 1:
        base.update(ships=[], group_available=False, needs_secret_choice=True,
                    entry_hexes=[p.label for p in corridor(engine, state)],
                    entry_range=rules(state)["arrival"]["entry_hex_range"])
    if state.scenario_state.get("s13_entry_hex"):
        base["chosen_entry_hex"] = state.scenario_state["s13_entry_hex"]
    if base["group_available"] and base["ships"]:
        by_id = {item["ship_id"]: item for item in base["ships"]}
        base["ships"] = [by_id[sid] for sid in ship_ids(state) if sid in by_id]
        # A pre-committed anchor stays visible only to the Allies.
        base["chosen_entry_hex"] = state.scenario_state.get("s13_entry_hex")
        base["entry_hexes"] = [p.label for p in corridor(engine, state)]
        base["required_speed"] = int(rules(state)["arrival"]["speed"])
        base["required_column"] = True
    return base


def validate(engine, state, batch):
    errors = []
    choice = batch.reinforcement_entry_choice
    if state.phase != Phase.REINFORCEMENT:
        if choice is not None:
            errors.append("S-13 entry anchor can only be sealed in the reinforcement phase")
        return errors
    if state.turn == 1 and batch.side == Side.ALLIES:
        if choice is None or choice.label not in {p.label for p in corridor(engine, state)}:
            errors.append("S-13 Allies must secretly select an entry hex in L27–V27 on turn 1")
    elif choice is not None:
        errors.append("S-13 entry anchor may only be selected once by Allies on turn 1")
    if batch.side != Side.ALLIES or not batch.reinforcements:
        return errors
    expected = ship_ids(state)
    if set(o.ship_id for o in batch.reinforcements) != set(expected):
        # General validation also covers missing/excess ships, but fail closed here.
        errors.append("S-13 reinforcement must enter as the complete three-ship column")
        return errors
    by_ship = {o.ship_id: o for o in batch.reinforcements}
    if len(by_ship) != len(batch.reinforcements):
        errors.append("S-13 duplicate ship entry")
        return errors
    orders = [by_ship[sid] for sid in expected]
    if len({o.heading for o in orders}) != 1 or any(o.speed != int(rules(state)["arrival"]["speed"]) for o in orders):
        errors.append("S-13 reinforcements must share a heading and enter at speed 5")
    anchor = state.scenario_state.get("s13_entry_hex")
    cells = [p.label for p in corridor(engine, state)]
    if anchor not in cells or orders[0].entry_hex.label != anchor:
        errors.append("S-13 first destroyer must enter at the pre-committed secret hex")
        return errors
    i = cells.index(anchor)
    labels = [o.entry_hex.label for o in orders]
    valid = any(0 <= i + direction*(len(orders)-1) < len(cells) and
                labels == [cells[i + direction*j] for j in range(len(orders))]
                for direction in (-1, 1))
    if not valid:
        errors.append("S-13 destroyers must form a continuous ordered column from the secret entry hex")
    return errors


def resolve(engine, state):
    if state.turn == 1:
        ally = next(b for b in engine._sealed_batches(state, Phase.REINFORCEMENT) if b.side == Side.ALLIES)
        state.scenario_state["s13_entry_hex"] = ally.reinforcement_entry_choice.label
        engine._event(state, "reinforcement_entry_sealed", "盟军已秘密选定增援入场格",
            payload={"secret_side": Side.ALLIES.value, "entry_hex": ally.reinforcement_entry_choice.label},
            rule=engine._scenario_rule(rules(state)["rule_id"], 14, "盟军秘密选择入场格"))
    elif state.reinforcement_available and state.scenario_state.get("s13_arrival_turn") == state.turn:
        if all(state.ships[sid].position for sid in ship_ids(state)):
            state.scenario_state["s13_arrived"] = True

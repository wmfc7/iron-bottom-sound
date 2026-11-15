"""AI reinforcement orders from the engine's side-specific legal candidates.

No unit/location rules are copied here: special scenarios own the candidate
interface and the engine remains the sole authority for validation.
"""
from __future__ import annotations

import random

from .models import HexCoord, ReinforcementOrder, Side


def propose(engine, state, side: Side, rng: random.Random | None = None):
    """Return (reinforcement orders, sealed S-13 choice); never inspect enemy choices."""
    candidates = engine._reinforcement_candidates(state, side)
    if candidates.get('needs_secret_choice'):
        choices = candidates.get('entry_hexes', [])
        if not choices:
            return [], None
        # A non-edge choice accommodates the three-ship ordered column on either side.
        choice = rng.choice(choices[2:-2] or choices) if rng else choices[len(choices)//2]
        return [], HexCoord.from_label(choice)

    rows = candidates.get('ships', [])
    if not candidates.get('group_available') or not rows:
        return [], None
    groups: dict[str, list[dict]] = {}
    for index, item in enumerate(rows):
        if item.get('group'):
            group = item['group']
        elif candidates.get('required_column'):
            group = 'single_column'
        else:
            group = f'generic_{index}'
        groups.setdefault(group, []).append(item)
    # The candidate interface has already excluded occupied/illegal hexes.
    # Do not inspect the opposing side's private ship positions from AI code.
    used: set[str] = set()
    orders: list[ReinforcementOrder] = []
    for group, ships in groups.items():
        entry_sets = [set(item.get('entry_hexes') or candidates.get('entry_hexes', [])) - used for item in ships]
        # A single column must occupy adjacent map hexes; other groups may fan out.
        column = candidates.get('required_column') or group == 'eastern'
        anchor = candidates.get('chosen_entry_hex') if column else None
        if column:
            shared = set.intersection(*entry_sets) if entry_sets else set()
            cells = sorted((HexCoord.from_label(s) for s in shared), key=lambda h: (h.q, h.r + h.q//2))
            chains = []
            if anchor:
                starts = [p for p in cells if p.label == anchor]
                for first in starts:
                    for reverse in (False, True):
                        sequence = sorted(cells, key=lambda h: (h.q, h.r + h.q//2), reverse=reverse)
                        offset = sequence.index(first)
                        segment = sequence[offset:offset+len(ships)]
                        if len(segment) == len(ships) and all(a.distance(b) == 1 for a,b in zip(segment,segment[1:])):
                            chains.append(segment)
            else:
                for reverse in (False, True):
                    sequence = list(reversed(cells)) if reverse else cells
                    for offset in range(len(sequence)-len(ships)+1):
                        segment = sequence[offset:offset+len(ships)]
                        if all(a.distance(b) == 1 for a,b in zip(segment,segment[1:])):
                            chains.append(segment)
            if not chains:
                # Do not fabricate an illegal plan; engine validates incomplete mandatory groups.
                continue
            places = (rng.choice(chains) if rng else chains[0])
        else:
            places = []
            for available in entry_sets:
                pool = sorted(available)
                if not pool:
                    break
                label = rng.choice(pool) if rng else pool[0]
                places.append(HexCoord.from_label(label))
                used.add(label)
            if len(places) != len(ships):
                continue
        speed = candidates.get('required_speed')
        if speed is None:
            speed = 0
        heading = rng.randint(1, 6) if rng else 1
        for row, place in zip(ships, places):
            # All members of the S-10 eastern force enter at the same speed and heading.
            item_speed = min(int(speed), int(row['max_speed']))
            orders.append(ReinforcementOrder(ship_id=row['ship_id'], entry_hex=place,
                                              heading=heading, speed=item_speed))
            used.add(place.label)
    return orders, None

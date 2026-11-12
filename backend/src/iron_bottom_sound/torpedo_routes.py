"""IBS-R-08.2.3: Launch from the ship's *actual* MF hex.

The first torpedo movement enters the appropriate adjacent lateral hex;
subsequent movement uses a fixed course.  The first step is NOT a free
zero-time displacement, and it costs one movement step and one hex of range.

The directions below are relative to the *ship's heading at launch*:
  Port A: -1,-1...  Port B: -2,-1,-1...  Port X: -1,-2,-2...  Port Y: -2,-2...
  Stbd A: +1,+1...  Stbd B: +2,+1,+1...  Stbd X: +1,+2,+2...  Stbd Y: +2,+2...
Negative/positive rotation uses the engine's 1..6 clockwise numbering.
"""
from __future__ import annotations


def wrap_heading(heading: int) -> int:
    if not isinstance(heading, int) or not 1 <= heading <= 6:
        raise ValueError('ship heading must be in 1..6')
    return heading


def launch_headings(ship_heading: int, side: str, angle: str) -> tuple[int, int]:
    """Return (heading for FIRST paid hex step, fixed heading thereafter)."""
    wrap_heading(ship_heading)
    if side not in ('port', 'starboard'):
        raise ValueError('launch side must be port or starboard')
    if angle not in ('A', 'B', 'X', 'Y'):
        raise ValueError('angle must be A, B, X or Y')
    sign = -1 if side == 'port' else 1
    first_offset = 1 if angle in ('A', 'X') else 2
    course_offset = 1 if angle in ('A', 'B') else 2
    return (((ship_heading - 1 + sign * first_offset) % 6) + 1,
            ((ship_heading - 1 + sign * course_offset) % 6) + 1)


def first_step_heading_from_course(
    ship_heading: int, course_heading: int, angle: str,
) -> int:
    """Recover launch side from the validated course, for preview functions.

    The old engine preview methods receive (ship heading, torpedo course,
    angle), not the side. The course has already been validated by its
    ``relative_heading`` rule table. Don't silently invent a side on bad data.
    """
    wrap_heading(ship_heading)
    wrap_heading(course_heading)
    if angle not in ('A', 'B', 'X', 'Y'):
        raise ValueError('Invalid torpedo angle')
    difference = (course_heading - ship_heading) % 6
    side = 'starboard' if difference in (1, 2) else 'port' if difference in (4, 5) else None
    if side is None:
        raise ValueError('Torpedo course does not match a firing side')
    first, predicted_course = launch_headings(ship_heading, side, angle)
    if predicted_course != course_heading:
        raise ValueError('Torpedo course and A/B/X/Y angle disagree')
    return first


def route_steps(ship_heading: int, side: str, angle: str, count: int) -> list[int]:
    """A pure reference oracle, useful for rules tests."""
    if count < 0:
        raise ValueError('step count must not be negative')
    first, fixed = launch_headings(ship_heading, side, angle)
    return ([first] + [fixed] * (count - 1)) if count else []

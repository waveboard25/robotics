"""Robot motion kinematics on grid."""

from __future__ import annotations

import math
from typing import Optional

from meshfleet.constants import BATTERY_DRAIN_PER_TICK, MAX_SPEED
from robots.state import RobotState


def step_toward(
    state: RobotState,
    target: tuple[int, int],
    orca_vel: Optional[tuple[float, float]] = None,
) -> RobotState:
    """Move one grid step toward target or apply ORCA velocity threshold."""
    cx, cy = state.position
    tx, ty = target

    if (cx, cy) == (tx, ty):
        state.velocity = (0.0, 0.0)
        state.intent = "STOP"
        return state

    if orca_vel and (abs(orca_vel[0]) < 0.1 and abs(orca_vel[1]) < 0.1):
        state.velocity = (0.0, 0.0)
        state.status = "YIELDING"
        state.intent = "YIELD"
        state.wait_ticks += 1
        return state

    dx = tx - cx
    dy = ty - cy
    nx, ny = cx, cy
    if abs(dx) >= abs(dy):
        nx = cx + (1 if dx > 0 else -1 if dx < 0 else 0)
    else:
        ny = cy + (1 if dy > 0 else -1 if dy < 0 else 0)

    state.position = (nx, ny)
    state.velocity = (float(nx - cx), float(ny - cy))
    state.heading = math.degrees(math.atan2(ny - cy, nx - cx)) if (nx != cx or ny != cy) else state.heading
    state.status = "MOVING"
    state.intent = "STRAIGHT"
    state.battery = max(0.0, state.battery - BATTERY_DRAIN_PER_TICK)
    return state


def hold_position(state: RobotState) -> RobotState:
    state.velocity = (0.0, 0.0)
    state.status = "YIELDING"
    state.intent = "YIELD"
    state.wait_ticks += 1
    return state

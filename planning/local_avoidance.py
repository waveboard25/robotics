"""Simplified ORCA local collision avoidance."""

from __future__ import annotations

import math
from typing import Optional

from meshfleet.constants import MAX_SPEED, ROBOT_RADIUS


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def compute_orca_velocity(
    pos: tuple[float, float],
    vel: tuple[float, float],
    preferred_vel: tuple[float, float],
    neighbors: list[tuple[tuple[float, float], tuple[float, float]]],
    time_horizon: float = 2.0,
) -> tuple[float, float]:
    """Return adjusted velocity avoiding neighbors. Simplified 2D ORCA."""
    if not neighbors:
        pref_mag = math.hypot(*preferred_vel)
        if pref_mag > MAX_SPEED:
            scale = MAX_SPEED / pref_mag
            return preferred_vel[0] * scale, preferred_vel[1] * scale
        return preferred_vel

    new_vel = preferred_vel
    combined_radius = 2 * ROBOT_RADIUS

    for npos, nvel in neighbors:
        rel_pos = (npos[0] - pos[0], npos[1] - pos[1])
        rel_vel = (vel[0] - nvel[0], vel[1] - nvel[1])
        dist = _dist((0, 0), rel_pos)

        if dist < combined_radius and dist > 1e-6:
            # Emergency separation
            scale = MAX_SPEED / dist
            new_vel = (-rel_pos[0] * scale * 0.5, -rel_pos[1] * scale * 0.5)
            continue

        if dist < 1e-6:
            new_vel = (0.0, 0.0)
            continue

        # Time to collision approximation
        rel_speed = _dist((0, 0), rel_vel)
        if rel_speed < 1e-6:
            continue

        ttc = (dist - combined_radius) / rel_speed
        if 0 < ttc < time_horizon:
            # Scale down preferred velocity
            factor = max(0.0, ttc / time_horizon)
            new_vel = (preferred_vel[0] * factor, preferred_vel[1] * factor)

    mag = math.hypot(*new_vel)
    if mag > MAX_SPEED:
        scale = MAX_SPEED / mag
        new_vel = (new_vel[0] * scale, new_vel[1] * scale)
    return new_vel


def grid_preferred_velocity(
    current: tuple[int, int],
    next_cell: Optional[tuple[int, int]],
) -> tuple[float, float]:
    if next_cell is None:
        return (0.0, 0.0)
    dx = next_cell[0] - current[0]
    dy = next_cell[1] - current[1]
    mag = math.hypot(dx, dy)
    if mag < 1e-6:
        return (0.0, 0.0)
    return (dx / mag * MAX_SPEED, dy / mag * MAX_SPEED)


def apply_orca_to_grid_move(
    pos: tuple[int, int],
    vel: tuple[float, float],
    next_cell: Optional[tuple[int, int]],
    peer_states: list[tuple[tuple[float, float], tuple[float, float]]],
) -> tuple[float, float]:
    pos_f = (float(pos[0]), float(pos[1]))
    pref = grid_preferred_velocity(pos, next_cell)
    return compute_orca_velocity(pos_f, vel, pref, peer_states)

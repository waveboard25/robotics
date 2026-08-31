"""Priority scoring for conflict resolution."""

from __future__ import annotations

from meshfleet.constants import W_INVERSE_DIST, W_URGENCY, W_WAIT_AGING
from robots.state import RobotState
from simulation.warehouse.grid import WarehouseGrid


def compute_priority(
    state: RobotState,
    grid: WarehouseGrid,
    goal: tuple[int, int] | None = None,
) -> float:
    goal = goal or state.goal
    dist = grid.manhattan(state.position, goal) if goal else 999
    inv_dist = 1.0 / max(dist, 1)
    aging = state.wait_ticks * 0.1
    return (
        W_URGENCY * state.task_urgency
        + W_INVERSE_DIST * inv_dist
        + W_WAIT_AGING * aging
    )


def should_yield(
    self_state: RobotState,
    other_state: RobotState,
    grid: WarehouseGrid,
) -> bool:
    self_prio = compute_priority(self_state, grid)
    other_prio = compute_priority(other_state, grid)
    if abs(self_prio - other_prio) < 1e-6:
        return self_state.robot_id > other_state.robot_id
    return self_prio < other_prio

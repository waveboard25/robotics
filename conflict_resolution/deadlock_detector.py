"""Local wait-for graph deadlock detection."""

from __future__ import annotations

from typing import Optional

from robots.state import RobotState


def detect_deadlock_cycle(
    self_id: str,
    waiting_on: dict[str, str],
) -> Optional[list[str]]:
    """Return cycle of robot IDs if self is in a wait-for cycle."""
    visited: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> Optional[list[str]]:
        if node in path:
            cycle_start = path.index(node)
            return path[cycle_start:] + [node]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        next_node = waiting_on.get(node)
        if next_node:
            result = dfs(next_node)
            if result:
                return result
        path.pop()
        return None

    if self_id not in waiting_on:
        return None
    return dfs(self_id)


def lowest_id_in_cycle(cycle: list[str]) -> str:
    return min(cycle)


def build_waiting_on(
    self_state: RobotState,
    blocked_by: Optional[str],
    peer_states: dict[str, RobotState],
) -> dict[str, str]:
    """Build wait-for graph edges from who blocks whom."""
    graph: dict[str, str] = {}
    if blocked_by:
        graph[self_state.robot_id] = blocked_by
    for rid, ps in peer_states.items():
        if ps.status == "YIELDING" and ps.wait_ticks > 0:
            # Heuristic: yielding robot waits on higher priority neighbor at same cell
            pass
    return graph

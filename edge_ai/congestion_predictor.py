"""Small, explainable edge congestion estimator.

It deliberately has no cloud/model dependency: each robot can derive the same
feature from its local map and peer telemetry, then use it while bidding.
"""

from __future__ import annotations

from simulation.warehouse.grid import WarehouseGrid


def predict_congestion(
    grid: WarehouseGrid,
    start: tuple[int, int],
    goal: tuple[int, int],
    peer_positions: list[tuple[int, int]] | None = None,
) -> float:
    """Estimate route pressure from choke points, blocks, and nearby traffic."""
    lo_x, hi_x = sorted((start[0], goal[0]))
    lo_y, hi_y = sorted((start[1], goal[1]))
    corridor = {
        (x, y)
        for x in range(lo_x, hi_x + 1)
        for y in range(lo_y, hi_y + 1)
    }
    chokepoints = len(corridor & (grid.choke_points | grid.intersections))
    blocked = len(corridor & grid.dynamic_blocked)
    nearby = sum(1 for p in peer_positions or [] if p in corridor)
    return 0.8 * chokepoints + 2.0 * blocked + 0.5 * nearby

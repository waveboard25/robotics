"""Task bidding cost model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from meshfleet.constants import (
    BATTERY_THRESHOLD,
    COST_W1_DISTANCE,
    COST_W2_CONGESTION,
    COST_W3_BATTERY,
    COST_W4_WORKLOAD,
    COST_W5_RISK,
    COST_W6_PROXIMITY,
)
from robots.state import RobotState
from simulation.warehouse.grid import WarehouseGrid


@dataclass
class CostWeights:
    distance: float = COST_W1_DISTANCE
    congestion: float = COST_W2_CONGESTION
    battery: float = COST_W3_BATTERY
    workload: float = COST_W4_WORKLOAD
    risk: float = COST_W5_RISK
    proximity: float = COST_W6_PROXIMITY


def compute_bid_cost(
    robot: RobotState,
    pickup: tuple[int, int],
    dropoff: tuple[int, int],
    grid: WarehouseGrid,
    congestion_penalty: float = 0.0,
    blocked_aisles: Optional[set[str]] = None,
    weights: Optional[CostWeights] = None,
) -> float:
    weights = weights or CostWeights()
    blocked_aisles = blocked_aisles or set()

    if robot.battery < BATTERY_THRESHOLD:
        return float("inf")

    dist_pickup = grid.manhattan(robot.position, pickup)
    dist_total = dist_pickup + grid.manhattan(pickup, dropoff)

    battery_penalty = 0.0
    if robot.battery < BATTERY_THRESHOLD * 2:
        battery_penalty = (BATTERY_THRESHOLD * 2 - robot.battery) * 0.5

    workload_penalty = robot.queued_tasks * 2.0

    risk_penalty = 0.0
    for aisle_id in blocked_aisles:
        for cell in grid.aisle_labels.get(aisle_id, []):
            if cell in {pickup, dropoff}:
                risk_penalty += 10.0

    proximity_bonus = 0.0
    if dist_pickup <= 3:
        proximity_bonus = 2.0

    return (
        weights.distance * dist_total
        + weights.congestion * congestion_penalty
        + weights.battery * battery_penalty
        + weights.workload * workload_penalty
        + weights.risk * risk_penalty
        - weights.proximity * proximity_bonus
    )

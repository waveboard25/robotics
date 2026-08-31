"""Decentralized auction — Contract Net Protocol."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from robots.state import RobotState, TaskSpec
from simulation.warehouse.grid import WarehouseGrid
from task_allocation.cost_model import compute_bid_cost


@dataclass
class AuctionState:
    task_id: str
    pickup: tuple[int, int]
    dropoff: tuple[int, int]
    urgency: float
    deadline_tick: Optional[int]
    bids: dict[str, float] = field(default_factory=dict)
    winner: Optional[str] = None
    closed: bool = False
    announce_tick: int = 0


@dataclass
class AuctionManager:
    open_auctions: dict[str, AuctionState] = field(default_factory=dict)
    awarded_tasks: dict[str, str] = field(default_factory=dict)  # task_id -> robot_id

    def announce_task(self, task: TaskSpec, tick: int) -> AuctionState:
        auction = AuctionState(
            task_id=task.task_id,
            pickup=task.pickup,
            dropoff=task.dropoff,
            urgency=task.urgency,
            deadline_tick=task.deadline_tick,
            announce_tick=tick,
        )
        self.open_auctions[task.task_id] = auction
        return auction

    def compute_local_bid(
        self,
        robot: RobotState,
        auction: AuctionState,
        grid: WarehouseGrid,
        congestion_penalty: float = 0.0,
        blocked_aisles: Optional[set[str]] = None,
    ) -> float:
        if robot.status not in ("IDLE", "MOVING") and robot.current_task:
            if robot.battery >= 20:
                pass
        if robot.current_task and robot.status == "MOVING":
            return float("inf")
        return compute_bid_cost(
            robot,
            auction.pickup,
            auction.dropoff,
            grid,
            congestion_penalty=congestion_penalty,
            blocked_aisles=blocked_aisles,
        )

    def submit_bid(self, task_id: str, robot_id: str, cost: float) -> None:
        auction = self.open_auctions.get(task_id)
        if auction and not auction.closed:
            auction.bids[robot_id] = cost

    def record_peer_bid(self, task_id: str, robot_id: str, cost: float) -> None:
        auction = self.open_auctions.get(task_id)
        if auction and not auction.closed:
            auction.bids[robot_id] = cost

    def determine_winner(self, task_id: str) -> Optional[str]:
        auction = self.open_auctions.get(task_id)
        if not auction or not auction.bids:
            return None
        winner = min(auction.bids.items(), key=lambda x: (x[1], x[0]))
        auction.winner = winner[0]
        auction.closed = True
        self.awarded_tasks[task_id] = winner[0]
        return winner[0]

    def is_task_taken(self, task_id: str) -> bool:
        return task_id in self.awarded_tasks

    def task_owner(self, task_id: str) -> Optional[str]:
        return self.awarded_tasks.get(task_id)


def nearest_robot_assignment(
    task: TaskSpec,
    robots: dict[str, RobotState],
    grid: WarehouseGrid,
) -> Optional[str]:
    """MVP fallback: nearest idle robot."""
    best_id: Optional[str] = None
    best_dist = float("inf")
    for rid, state in robots.items():
        if state.current_task or state.status == "OFFLINE":
            continue
        d = grid.manhattan(state.position, task.pickup)
        if d < best_dist:
            best_dist = d
            best_id = rid
    return best_id

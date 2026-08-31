"""Robot state representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RobotState:
    robot_id: str
    seq: int = 0
    tick: int = 0
    position: tuple[int, int] = (0, 0)
    velocity: tuple[float, float] = (0.0, 0.0)
    heading: float = 0.0
    battery: float = 100.0
    status: str = "IDLE"  # IDLE | MOVING | YIELDING | CHARGING | OFFLINE
    current_task: Optional[str] = None
    intent: str = "STOP"
    next_waypoints: list[tuple[int, int]] = field(default_factory=list)
    priority_score: float = 0.0
    reservation_horizon_id: int = 0
    wait_ticks: int = 0
    goal: Optional[tuple[int, int]] = None
    task_urgency: float = 1.0
    queued_tasks: int = 0

    def copy(self) -> "RobotState":
        return RobotState(
            robot_id=self.robot_id,
            seq=self.seq,
            tick=self.tick,
            position=self.position,
            velocity=self.velocity,
            heading=self.heading,
            battery=self.battery,
            status=self.status,
            current_task=self.current_task,
            intent=self.intent,
            next_waypoints=list(self.next_waypoints),
            priority_score=self.priority_score,
            reservation_horizon_id=self.reservation_horizon_id,
            wait_ticks=self.wait_ticks,
            goal=self.goal,
            task_urgency=self.task_urgency,
            queued_tasks=self.queued_tasks,
        )


@dataclass
class TaskSpec:
    task_id: str
    pickup: tuple[int, int]
    dropoff: tuple[int, int]
    urgency: float = 1.0
    deadline_tick: Optional[int] = None

    @property
    def goal_for_phase(self) -> tuple[int, int]:
        return self.pickup

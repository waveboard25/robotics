"""Deterministic, headless warehouse simulator used by tests and benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from edge_ai.congestion_predictor import predict_congestion
from planning.global_planner import grid_astar, space_time_astar
from planning.reservation_table import ReservationTable
from robots.state import RobotState, TaskSpec
from simulation.engine.metrics import FleetMetrics
from simulation.warehouse.grid import WarehouseGrid
from task_allocation.cost_model import compute_bid_cost


@dataclass
class SimRobot:
    state: RobotState
    task: Optional[TaskSpec] = None
    phase: str = "pickup"
    path: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class FleetSimulator:
    grid: WarehouseGrid
    robots: dict[str, SimRobot]
    tasks: list[TaskSpec]
    algorithm: str = "proposed"
    events: list[dict] = field(default_factory=list)
    metrics: FleetMetrics = field(init=False)
    tick: int = 0
    pending: list[TaskSpec] = field(init=False)
    completed_at: list[int] = field(default_factory=list)
    reservations: ReservationTable = field(default_factory=ReservationTable)

    def __post_init__(self) -> None:
        self.pending = list(self.tasks)
        self.metrics = FleetMetrics(algorithm=self.algorithm)

    @classmethod
    def from_scenario(cls, grid: WarehouseGrid, scenario: dict, algorithm: str = "proposed") -> "FleetSimulator":
        robots = {
            r["id"]: SimRobot(RobotState(robot_id=r["id"], position=tuple(r["spawn"])))
            for r in scenario.get("robots", [])
        }
        tasks = [TaskSpec(t["id"], tuple(t["pickup"]), tuple(t["dropoff"]), t.get("urgency", 1.0), t.get("deadline_tick")) for t in scenario.get("tasks", [])]
        return cls(grid, robots, tasks, algorithm, list(scenario.get("events", [])))

    def _apply_events(self) -> None:
        for event in self.events:
            if event.get("at_tick") != self.tick:
                continue
            if event["type"] == "block_aisle":
                self.grid.block_cells([tuple(c) for c in event["cells"]])
                for robot in self.robots.values():
                    if robot.path and any(c in self.grid.dynamic_blocked for c in robot.path):
                        robot.path = []
                        self.metrics.replans += 1
            elif event["type"] == "robot_failure":
                robot = self.robots[event["robot_id"]]
                robot.state.status = "OFFLINE"
                self.reservations.release_robot(robot.state.robot_id)
                if robot.task:
                    self.pending.insert(0, robot.task)
                    robot.task = None
                    robot.path = []
                    self.metrics.reassignments += 1

    def _allocate(self) -> None:
        idle = [r for r in self.robots.values() if r.task is None and r.state.status != "OFFLINE" and r.state.battery >= 20]
        for task in list(self.pending):
            if not idle:
                return
            if self.algorithm == "baseline":
                winner = min(idle, key=lambda r: (self.grid.manhattan(r.state.position, task.pickup), r.state.robot_id))
            else:
                peers = [r.state.position for r in self.robots.values() if r.state.status != "OFFLINE"]
                winner = min(idle, key=lambda r: (compute_bid_cost(r.state, task.pickup, task.dropoff, self.grid, predict_congestion(self.grid, r.state.position, task.pickup, peers)), r.state.robot_id))
            winner.task, winner.phase, winner.state.current_task = task, "pickup", task.task_id
            winner.path = []
            self.pending.remove(task)
            idle.remove(winner)

    def _plan(self) -> None:
        self.reservations.prune_old(self.tick)
        for robot in sorted(self.robots.values(), key=lambda r: r.state.robot_id):
            if robot.task is None or robot.state.status == "OFFLINE":
                continue
            goal = robot.task.pickup if robot.phase == "pickup" else robot.task.dropoff
            # A task may be assigned to a robot already parked at its pickup.
            # Advance this state before asking a planner for a zero-length path.
            if robot.state.position == goal:
                if robot.phase == "pickup":
                    robot.phase, robot.path = "dropoff", []
                    goal = robot.task.dropoff
                else:
                    robot.task = None
                    robot.state.current_task = None
                    robot.state.status = "IDLE"
                    self.metrics.completed_tasks += 1
                    self.completed_at.append(self.tick)
                    continue
            if not robot.path or robot.path[0] != robot.state.position or any(c in self.grid.dynamic_blocked for c in robot.path):
                if self.algorithm == "baseline":
                    robot.path = grid_astar(self.grid, robot.state.position, goal)
                else:
                    robot.path = space_time_astar(self.grid, robot.state.position, goal, self.tick, self.reservations, robot.state.robot_id)
                self.reservations.reserve_path(robot.state.robot_id, robot.path, self.tick)
                self.metrics.replans += 1

    def _move(self) -> None:
        occupied = {r.state.position: r.state.robot_id for r in self.robots.values() if r.state.status != "OFFLINE"}
        claims: dict[tuple[int, int], list[SimRobot]] = {}
        for r in self.robots.values():
            if r.task and r.state.status != "OFFLINE" and len(r.path) > 1:
                claims.setdefault(r.path[1], []).append(r)
        for target, claimants in claims.items():
            winner = min(claimants, key=lambda r: (-r.task.urgency, r.state.robot_id))
            for r in claimants:
                # A taskless robot is a cooperative obstacle: pull it into an
                # adjacent free cell before letting an assigned robot enter.
                # This models the same yield behaviour used by RobotNode.
                blocking_id = occupied.get(target)
                if blocking_id and blocking_id != r.state.robot_id:
                    blocker = self.robots[blocking_id]
                    if blocker.task is None:
                        alternatives = [
                            cell for cell in self.grid.neighbors(*blocker.state.position)
                            if cell not in occupied and cell != target
                        ]
                        if alternatives:
                            new_cell = min(alternatives)
                            occupied.pop(blocker.state.position)
                            blocker.state.position = new_cell
                            blocker.state.status = "YIELDING"
                            occupied[new_cell] = blocking_id
                if r is not winner or (target in occupied and occupied[target] != r.state.robot_id):
                    r.state.wait_ticks += 1
                    self.metrics.total_wait_ticks += 1
                    continue
                r.state.position = target
                r.state.status = "MOVING"
                r.state.battery = max(0.0, r.state.battery - 0.01)
                r.path.pop(0)
                if r.task and r.state.position == (r.task.pickup if r.phase == "pickup" else r.task.dropoff):
                    if r.phase == "pickup":
                        r.phase, r.path = "dropoff", []
                    else:
                        r.task = None
                        r.state.current_task = None
                        r.state.status = "IDLE"
                        self.metrics.completed_tasks += 1
                        self.completed_at.append(self.tick)

    def step(self) -> None:
        self.tick += 1
        self._apply_events()
        self._allocate()
        self._plan()
        self._move()

    def run(self, max_ticks: int = 500) -> FleetMetrics:
        while self.tick < max_ticks and (self.pending or any(r.task for r in self.robots.values())):
            self.step()
        self.metrics.ticks = self.tick
        self.metrics.failed_tasks = len(self.pending) + sum(1 for r in self.robots.values() if r.task)
        self.metrics.mean_completion_tick = sum(self.completed_at) / len(self.completed_at) if self.completed_at else 0.0
        return self.metrics

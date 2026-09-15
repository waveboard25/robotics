"""
MeshFleet headless simulation engine (Python reference implementation).

WHY THIS EXISTS
----------------
simulator.html is the presentation-ready 3D demo (runs standalone in a
browser, everything implemented in JS). This module is a second,
behavior-identical implementation of the same physics/state-machine used
for:

  1. Teammates who want to write and unit-test their Python module
     (path planner, conflict resolution, task allocation, edge-AI) against
     a real simulation without needing a browser or a rendering pipeline.
  2. Batch / headless testing of scenarios (e.g. in CI, or from a terminal
     during development).

It is intentionally NOT wired to the browser demo — the two are decoupled
on purpose. See SIMULATION_INTERFACES.md for how a team would bridge them
(e.g. exposing this engine over a local WebSocket/REST endpoint that the
HTML page polls) if that becomes worth doing later.

WHAT THIS ENGINE DOES / DOES NOT DO
------------------------------------
DOES:      physics stepping, collision *detection*, battery drain/charge,
           state machine transitions, route/task/obstacle/command intake.
DOES NOT:  path planning, conflict *resolution* strategy, task allocation
           strategy, or any AI decision-making. Those are teammates' work;
           this engine only reports what happened and obeys commands.
"""

from __future__ import annotations
import math
import time as _time
from dataclasses import replace
from typing import Callable, Optional

from .schemas import (
    Position, RobotState, RobotOperationalState, RobotCommand, CommandType,
    Task, CollisionEvent, EnvironmentState,
)
from .warehouse_layout import build_default_warehouse_layout

ROBOT_RADIUS = 0.55
MAX_SPEED = 3.2
ACCEL = 2.0
DECEL = 3.0
ARRIVE_EPS = 0.12


class _RobotInternal:
    """Mutable internal robot record. RobotState (schemas.py) is the public,
    read-only snapshot handed to other modules — see .public_state()."""

    def __init__(self, robot_id: str, x: float, z: float):
        self.robot_id = robot_id
        self.position = Position(x=x, z=z)
        self.orientation = 0.0
        self.velocity = 0.0
        self.battery = 100.0
        self.current_task: Optional[str] = None
        self.destination: Optional[str] = None
        self.state = RobotOperationalState.IDLE
        self.comm_status = "ONLINE"
        self.waypoints: list[tuple[float, float]] = []
        self.wp_index = 0
        self.target_velocity = 0.0
        self.going_to_charge: Optional[str] = None
        self.max_override: Optional[float] = None
        self.loop_route: Optional[list[tuple[float, float]]] = None

    def public_state(self, sim_time: float) -> RobotState:
        remaining = self.waypoints[self.wp_index:]
        return RobotState(
            robot_id=self.robot_id,
            position=Position(x=self.position.x, z=self.position.z),
            orientation=self.orientation,
            velocity=round(self.velocity, 3),
            battery=round(self.battery, 1),
            current_task=self.current_task,
            destination=self.destination,
            current_route=[[wp[0], wp[1]] for wp in remaining],
            current_state=self.state,
            communication_status=self.comm_status,
            timestamp=sim_time,
        )


class SimulationEngine:
    def __init__(self, warehouse: Optional[dict] = None):
        self.warehouse = warehouse or build_default_warehouse_layout()
        self.robots: dict[str, _RobotInternal] = {}
        self.obstacles: dict[str, dict] = {}
        self.blocked_aisles: dict[str, dict] = {}
        self.tasks: dict[str, Task] = {}
        self.collision_events: list[CollisionEvent] = []
        self.sim_time = 0.0
        self._listeners: list[Callable[[str, dict], None]] = []

        for o in self.warehouse.get("staticObstacles", []):
            self.add_obstacle(o["id"], o["x"], o["z"], o.get("r", 0.6))

    # ---------------------------------------------------------------- events
    def on_event(self, fn: Callable[[str, dict], None]) -> None:
        self._listeners.append(fn)

    def _emit(self, name: str, payload: dict) -> None:
        for fn in self._listeners:
            fn(name, payload)

    # --------------------------------------------------------------- robots
    def add_robot(self, robot_id: str, x: float, z: float) -> RobotState:
        r = _RobotInternal(robot_id, x, z)
        self.robots[robot_id] = r
        return r.public_state(self.sim_time)

    def get_robot_state(self, robot_id: str) -> Optional[RobotState]:
        r = self.robots.get(robot_id)
        return r.public_state(self.sim_time) if r else None

    # ------------------------------------------------------------ interface
    def get_environment_state(self) -> EnvironmentState:
        return EnvironmentState(
            warehouse=self.warehouse,
            obstacles=list(self.obstacles.values()),
            blocked_aisles=list(self.blocked_aisles.values()),
            robot_states=[r.public_state(self.sim_time) for r in self.robots.values()],
            simulation_time=self.sim_time,
        )

    def set_route(self, robot_id: str, route: list[list[float]], destination: Optional[str] = None,
                  loop: bool = False) -> bool:
        r = self.robots.get(robot_id)
        if not r:
            return False
        r.waypoints = [(p[0], p[1]) for p in route]
        r.wp_index = 0
        r.loop_route = list(r.waypoints) if loop else None
        if destination:
            r.destination = destination
        if r.state in (RobotOperationalState.IDLE, RobotOperationalState.WAITING):
            r.state = RobotOperationalState.MOVING
        self._emit("ROUTE_SET", {"robot_id": robot_id, "route": route})
        return True

    def assign_task(self, task: Task) -> None:
        self.tasks[task.task_id] = task
        self._emit("TASK_ASSIGNED", {"task_id": task.task_id})

    def send_command(self, cmd: RobotCommand) -> dict:
        r = self.robots.get(cmd.target)
        if not r:
            return {"ok": False, "error": "unknown robot"}

        if cmd.type == CommandType.SET_ROUTE:
            self.set_route(cmd.target, cmd.route or [], cmd.destination)
        elif cmd.type == CommandType.STOP:
            r.waypoints, r.target_velocity, r.velocity = [], 0.0, 0.0
            r.state = RobotOperationalState.BLOCKED
            self._emit("SAFETY_STOP", {"robot_id": cmd.target})
        elif cmd.type == CommandType.WAIT:
            r.state, r.target_velocity = RobotOperationalState.WAITING, 0.0
        elif cmd.type == CommandType.RESUME:
            r.state = RobotOperationalState.MOVING if r.waypoints else RobotOperationalState.IDLE
        elif cmd.type == CommandType.REROUTE:
            self.set_route(cmd.target, cmd.route or [], cmd.destination)
            r.state = RobotOperationalState.REROUTING
        elif cmd.type == CommandType.GO_TO_CHARGER:
            station = self._nearest_charger(r)
            self.set_route(cmd.target, [[r.position.x, r.position.z], [station["x"], station["z"]]],
                            destination=f"CHARGER:{station['id']}")
            r.going_to_charge = station["id"]
        elif cmd.type == CommandType.SET_VELOCITY:
            r.max_override = cmd.velocity
        return {"ok": True}

    def _nearest_charger(self, r: _RobotInternal) -> dict:
        return min(
            self.warehouse["chargingStations"],
            key=lambda c: math.hypot(c["x"] - r.position.x, c["z"] - r.position.z),
        )

    # ------------------------------------------------------------ obstacles
    def add_obstacle(self, obstacle_id: str, x: float, z: float, r: float = 0.6,
                      temporary: bool = False, duration: Optional[float] = None) -> dict:
        o = {"id": obstacle_id, "x": x, "z": z, "r": r, "temporary": temporary,
             "expires_at": (self.sim_time + duration) if duration else None}
        self.obstacles[obstacle_id] = o
        self._emit("OBSTACLE_ADDED", o)
        return o

    def remove_obstacle(self, obstacle_id: str) -> None:
        if self.obstacles.pop(obstacle_id, None) is not None:
            self._emit("OBSTACLE_REMOVED", {"id": obstacle_id})

    def block_aisle(self, aisle_id: str, box: dict, temporary: bool = False,
                     duration: Optional[float] = None) -> None:
        b = {"id": aisle_id, "box": box, "temporary": temporary,
             "expires_at": (self.sim_time + duration) if duration else None}
        self.blocked_aisles[aisle_id] = b
        self._emit("AISLE_BLOCKED", b)

    def unblock_aisle(self, aisle_id: str) -> None:
        if self.blocked_aisles.pop(aisle_id, None) is not None:
            self._emit("AISLE_UNBLOCKED", {"id": aisle_id})

    def _point_in_blocked_aisle(self, x: float, z: float):
        for b in self.blocked_aisles.values():
            box = b["box"]
            if box["xMin"] <= x <= box["xMax"] and box["zMin"] <= z <= box["zMax"]:
                return b
        return None

    # --------------------------------------------------------------- physics
    def step(self, dt: float) -> None:
        self.sim_time += dt

        for oid in [k for k, v in self.obstacles.items() if v["expires_at"] and self.sim_time >= v["expires_at"]]:
            self.remove_obstacle(oid)
        for bid in [k for k, v in self.blocked_aisles.items() if v["expires_at"] and self.sim_time >= v["expires_at"]]:
            self.unblock_aisle(bid)

        for r in self.robots.values():
            if (r.battery <= 2 and r.state != RobotOperationalState.CHARGING
                    and not r.going_to_charge and not r.loop_route):
                self._emit("LOW_BATTERY", {"robot_id": r.robot_id, "battery": r.battery})
                self.send_command(RobotCommand(type=CommandType.GO_TO_CHARGER, target=r.robot_id))
            self._step_robot(r, dt)

        self._check_collisions()

    def _step_robot(self, r: _RobotInternal, dt: float) -> None:
        moving = r.state in (RobotOperationalState.MOVING, RobotOperationalState.AVOIDING,
                              RobotOperationalState.REROUTING)

        if r.state == RobotOperationalState.CHARGING:
            r.battery = min(100.0, r.battery + 12 * dt)
            if r.battery >= 99.5:
                r.state = RobotOperationalState.IDLE
                r.going_to_charge = None
                self._emit("CHARGE_COMPLETE", {"robot_id": r.robot_id})
            return
        r.battery = max(0.0, r.battery - (0.9 if moving else 0.05) * dt)

        if r.state in (RobotOperationalState.WAITING, RobotOperationalState.BLOCKED, RobotOperationalState.ERROR):
            r.target_velocity = 0.0

        if not r.waypoints:
            r.target_velocity = 0.0
            r.velocity = max(0.0, r.velocity - DECEL * dt)
            if r.velocity <= 0.01 and r.state == RobotOperationalState.MOVING:
                r.state = RobotOperationalState.IDLE
            return

        wp = r.waypoints[r.wp_index]
        dx, dz = wp[0] - r.position.x, wp[1] - r.position.z
        dist = math.hypot(dx, dz)
        desired_heading = math.atan2(dx, dz)

        if self._point_in_blocked_aisle(*wp):
            r.state = RobotOperationalState.BLOCKED
            r.target_velocity = 0.0
        elif r.state == RobotOperationalState.BLOCKED:
            r.state = RobotOperationalState.MOVING

        if dist < ARRIVE_EPS:
            r.wp_index += 1
            if r.wp_index >= len(r.waypoints):
                if r.loop_route and not r.going_to_charge:
                    r.waypoints = list(r.loop_route)
                    r.wp_index = 0
                    r.state = RobotOperationalState.MOVING
                    r.velocity = 0.0
                    self._emit("PATROL_LOOP", {"robot_id": r.robot_id})
                    return
                r.waypoints = []
                if r.going_to_charge:
                    r.state = RobotOperationalState.CHARGING
                    self._emit("CHARGE_START", {"robot_id": r.robot_id})
                else:
                    r.state = RobotOperationalState.IDLE
                    r.destination = None
                    self._emit("DESTINATION_REACHED", {"robot_id": r.robot_id})
                r.velocity = 0.0
                return

        if r.state not in (RobotOperationalState.WAITING, RobotOperationalState.BLOCKED, RobotOperationalState.ERROR):
            if r.state not in (RobotOperationalState.AVOIDING, RobotOperationalState.REROUTING):
                r.state = RobotOperationalState.MOVING
            r.target_velocity = r.max_override or MAX_SPEED

        d_angle = desired_heading - r.orientation
        d_angle = (d_angle + math.pi) % (2 * math.pi) - math.pi
        r.orientation += d_angle * min(1.0, dt * 4)

        if r.velocity < r.target_velocity:
            r.velocity = min(r.target_velocity, r.velocity + ACCEL * dt)
        else:
            r.velocity = max(r.target_velocity, r.velocity - DECEL * dt)

        move_dist = r.velocity * dt
        ratio = min(1.0, move_dist / dist) if dist > 0 else 0.0
        r.position.x += dx * ratio
        r.position.z += dz * ratio

    def _check_collisions(self) -> None:
        robots = list(self.robots.values())
        for i in range(len(robots)):
            for j in range(i + 1, len(robots)):
                a, b = robots[i], robots[j]
                d = math.hypot(a.position.x - b.position.x, a.position.z - b.position.z)
                min_d = ROBOT_RADIUS * 2
                if min_d <= d < min_d * 1.001:
                    if a.state == RobotOperationalState.MOVING:
                        a.state = RobotOperationalState.AVOIDING
                    if b.state == RobotOperationalState.MOVING:
                        b.state = RobotOperationalState.AVOIDING
                if d < min_d:
                    ev = CollisionEvent(
                        timestamp=self.sim_time, robot_a=a.robot_id, robot_b_or_obstacle=b.robot_id,
                        location=Position(x=(a.position.x + b.position.x) / 2,
                                           z=(a.position.z + b.position.z) / 2),
                        severity="HIGH",
                    )
                    self.collision_events.append(ev)
                    self._emit("COLLISION", ev.__dict__)
                    a.target_velocity = b.target_velocity = 0.0
                    a.state = b.state = RobotOperationalState.WAITING

        for o in self.obstacles.values():
            for a in robots:
                d = math.hypot(a.position.x - o["x"], a.position.z - o["z"])
                if d < ROBOT_RADIUS + o["r"]:
                    ev = CollisionEvent(
                        timestamp=self.sim_time, robot_a=a.robot_id, robot_b_or_obstacle=o["id"],
                        location=Position(x=o["x"], z=o["z"]), severity="MEDIUM",
                    )
                    self.collision_events.append(ev)
                    self._emit("COLLISION", ev.__dict__)
                    a.target_velocity = 0.0
                    a.state = RobotOperationalState.AVOIDING

    # ------------------------------------------------------------- helpers
    def run_for(self, seconds: float, dt: float = 0.1) -> None:
        """Convenience for headless/CI testing: advance the clock in fixed steps."""
        steps = int(seconds / dt)
        for _ in range(steps):
            self.step(dt)

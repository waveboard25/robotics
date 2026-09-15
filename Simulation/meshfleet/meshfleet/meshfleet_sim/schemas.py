"""
MeshFleet Simulation — shared data schemas.

These dataclasses are the CONTRACT between the simulator and every other
MeshFleet module (P2P comms, path planner, conflict resolution, task
allocation, edge-AI, dashboard). They are field-for-field identical to the
JS objects produced/consumed by simulator.html (see SIMULATION_INTERFACES.md).

Nobody outside this file should need to know how the simulator represents
robots or the warehouse internally — they only need these shapes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RobotOperationalState(str, Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    WAITING = "WAITING"
    AVOIDING = "AVOIDING"
    REROUTING = "REROUTING"
    CHARGING = "CHARGING"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class CommandType(str, Enum):
    SET_ROUTE = "SET_ROUTE"
    STOP = "STOP"
    WAIT = "WAIT"
    RESUME = "RESUME"
    REROUTE = "REROUTE"
    GO_TO_CHARGER = "GO_TO_CHARGER"
    SET_VELOCITY = "SET_VELOCITY"


@dataclass
class Position:
    x: float
    z: float
    y: float = 0.0


@dataclass
class RobotState:
    robot_id: str
    position: Position
    orientation: float               # radians, yaw
    velocity: float                  # scalar units/sec along heading
    battery: float                   # 0-100
    current_task: Optional[str]
    destination: Optional[str]
    current_route: list              # list of [x, z] waypoints remaining
    current_state: RobotOperationalState
    communication_status: str        # "ONLINE" | "STALE" | "OFFLINE"
    timestamp: float                 # simulation time (seconds)


@dataclass
class EnvironmentState:
    warehouse: dict                  # warehouse layout config (see warehouse_layout.py)
    obstacles: list                  # list of {id, x, z, r, temporary}
    blocked_aisles: list             # list of {id, box:{xMin,xMax,zMin,zMax}, temporary}
    robot_states: list               # list[RobotState]
    simulation_time: float


@dataclass
class RobotCommand:
    type: CommandType
    target: str                      # robot_id
    route: Optional[list] = None     # list of [x, z] waypoints, required for SET_ROUTE/REROUTE
    velocity: Optional[float] = None
    destination: Optional[str] = None


@dataclass
class Task:
    task_id: str
    pickup_location: str             # station id, e.g. "P-01"
    drop_location: str               # station id, e.g. "D-03"
    priority: int = 0


@dataclass
class CollisionEvent:
    timestamp: float
    robot_a: str
    robot_b_or_obstacle: str
    location: Position
    severity: str                    # "LOW" | "MEDIUM" | "HIGH"

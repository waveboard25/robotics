from pathlib import Path

import yaml
from communication.discovery import PeerTable
from communication.protocol import Message, MessageType

from planning.global_planner import space_time_astar
from planning.reservation_table import ReservationTable
from simulation.engine.fleet_simulator import FleetSimulator, SimRobot
from simulation.warehouse.grid import WarehouseGrid
from robots.state import RobotState, TaskSpec
from simulation.warehouse.grid import load_warehouse

ROOT = Path(__file__).resolve().parent.parent


def test_space_time_plan_preserves_waits() -> None:
    grid = load_warehouse(ROOT / "configs/warehouse_layouts/default.yaml")
    table = ReservationTable()
    table.reserve_path("R2", [(1, 3), (1, 4)], 0)
    path = space_time_astar(grid, (1, 3), (1, 5), 0, table, "R1")
    assert path[:2] == [(1, 3), (1, 3)]


def test_failure_requeues_task_and_simulation_completes_work() -> None:
    with open(ROOT / "configs/scenarios/scenario_03.yaml", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)
    grid = load_warehouse(ROOT / scenario["map"])
    metrics = FleetSimulator.from_scenario(grid, scenario).run(350)
    assert metrics.reassignments == 1
    assert metrics.completed_tasks == 3
    assert metrics.collisions == 0


def test_move_rejects_head_on_swap() -> None:
    grid = WarehouseGrid(width=3, height=1)
    left = SimRobot(
        RobotState(robot_id="R1", position=(0, 0)),
        TaskSpec("T1", (1, 0), (2, 0)),
        path=[(0, 0), (1, 0)],
    )
    right = SimRobot(
        RobotState(robot_id="R2", position=(1, 0)),
        TaskSpec("T2", (0, 0), (2, 0)),
        path=[(1, 0), (0, 0)],
    )
    simulator = FleetSimulator(grid, {"R1": left, "R2": right}, [])

    simulator._move()

    assert left.state.position == (0, 0)
    assert right.state.position == (1, 0)


def test_peer_liveness_uses_local_receive_time() -> None:
    peers = PeerTable(stale_threshold=1.0)
    peers.update_from_message(
        Message(
            MessageType.TELEMETRY,
            "R2",
            seq=1,
            timestamp=0.0,
            payload={"position": [1, 1]},
        ),
        "R1",
    )

    assert peers.get_active_peers()["R2"].position == (1, 1)
    assert not peers.evict_stale()


def test_stale_peer_remains_a_safety_obstacle() -> None:
    peers = PeerTable(stale_threshold=1.0)
    peers.update_from_message(
        Message(
            MessageType.TELEMETRY,
            "R2",
            seq=1,
            payload={"position": [1, 1]},
        ),
        "R1",
    )

    stale = peers.evict_stale(now=peers.peers["R2"].last_seen + 2.0)

    assert stale == ["R2"]
    assert peers.get_active_peers()["R2"].status == "STALE"


def test_blocked_aisle_cell_is_never_entered() -> None:
    grid = WarehouseGrid(width=3, height=1)
    robot = SimRobot(
        RobotState(robot_id="R1", position=(0, 0)),
        TaskSpec("T1", (2, 0), (2, 0)),
        path=[(0, 0), (1, 0), (2, 0)],
    )
    simulator = FleetSimulator(grid, {"R1": robot}, [])
    grid.block_cells([(1, 0)])

    simulator._move()

    assert robot.state.position == (0, 0)

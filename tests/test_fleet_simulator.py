from pathlib import Path

import yaml

from planning.global_planner import space_time_astar
from planning.reservation_table import ReservationTable
from simulation.engine.fleet_simulator import FleetSimulator
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

"""Scenario runner — spawns robot processes and optional visualizer."""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.discovery import PeerTable
from communication.protocol import MessageType
from communication.transport_udp import UDPTransport
from meshfleet.constants import BROADCAST_PORT, TICK_DT
from robots.state import TaskSpec
from simulation.scenarios.task_generator import TaskGenerator
from simulation.warehouse.grid import load_warehouse

try:
    from simulation.renderer.pygame_view import PygameRenderer
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


def load_scenario(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def spawn_robots(scenario: dict, headless: bool = True) -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    python = sys.executable
    for robot in scenario.get("robots", []):
        cmd = [
            python, "-m", "robots.robot_node",
            "--id", robot["id"],
            "--spawn-x", str(robot["spawn"][0]),
            "--spawn-y", str(robot["spawn"][1]),
            "--map", scenario.get("map", "configs/warehouse_layouts/default.yaml"),
            "--max-ticks", str(scenario.get("max_ticks", 500)),
        ]
        if headless:
            cmd.append("--headless")
        if scenario.get("use_auction", True):
            pass
        else:
            cmd.append("--no-auction")
        procs.append(subprocess.Popen(cmd, cwd=str(ROOT)))
        time.sleep(0.3)
    return procs


def run_tasks(scenario: dict) -> None:
    gen = TaskGenerator(port=BROADCAST_PORT)
    time.sleep(scenario.get("task_delay", 1.0))

    for task in scenario.get("tasks", []):
        spec = TaskSpec(
            task_id=task["id"],
            pickup=tuple(task["pickup"]),
            dropoff=tuple(task["dropoff"]),
            urgency=task.get("urgency", 1.0),
            deadline_tick=task.get("deadline_tick"),
        )
        gen.announce(spec, tick=task.get("announce_tick", 0))
        time.sleep(task.get("delay_after", 1.5))

    for event in scenario.get("events", []):
        delay = event.get("at_tick", 100) * TICK_DT
        time.sleep(max(0, delay - time.time() % 1000))  # rough timing
        if event["type"] == "block_aisle":
            gen.block_aisle(
                event["aisle_id"],
                [tuple(c) for c in event["cells"]],
                tick=event.get("at_tick", 100),
            )

    time.sleep(2)
    gen.close()


def visualize(scenario: dict, duration: float) -> None:
    if not HAS_PYGAME:
        print("Pygame not available — skipping visualization")
        return

    map_path = ROOT / scenario.get("map", "configs/warehouse_layouts/default.yaml")
    grid = load_warehouse(map_path)
    renderer = PygameRenderer(grid, title=scenario.get("name", "MeshFleet"))

    transport = UDPTransport(port=BROADCAST_PORT)
    peers = PeerTable()
    start = time.time()

    while time.time() - start < duration:
        for msg in transport.recv_all():
            peers.update_from_message(msg, "DASHBOARD")
        peers.evict_stale()

        robot_info = {}
        for rid, state in peers.get_active_peers().items():
            robot_info[rid] = {
                "position": state.position,
                "status": state.status,
                "next_waypoints": state.next_waypoints,
            }

        if not renderer.draw(robot_info):
            break

    renderer.close()
    transport.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MeshFleet scenario")
    parser.add_argument("--scenario", required=True, help="Path to scenario YAML")
    parser.add_argument("--visual", action="store_true", help="Show Pygame visualization")
    parser.add_argument("--no-headless", action="store_true", help="Robots with logging")
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.is_absolute():
        scenario_path = ROOT / scenario_path
    scenario = load_scenario(scenario_path)

    print(f"Running scenario: {scenario.get('name', scenario_path.name)}")
    procs = spawn_robots(scenario, headless=not args.no_headless)

    task_thread = threading.Thread(target=run_tasks, args=(scenario,), daemon=True)
    task_thread.start()

    duration = scenario.get("max_ticks", 500) * TICK_DT + 5

    if args.visual:
        visualize(scenario, duration)
    else:
        time.sleep(duration)

    for p in procs:
        p.terminate()
    for p in procs:
        p.wait(timeout=5)

    print("Scenario complete.")


if __name__ == "__main__":
    main()

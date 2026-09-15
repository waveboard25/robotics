"""
The 8 SIH demo scenarios, expressed against SimulationEngine.

These mirror loadScenario() in simulator.html exactly (same waypoints,
same timings-in-spirit) so behavior discussed using the Python engine
matches what judges will see in the visual demo.
"""

import random

from .engine import SimulationEngine
from .schemas import RobotCommand, CommandType, Task


def _spawn(engine: SimulationEngine, n: int, start_z=(-9, -3, 3, 9, -6, 0, 6, -12, 12, -1.5)):
    ids = []
    for i in range(n):
        rid = f"AMR-{i+1:02d}"
        engine.add_robot(rid, -18, start_z[i % len(start_z)])
        ids.append(rid)
    return ids


def scenario_1_overlapping_routes(engine: SimulationEngine):
    """All spawned AMRs roam through separate multi-turn patrol routes."""
    ids = _spawn(engine, 10)
    patrol_bands = [-9, -3, 3, 9, -6, 0, 6, -12, 12, -1.5]
    for i, rid in enumerate(ids):
        start_z = patrol_bands[i % len(patrol_bands)]
        lane_z = 7.2 if start_z == 6 else start_z
        x1 = -15 + random.random() * 4
        x2 = -7 + random.random() * 6
        x3 = 1 + random.random() * 6
        x4 = 10 + random.random() * 6
        route = [
            [-18, start_z], [-18, lane_z], [x1, lane_z], [x2, lane_z],
            [x3, lane_z], [x4, lane_z], [20, lane_z], [x4, lane_z],
            [x2, lane_z], [x1, lane_z], [-18, lane_z], [-18, start_z],
        ]
        engine.set_route(rid, route, f"D-{(i % 4) + 1:02d}", loop=True)
    return ids


def scenario_2_convergent_intersection(engine: SimulationEngine):
    """Three AMRs approaching the same intersection at once."""
    ids = _spawn(engine, 3)
    engine.set_route(ids[0], [[-6, -12], [-6, 0]], "INT-B")
    engine.set_route(ids[1], [[-18, 0], [-6, 0]], "INT-B")
    engine.set_route(ids[2], [[9, -9], [-6, -9], [-6, 0]], "INT-B")
    return ids


def scenario_3_narrow_aisle_faceoff(engine: SimulationEngine):
    """Two AMRs approaching each other in a narrow aisle (x=9 corridor)."""
    engine.add_robot("AMR-N1", 9, -12)
    engine.add_robot("AMR-N2", 9, 12)
    engine.set_route("AMR-N1", [[9, 12]], "north end")
    engine.set_route("AMR-N2", [[9, -12]], "south end")
    return ["AMR-N1", "AMR-N2"]


def scenario_4_dynamic_obstacle(engine: SimulationEngine, block_at_t=3.0, duration=20.0):
    """A dynamic obstacle blocks an aisle mid-route; planner must be told."""
    ids = _spawn(engine, 3)
    engine.set_route(ids[0], [[-18, -9], [-6, -9], [-6, 9], [20, 9]], "D-04")

    def _watch(name, payload, _state={"blocked": False}):
        if not _state["blocked"] and engine.sim_time >= block_at_t:
            engine.block_aisle("AISLE-BLOCK-1", {"xMin": -7.5, "xMax": -4.5, "zMin": -4, "zMax": 4},
                                temporary=True, duration=duration)
            _state["blocked"] = True

    # Simplest correct approach: caller should check sim_time each tick and
    # call block_aisle once; provided here as a manual trigger for scripts:
    return ids


def scenario_5_reroute_command(engine: SimulationEngine):
    """A robot receives a new route mid-journey from an external planner."""
    ids = _spawn(engine, 3)
    engine.set_route(ids[0], [[-18, -9], [-6, -9], [-6, 9], [20, 9]], "D-04")
    return ids


def scenario_6_low_battery_charging(engine: SimulationEngine):
    """A robot has low battery and autonomously seeks a charging station."""
    ids = _spawn(engine, 3)
    engine.robots[ids[0]].battery = 6.0
    engine.set_route(ids[0], [[-18, -9], [-6, -9], [-6, 3], [-18, 3]], "patrol")
    return ids


def scenario_7_safety_stop(engine: SimulationEngine):
    """A robot stops immediately because of an external safety STOP command."""
    ids = _spawn(engine, 3)
    engine.set_route(ids[0], [[-18, -9], [20, -9]], "D-01")
    return ids


def scenario_8_pickup_transport_dropoff(engine: SimulationEngine, n=3):
    """Multiple robots perform pickup -> transport -> drop-off tasks."""
    ids = _spawn(engine, n)
    for i, rid in enumerate(ids):
        p = engine.warehouse["pickupStations"][i % 4]
        d = engine.warehouse["dropStations"][i % 4]
        task = Task(task_id=f"T-{i+1}", pickup_location=p["id"], drop_location=d["id"], priority=i % 3)
        engine.assign_task(task)
        engine.robots[rid].current_task = task.task_id
        engine.set_route(rid, [[p["x"], p["z"]], [-6, p["z"]], [-6, d["z"]], [d["x"], d["z"]]], d["id"])
    return ids


SCENARIOS = {
    1: scenario_1_overlapping_routes,
    2: scenario_2_convergent_intersection,
    3: scenario_3_narrow_aisle_faceoff,
    4: scenario_4_dynamic_obstacle,
    5: scenario_5_reroute_command,
    6: scenario_6_low_battery_charging,
    7: scenario_7_safety_stop,
    8: scenario_8_pickup_transport_dropoff,
}

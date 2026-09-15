"""
Run a scenario headlessly and print periodic state snapshots as JSON.
Useful for teammates to sanity-check their module against real engine
output without opening the browser demo.

Usage:
    python -m meshfleet_sim.run_scenario 1 --seconds 15 --every 2.5
"""
import argparse
import dataclasses
import json

from .engine import SimulationEngine
from .scenarios import SCENARIOS


def _default(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if hasattr(o, "value"):
        return o.value
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", type=int, choices=sorted(SCENARIOS.keys()))
    ap.add_argument("--seconds", type=float, default=15.0)
    ap.add_argument("--every", type=float, default=2.5)
    ap.add_argument("--dt", type=float, default=0.1)
    args = ap.parse_args()

    engine = SimulationEngine()
    engine.on_event(lambda name, payload: print(f"[event] t={engine.sim_time:5.1f}s {name} {payload}"))
    SCENARIOS[args.scenario](engine)

    # scenario 4 needs a manually-timed obstacle injection when run headlessly
    if args.scenario == 4:
        injected = False

    t = 0.0
    next_print = 0.0
    while t < args.seconds:
        if args.scenario == 4 and not injected and t >= 3.0:
            engine.block_aisle("AISLE-BLOCK-1", {"xMin": -7.5, "xMax": -4.5, "zMin": -4, "zMax": 4},
                                temporary=True, duration=20.0)
            injected = True
        engine.step(args.dt)
        t += args.dt
        if t >= next_print:
            env = engine.get_environment_state()
            print(json.dumps({
                "t": round(env.simulation_time, 1),
                "robots": [dataclasses.asdict(r) for r in env.robot_states],
            }, default=_default))
            next_print += args.every


if __name__ == "__main__":
    main()

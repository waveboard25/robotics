"""Repeatable baseline/proposed benchmark runner."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml

from simulation.engine.fleet_simulator import FleetSimulator
from simulation.warehouse.grid import load_warehouse

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--output", default="benchmarking/results/benchmark.csv")
    args = parser.parse_args()
    scenario_path = ROOT / args.scenario
    with open(scenario_path, encoding="utf-8") as f:
        scenario = yaml.safe_load(f)
    rows = []
    for algorithm in ("baseline", "proposed"):
        for trial in range(args.trials):
            grid = load_warehouse(ROOT / scenario.get("map", "configs/warehouse_layouts/default.yaml"))
            metrics = FleetSimulator.from_scenario(grid, scenario, algorithm).run(scenario.get("max_ticks", 500)).to_dict()
            metrics["trial"] = trial + 1
            rows.append(metrics)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} runs to {output}")


if __name__ == "__main__":
    main()

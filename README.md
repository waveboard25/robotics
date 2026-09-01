# MeshFleet

Decentralized edge-AI fleet coordination for warehouse AMRs (SIH26123).

Each robot runs as an independent OS process communicating over UDP broadcast with no central decision server. Coordination uses space-time A* with reservation tables, ORCA local avoidance, priority-based conflict resolution, and Contract Net Protocol task allocation.

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Run a scenario (spawns robot processes)
python -m simulation.scenarios.runner --scenario configs/scenarios/scenario_03.yaml

# Or start a single robot manually
python -m robots.robot_node --id R1 --spawn-x 1 --spawn-y 1

# Run tests
pytest tests/ -v

# Benchmark baseline vs proposed (writes one row per trial and algorithm)
python -m benchmarking.run_benchmark --scenario configs/scenarios/scenario_03.yaml --trials 10
```

## Architecture

- **Robots**: independent processes (`robots/robot_node.py`)
- **Planning**: space-time A* + windowed reservation table
- **Safety**: ORCA local collision avoidance
- **Tasks**: decentralized auction (Contract Net Protocol)
- **Comms**: UDP broadcast JSON (no broker)
- **Evaluation**: deterministic digital-twin simulator, fault scenarios, and CSV metrics

## Docker

```bash
cd deployment/docker
docker compose up --build
```

## Project Structure

See `docs/architecture.md` for full details.

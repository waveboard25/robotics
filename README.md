# MeshFleet

Decentralized edge-AI fleet coordination for warehouse AMRs.

Each robot runs as an independent OS process communicating over UDP broadcast with no central decision server. Coordination uses space-time A* with reservation tables, ORCA local avoidance, priority-based conflict resolution, and Contract Net Protocol task allocation.

## Setup on Windows

Run these commands from the repository root, the folder containing
`requirements.txt`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `.venv\Scripts\activate.bat` from
`cmd.exe`, or allow local scripts for your user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Run modules with `python -m ...` from the repository root so imports such as
`communication`, `robots`, and `simulation` resolve correctly.

## Browser dashboard

The dashboard listens to the same UDP telemetry as the visualizer and presents a
live warehouse map, robot locations and status, battery levels, task assignments,
and scenario events in a browser.

Start the dashboard in one terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m dashboard.app --scenario configs/scenarios/scenario_03.yaml
```

Open <http://127.0.0.1:8000>, then start the scenario in a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m simulation.scenarios.runner --scenario configs/scenarios/scenario_03.yaml
```

The dashboard API is available at `/api/state`, and the live browser stream uses
the `/ws` WebSocket endpoint. The default UDP port is `5000`; override it with
`--udp-port` when running a fleet on another port.

## Run the live scenario without the dashboard

```powershell
.\.venv\Scripts\Activate.ps1
python -m simulation.scenarios.runner --scenario configs/scenarios/scenario_03.yaml
```

The runner starts one process per robot, announces the configured tasks, and
delivers scenario events such as the aisle 4 blockage at tick 25. To see robot
logs directly, add `--no-headless`:

```powershell
python -m simulation.scenarios.runner `
  --scenario configs/scenarios/scenario_03.yaml `
  --no-headless
```

To run one robot by itself:

```powershell
python -m robots.robot_node --id R1 --spawn-x 1 --spawn-y 1
```

## Test and benchmark

```powershell
python -m pytest tests -v
python -m benchmarking.run_benchmark --scenario configs/scenarios/scenario_03.yaml --trials 10
```

The benchmark writes its CSV output under `benchmarking/results/`.

## If Python reports a Git conflict marker

An error such as:

```text
SyntaxError: invalid syntax
at a line containing a Git merge marker
```

means Git conflict markers were left inside a source file. They are not Python
syntax. This commonly happens when a merge or pull operation was interrupted.
Do not try to fix this by changing Python indentation. From the repository
root, inspect the markers:

```powershell
Select-String -Path .\simulation\scenarios\runner.py `
  -Pattern '<<<<<<<|=======|>>>>>>>'
```

Open the file and keep the correct version of each section, deleting all three
marker lines and the unwanted duplicate section. Then verify the file:

```powershell
python -m py_compile .\simulation\scenarios\runner.py
python -m pytest tests -q
```

If you want to discard a local conflicted copy and restore the latest committed
version, first make a backup if it contains work, then run:

```powershell
git restore .\simulation\scenarios\runner.py
```

The error path `C:\Users\91944\meshfleet\...` is a different checkout from an
isolated worktree. Verify `git status` and `git log -1` in the directory where
you run Python.

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

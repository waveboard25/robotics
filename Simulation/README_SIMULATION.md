# MeshFleet — 3D AMR Warehouse Simulator

**SIH26-26123 — Edge-AI Based Distributed Fleet Coordination for AMRs in Smart Warehouses**
Scope owned by this deliverable: **3D simulation, integration interfaces, and hardware
deployment documentation.** No physical hardware is built. No teammate's algorithm
(P2P mesh comms, path planning, conflict resolution, task allocation, edge-AI, dashboard)
is implemented here — this package only gives those modules something real to plug into.

---

## 1. What's in this deliverable

| Piece | File(s) | What it is |
|---|---|---|
| 3D visual simulator | `simulator.html` | Self-contained, browser-based, presentation-ready 3D warehouse with up to 10 AMRs. Open it, click Start, pick a scenario. No install, no server. |
| Python reference engine | `meshfleet_sim/` | A second, behavior-identical implementation of the same simulation physics/state-machine, as an importable Python package, for teammates to build and unit-test their modules against without a browser. |
| Interface documentation | `SIMULATION_INTERFACES.md` | The data contract (`RobotState`, `EnvironmentState`, `RobotCommand`, `Task`, `CollisionEvent`) every other module talks to. |
| Hardware docs | `HARDWARE_ARCHITECTURE.md`, `SIMULATION_TO_HARDWARE.md`, `DEPLOYMENT_ROADMAP.md` | How this would become a real AMR fleet — future work, clearly labelled as such. |
| Judge prep | `HARDWARE_JUDGE_QA.md` | 40 rehearsed answers to likely hardware questions. |

## 2. Why two implementations of the same simulator?

`simulator.html` cannot be reached by a Python process running elsewhere (it runs in the
judge's / your browser). Teammates writing Python modules still need something to develop
against. So the same physics/state-machine is implemented twice, kept in lockstep by
sharing one written contract (`SIMULATION_INTERFACES.md`) and the same default warehouse
layout:

- **`simulator.html`** — what you *demo*. Everything (physics, rendering, scenarios, UI)
  is self-contained JavaScript + Three.js. This is the polished, "wow factor" artifact.
- **`meshfleet_sim/` (Python)** — what teammates *develop against*. Same field names, same
  physics constants, same 8 scenarios, importable as a normal Python package, runnable
  headless (`python -m meshfleet_sim.run_scenario 1`) for fast iteration/CI without any
  rendering.

If, later, the team wants the *browser* to be driven live by *real* teammate Python
modules (rather than the browser's own built-in demo logic), the natural next step is to
put a thin WebSocket/REST bridge in front of `SimulationEngine` and have `simulator.html`
poll it instead of stepping its own copy — see the "Bridging the two" note in
`SIMULATION_INTERFACES.md`. That bridge is not required for the SIH demo and was not built,
to keep the demo laptop-only and dependency-free.

## 3. Running the 3D simulator

No build step, no server required.

```
Just open simulator.html in any modern desktop browser (Chrome/Edge/Firefox).
```

Controls:
- **Start / Pause / Reset** — bottom-left panel.
- **Simulation speed** — slider, 0x–4x.
- **Scenario** dropdown — jumps straight to any of the 8 demo scenarios (Part 13).
- **Fleet size** dropdown — 3 / 5 / 10 robots.
- **Left-drag** to orbit the camera, **right-drag** to pan, **scroll** to zoom.
- **Click a robot** to open its live inspector panel (ID, battery, state, task,
  destination, speed, position, comm status) on the right.
- The event log (top-left) streams every simulation event (route set, collision,
  aisle blocked, low battery, safety stop, destination reached, etc.) with a timestamp.

## 4. Running scenarios headlessly (Python)

```bash
cd meshfleet_sim/..
python -m meshfleet_sim.run_scenario 1 --seconds 15 --every 2.5
```

`scenario` is 1–8 (matches Part 13 numbering exactly in both implementations).
This prints event log lines plus periodic JSON snapshots of every robot's state —
useful for a teammate to eyeball real engine output while developing, or to write
assertions against in a quick test script.

## 5. How teammates connect their modules

Nobody needs to touch simulator internals. Two supported paths:

**A. Python-side development (recommended for path planning / task allocation / conflict
resolution / edge-AI prototyping):**
```python
from meshfleet_sim import SimulationEngine, RobotCommand, CommandType, Task

engine = SimulationEngine()
engine.add_robot("AMR-01", x=-18, z=-9)

# your planner computes a route -> hand it to the engine
engine.set_route("AMR-01", route=[[-18,-9], [-6,-9], [-6,0]], destination="D-01")

# your conflict-resolution module can issue commands
engine.send_command(RobotCommand(type=CommandType.WAIT, target="AMR-01"))

# read the world back out (this is exactly what your module should consume)
env = engine.get_environment_state()
```

**B. Browser-side (recommended for dashboard prototyping):**
```javascript
// simulator.html exposes window.MeshFleet — open devtools console and try:
MeshFleet.getEnvironmentState()
MeshFleet.sendCommand({type:"STOP", target:"AMR-01"})
MeshFleet.assignTask({task_id:"T-99", pickup_location:"P-01", drop_location:"D-02", priority:1})
```
A dashboard module can be built as a second HTML page / React app that talks to
`window.MeshFleet` if hosted in the same page, or — for a genuinely separate
dashboard process — via the WebSocket bridge idea described above.

Full field-by-field schema documentation: see `SIMULATION_INTERFACES.md`.

## 6. Project structure

```
meshfleet/
├── simulator.html                  ← the 3D demo (open this)
├── docs/
│   ├── README_SIMULATION.md
│   ├── SIMULATION_INTERFACES.md
│   ├── HARDWARE_ARCHITECTURE.md
│   ├── SIMULATION_TO_HARDWARE.md
│   ├── HARDWARE_JUDGE_QA.md
│   └── DEPLOYMENT_ROADMAP.md
└── meshfleet_sim/                  ← Python reference engine (importable package)
    ├── __init__.py
    ├── schemas.py                  ← RobotState / EnvironmentState / RobotCommand / Task / CollisionEvent
    ├── warehouse_layout.py         ← default warehouse config (data, not hard-coded logic)
    ├── engine.py                   ← physics + state machine + collision detection
    ├── mock_comm.py                ← standalone mock of the future P2P comms interface
    ├── scenarios.py                ← the 8 demo scenarios
    └── run_scenario.py             ← CLI: run a scenario headless, print JSON snapshots
```

## 7. What this is / is not

**Is:** a working 3D simulation of a multi-AMR warehouse with physically plausible
movement, collision *detection*, battery modelling, dynamic obstacles, and a clean,
documented interface other modules can call.

**Is not:** a path planner, a conflict-resolution algorithm, a task-allocation system, an
edge-AI model, a fleet dashboard, or physical hardware. Those are explicitly out of scope
for this piece of the project and are owned by teammates (software) or are future work
(hardware) — see `DEPLOYMENT_ROADMAP.md`.

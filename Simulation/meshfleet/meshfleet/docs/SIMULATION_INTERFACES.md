# MeshFleet Simulation — Integration Interfaces

This is the contract between the simulator (this deliverable) and every other MeshFleet
module. It is implemented identically in two places:

- JavaScript: `simulator.html`, exposed as the global `window.MeshFleet` object.
- Python: `meshfleet_sim/schemas.py` + `meshfleet_sim/engine.py`.

If you're writing the path planner, conflict resolution, task allocation, edge-AI, mesh
comms, or dashboard module, this document is everything you need to know about the
simulator — you should not need to read `engine.py` internals.

```
        ┌───────────────┐        RobotCommand         ┌─────────────────────┐
        │  Path planner │ ───────────────────────────▶ │                     │
        └───────────────┘                              │                     │
        ┌───────────────┐        Task                  │   MeshFleet         │
        │ Task allocator│ ───────────────────────────▶ │   Simulator         │
        └───────────────┘                              │  (this deliverable) │
        ┌───────────────┐        RobotCommand(STOP...) │                     │
        │Conflict resolv│ ───────────────────────────▶ │                     │
        └───────────────┘                              │                     │
        ┌───────────────┐        Obstacle/Aisle events │                     │
        │  Edge-AI /     │ ◀─────────────────────────  │                     │
        │  P2P comms     │        EnvironmentState      │                     │
        └───────────────┘ ◀─────────────────────────  │                     │
        ┌───────────────┐        EnvironmentState       │                     │
        │  Dashboard     │ ◀─────────────────────────  │                     │
        └───────────────┘                              └─────────────────────┘
```

## 1. Core data shapes

### RobotState (what the simulator reports about one robot)
| Field | Type | Notes |
|---|---|---|
| `robot_id` | string | e.g. `"AMR-01"` |
| `position` | `{x, y, z}` | world coordinates, meters-equivalent units; `y` is always 0 (ground-plane robot) |
| `orientation` | float (radians) | yaw, 0 = facing +z |
| `velocity` | float | current scalar speed along heading |
| `battery` | float 0–100 | percent |
| `current_task` | string \| null | task_id if assigned |
| `destination` | string \| null | human-readable target (station id, "patrol", etc.) |
| `current_route` | list of `[x, z]` | remaining waypoints, in order |
| `current_state` | enum | `IDLE \| MOVING \| WAITING \| AVOIDING \| REROUTING \| CHARGING \| BLOCKED \| ERROR` |
| `communication_status` | string | `ONLINE \| STALE \| OFFLINE` (simulation always reports ONLINE; a real comms module would set this) |
| `timestamp` | float | simulation clock, seconds |

### EnvironmentState (the whole virtual world, one snapshot)
| Field | Type |
|---|---|
| `warehouse` | warehouse layout config object (see below) |
| `obstacles` | list of `{id, x, z, r, temporary}` |
| `blocked_aisles` | list of `{id, box:{xMin,xMax,zMin,zMax}, temporary}` |
| `robot_states` | list of `RobotState` |
| `simulation_time` | float, seconds |

### RobotCommand (what other modules send **to** a robot)
| Field | Type | Notes |
|---|---|---|
| `type` | enum | `SET_ROUTE \| STOP \| WAIT \| RESUME \| REROUTE \| GO_TO_CHARGER \| SET_VELOCITY` |
| `target` | string | robot_id |
| `route` | list of `[x, z]` | required for `SET_ROUTE` / `REROUTE` |
| `velocity` | float | required for `SET_VELOCITY` |
| `destination` | string | optional human-readable label |

`STOP` is a hard safety command: the simulator zeroes velocity and clears the route on the
next physics tick, unconditionally, regardless of any planner logic. This is the "physical
brake", not a suggestion.

### Task
| Field | Type |
|---|---|
| `task_id` | string |
| `pickup_location` | station id, e.g. `"P-01"` |
| `drop_location` | station id, e.g. `"D-03"` |
| `priority` | int |

Assigning a `Task` does **not** move a robot by itself — the simulator only records and
displays it. A route still has to be handed to the robot via `SET_ROUTE` (normally by the
path planner, once the task allocator has decided who gets the task).

### CollisionEvent (what the simulator reports **from** its physics)
| Field | Type |
|---|---|
| `timestamp` | float |
| `robot_a` | robot_id |
| `robot_b_or_obstacle` | robot_id or obstacle_id |
| `location` | `{x, z}` |
| `severity` | `LOW \| MEDIUM \| HIGH` |

## 2. Warehouse layout config

A plain data object (`build_default_warehouse_layout()` in Python /
`buildDefaultWarehouseLayout()` in JS): `bounds`, `racks[]`, `aisles`, `intersections[]`,
`pickupStations[]`, `dropStations[]`, `chargingStations[]`, `staticObstacles[]`. Swap this
object (or point the loader at a different one) to change the warehouse without touching
simulation logic. Coordinates are `(x, z)` in a flat ground plane; `gridScale: 1` means
route waypoints are given directly in the same units as everything else (no separate
grid-index system to convert).

## 3. Function-level API

### Python (`meshfleet_sim.SimulationEngine`)
```
engine.add_robot(robot_id, x, z) -> RobotState
engine.get_robot_state(robot_id) -> RobotState | None
engine.get_environment_state() -> EnvironmentState
engine.set_route(robot_id, route, destination=None) -> bool
engine.assign_task(task: Task) -> None
engine.send_command(cmd: RobotCommand) -> {"ok": bool, ...}
engine.add_obstacle(id, x, z, r=0.6, temporary=False, duration=None)
engine.remove_obstacle(id)
engine.block_aisle(id, box, temporary=False, duration=None)
engine.unblock_aisle(id)
engine.on_event(callback)          # callback(event_name: str, payload: dict)
engine.step(dt)                    # advance physics by dt seconds
engine.run_for(seconds, dt=0.1)    # convenience loop for headless testing
```

### JavaScript (`window.MeshFleet`, inside `simulator.html`)
```js
MeshFleet.getEnvironmentState()
MeshFleet.getRobotState(id)
MeshFleet.sendCommand({type, target, route, velocity, destination})
MeshFleet.setRoute(id, route, opts)
MeshFleet.assignTask(task)
MeshFleet.addObstacle(id, x, z, r, opts)
MeshFleet.removeObstacle(id)
MeshFleet.blockAisle(id, box, opts)
MeshFleet.unblockAisle(id)
MeshFleet.onEvent(fn)              // fn(eventName, payload)
MeshFleet.loadScenario(n)
MeshFleet.listRobots()
```

## 4. Events emitted by the simulator

`ROUTE_SET`, `TASK_ASSIGNED`, `SAFETY_STOP`, `OBSTACLE_ADDED`, `OBSTACLE_REMOVED`,
`AISLE_BLOCKED`, `AISLE_UNBLOCKED`, `COLLISION`, `LOW_BATTERY`, `CHARGE_START`,
`CHARGE_COMPLETE`, `DESTINATION_REACHED`.

Any module can subscribe (`on_event` / `onEvent`) instead of polling `EnvironmentState`
every tick — this is the natural hook point for a P2P comms module deciding what to gossip
to peers, or a dashboard deciding what to log.

## 5. What the simulator deliberately does **not** decide

- **Which route a robot takes** — it only follows whatever `SET_ROUTE`/`REROUTE` gives it.
  A hard-coded straight line to the next waypoint is *not* a path planner.
- **What to do about a collision or near-miss** — it reports `COLLISION` and puts the
  robots in `WAITING`/`AVOIDING`; deciding who yields, replans, or waits how long is
  conflict resolution's job.
- **Who gets a task** — `assign_task` just records a task against a robot id someone else
  already chose.
- **When AI should override anything** — the simulator has no AI in it. Any "smart"
  decision is made outside and expressed back as a `RobotCommand` or a new route.

## 6. Mock communication vs. real P2P/mesh module

`meshfleet_sim.MockCommBus` (Python) implements four calls — `send_state`,
`receive_state`, `send_command`, `receive_environment_update` — as direct, zero-latency
function calls into the engine. It exists purely so other modules can be written today
against a stable interface. A real mesh/P2P module should implement the **same four
call signatures** over its actual transport (sockets, DDS, MQTT, etc.); nothing else
in the codebase needs to change when the mock is swapped out. This mirrors the real
hardware picture, where each robot only has its own edge computer's view of the world
plus whatever peers have told it — see `HARDWARE_ARCHITECTURE.md`.

## 7. Bridging the browser demo and the Python engine (not built, documented for later)

If the team later wants the visual `simulator.html` to be driven live by real teammate
Python modules instead of its own built-in demo logic, the standard approach is:

1. Run `SimulationEngine` inside a small Python process with a WebSocket or REST endpoint
   that serializes `get_environment_state()` and accepts `RobotCommand`/`Task`/route JSON.
2. Point `simulator.html` at that endpoint instead of stepping its own local copy of the
   physics (swap `stepSimulation()`'s call site for a `fetch`/`WebSocket` message handler
   that overwrites `Sim.robots` from the server's snapshot each tick).

This was intentionally **not** built for the SIH demo, to keep the visual simulator a
single, dependency-free HTML file that works offline on any laptop with no server to
keep running during the presentation.

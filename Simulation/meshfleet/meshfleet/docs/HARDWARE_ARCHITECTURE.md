# MeshFleet — Real-World Hardware Deployment Architecture

> **Status: [FUTURE HARDWARE DEPLOYMENT].** Nothing in this document is built. It exists
> so the team can talk credibly about how the simulation would become a real AMR fleet,
> and so hardware-related judge questions have a rehearsed, honest answer.

## 1. Per-robot architecture

```
                              REAL AMR
                                 │
        ┌────────────────────────┼────────────────────────┐
        ↓                        ↓                         ↓
    Sensors                Localization                Encoders
  (LiDAR / depth        (IMU + wheel odometry       (wheel encoders,
   camera / ultrasonic /  + optional SLAM /           feed into
   bumper)                AprilTag fiducials)         localization)
        │                        │                         │
        └────────────────────────┼─────────────────────────┘
                                 ↓
                          Edge Computer
                    (Raspberry Pi-class or
                     NVIDIA Jetson-class)
                                 │
                         MeshFleet Node
              (local safety loop + local state +
               interfaces identical to
               SIMULATION_INTERFACES.md)
                                 │
                           P2P Network
                        (Wi-Fi / mesh radio)
                                 │
             ┌───────────────────┼───────────────────┐
             ↓                   ↓                   ↓
          AMR-01               AMR-02               AMR-03
                                 │
                                 ↓
                        Motor Control Layer
              (motor controller → BLDC/DC motors → wheels,
               with hardware velocity/current limits
               independent of software)
```

## 2. Why the interfaces stay the same

The MeshFleet Node on a real AMR is meant to expose and consume the *same*
`RobotState` / `EnvironmentState` / `RobotCommand` / `Task` / `CollisionEvent` shapes
documented in `SIMULATION_INTERFACES.md`. A path planner, conflict-resolution module, or
task allocator written and tested against the simulator should not need to change when
it starts talking to a real robot — only the thing underneath the interface changes
(simulated physics → real sensors/motors). This is the whole point of designing the
interface first.

## 3. Hardware categories (options, not a bill of materials)

None of the following is mandatory in every combination — the right set depends on
budget, indoor GPS-denied navigation needs, and how much onboard AI inference is wanted.

**Edge computing**
- *Raspberry Pi–class* (e.g. Pi 4/5): cheap, low power, enough for ROS 2 node logic,
  encoder/IMU fusion, and basic obstacle-avoidance rules. Not enough for real-time
  camera-based deep-learning inference at speed.
- *NVIDIA Jetson–class* (e.g. Orin Nano/NX): GPU-accelerated, suited to camera/LiDAR
  perception, SLAM, and on-device AI models. Higher cost and power draw.

**Localization**
- Wheel encoders (relative odometry, drifts over time — cheap, always used as a baseline).
- IMU (improves heading estimate, corrects some drift).
- LiDAR (2D LiDAR SLAM is a common, affordable, robust choice for structured warehouses).
- Camera + AprilTags (cheap absolute position fixes at known tag locations — popular in
  student/low-cost AMR builds because it avoids full SLAM).
- Sensor fusion (encoders + IMU + LiDAR/tags via an extended Kalman filter or similar) —
  what a production AMR actually uses; no single sensor is trusted alone.

**Obstacle detection**
- LiDAR (accurate range, works in most lighting, moderate cost).
- Depth camera (good for shorter-range 3D obstacle shapes, cheaper than LiDAR).
- Ultrasonic / ToF sensors (cheap, short-range, good as a last-resort bumper ring).
- Physical bumper / emergency-stop switch (hard safety layer, independent of software).

**Motion**
- Motor controller (translates velocity commands into PWM/current for motors).
- DC or BLDC motors with wheel encoders (closed-loop speed control).

**Network**
- Wi-Fi (simplest, sufficient for a warehouse-scale mesh at modest robot counts).
- Ethernet (only relevant for fixed infrastructure, e.g. a base station).
- Other wireless mesh radios where Wi-Fi congestion becomes a problem at larger fleet sizes.

**Power**
- Battery (typically Li-ion/LiFePO4 for AMRs).
- BMS (battery management system) for safe charge/discharge.
- Charging station / dock, matching the simulator's `chargingStations`.

**Student prototype vs. industrial AMR:** a student prototype would realistically use a
Raspberry Pi or a single Jetson Nano/Orin Nano, 2D LiDAR or AprilTags for localization,
ultrasonic sensors as a cheap safety net, and Wi-Fi. An industrial AMR typically adds
redundant safety-rated LiDAR, a certified emergency-stop circuit, sensor fusion with SLAM,
and often a dedicated safety microcontroller separate from the "smart" compute — because
certification requirements (e.g. ISO 3691-4 for AMRs) demand a safety layer that cannot be
taken down by a software bug.

## 4. Edge computing rationale (Part 20)

- **Lower latency:** obstacle reaction and local coordination decisions happen in
  milliseconds on-device, not round-tripped to a cloud server.
- **Reduced cloud dependency:** the fleet keeps operating inside the warehouse even if the
  facility's internet uplink is down — only local Wi-Fi/mesh is required.
- **Operation during unreliable connectivity:** each robot's edge computer holds enough
  local state (its own position, its last known safe world state) to keep behaving safely
  without a live link.
- **Local safety decisions:** a hard stop for an about-to-collide robot cannot wait for a
  cloud round trip; it must be decided on the robot.
- **Scalability:** compute cost scales with the fleet (each robot brings its own compute),
  instead of one central server having to handle every robot's sensor stream at once.
- **Privacy:** raw camera/LiDAR data can stay on-premises rather than being streamed
  off-site.
- **Distributed decision-making:** matches the project's actual architecture — coordination
  is peer-to-peer, not dependent on one central brain (see Part 5's constraint that the
  simulation state must not become a conceptual centralized controller).

**What should *not* move entirely to the cloud:** anything on the safety-critical path —
collision avoidance, emergency stop, and the immediate local motion-control loop. The
cloud (or a facility server) is a reasonable place for fleet-wide analytics, long-term
route optimization, dashboards, and non-time-critical AI model updates — never for the
decision "should this robot stop right now."

## 5. Network failure behaviour (Part 21)

```
Wi-Fi goes down for AMR-03
        │
        ▼
1. AMR-03 continues using its own locally known safe state
2. Stale peer information (positions it can no longer refresh) is discarded/aged out
3. Hard safety rules (obstacle stop, speed limits) remain active regardless of network
4. AMR-03 slows down / stops if it can no longer confirm the area ahead is clear
5. Communication resumes
6. AMR-03 re-broadcasts its current state to peers
7. Route/coordination is recalculated by the planning/coordination module with fresh data
```
This is the intended design behaviour; it has not been implemented or tested on hardware,
since no hardware exists yet — it is documented as the plan, not a verified result.

## 6. Edge computer failure behaviour (Part 22)

- Peers detect a missing/stale heartbeat from the failed robot (timeout-based).
- The failed robot is expected to fail safe — stop rather than continue moving blind.
- Any task assigned to it is reassigned by the task-allocation module once it's marked
  unavailable.
- The failed robot is removed from active coordination (peers stop waiting on it,
  stop planning around its stale reported position).
- On recovery/reboot, the robot re-announces itself and rejoins coordination.

## 7. Safety hierarchy (Part 26)

```
                HARD SAFETY
      (bumper / e-stop / motor current limits —
       cannot be overridden by any software layer)
                    ↓
       DETERMINISTIC COLLISION AVOIDANCE
      (rule-based: stop/slow when something is
       too close, regardless of what any planner
       or AI wants)
                    ↓
                PATH PLANNING
        (decides *where* to go, assuming the
         above two layers keep it safe)
                    ↓
              AI OPTIMIZATION
        (traffic prediction, task sequencing,
         throughput optimization — a suggestion
         layer, never a safety layer)
```
AI must never be able to override hard safety or deterministic collision avoidance. For a
real deployment this also requires, beyond software: a physical emergency-stop button,
hardware-enforced motor speed/current limits, dedicated obstacle sensors wired into a
stop circuit independent of the main compute, watchdog timers that force a safe stop if
the main process hangs, and a well-defined fail-safe state (wheels braked, beacon on,
awaiting reset) for every failure mode.

# MeshFleet — Physical Deployment Roadmap

> **Status: [FUTURE HARDWARE DEPLOYMENT].** Describes a plausible path from this
> simulation to physical robots. None of Phases 3–5 have been built or funded.

## Phase 1 — 3D Simulation *(this deliverable — done)*
- **Hardware:** none.
- **Software:** `simulator.html` (visual demo) + `meshfleet_sim` (Python reference
  engine) + documented interfaces.
- **Testing:** the 8 scenarios, run both visually and headlessly.
- **Risks:** simulation fidelity gaps (see `SIMULATION_TO_HARDWARE.md`) could hide
  problems that only appear on real sensors/motors.
- **Expected outcome:** a working, judge-demoable proof of the coordination concept and
  a stable interface for every other module to build against.

## Phase 2 — Software-in-the-loop testing
- **Hardware:** none (or one dev laptop only).
- **Software:** real teammate modules (path planner, conflict resolution, task
  allocator, edge-AI, real P2P comms) wired to `SimulationEngine` in place of the mock
  logic/`MockCommBus`, still against simulated physics.
- **Testing:** the same 8 scenarios, now exercising real algorithms instead of the
  simulator's placeholder behaviour (e.g. actual conflict resolution instead of
  "both robots just wait").
- **Risks:** integration bugs at module boundaries; timing assumptions that don't hold
  once modules run asynchronously instead of in one process.
- **Expected outcome:** confidence that the *algorithms*, not just the visuals, work.

## Phase 3 — One physical AMR
- **Hardware:** one low-cost chassis, one edge computer (Raspberry Pi or Jetson Nano
  class), motor controller + motors + encoders, one localization method (e.g. AprilTags
  or 2D LiDAR), basic obstacle sensors (ultrasonic ring), battery + charging dock.
- **Software:** MeshFleet Node ported to run on the real edge computer, same interfaces,
  now backed by real sensor drivers instead of simulated values.
- **Testing:** the robot alone repeats simple versions of the simulated scenarios
  (follow a route, stop for an obstacle, go charge at low battery) in a small real
  test area.
- **Risks:** localization drift, sensor noise, real-world timing very different from
  simulation; safety hardware (e-stop) must be proven before any autonomous motion.
- **Expected outcome:** proof that the simulated interfaces and behaviours transfer to
  one real robot.

## Phase 4 — Three physical AMRs
- **Hardware:** two more units identical to Phase 3's.
- **Software:** real P2P/mesh communication between the three robots; multi-robot
  scenarios (overlapping routes, intersection contention, narrow-aisle face-off) repeated
  physically.
- **Testing:** the same scenario set as the simulator's Scenarios 1–3, now for real.
- **Risks:** real network unreliability (Wi-Fi interference, range), true concurrency
  bugs that a single-process simulation can't surface, physical collision risk during
  early testing (should be done at low speed with a human supervisor / kill switch).
- **Expected outcome:** validated multi-robot coordination, including graceful handling
  of communication loss (Part 21) and one robot's failure (Part 22).

## Phase 5 — Larger fleet
- **Hardware:** additional units, larger test/production floor.
- **Software:** scaling considerations for the mesh network and coordination algorithm
  at higher robot counts (see `HARDWARE_JUDGE_QA.md` Q24–25 for how this is expected to
  degrade gracefully rather than assume it scales for free).
- **Testing:** load/throughput testing, congestion scenarios, larger-scale battery/
  charging-station capacity planning.
- **Risks:** network congestion, charging-station contention, task-allocation fairness
  at scale — none of these are validated by a 3-robot Phase 4.
- **Expected outcome:** a fleet-scale operational picture, informing whether industrial-
  grade hardware (redundant sensors, certified safety systems) is now warranted.

---

## Cost estimate (India market, rough order-of-magnitude, Phase 3-level prototype)

**These are estimates only, will vary by vendor/import duty/exact spec, and are not a
procurement commitment — we are not buying these components now.**

| Component | Low-cost prototype | More capable prototype |
|---|---|---|
| Chassis (frame, wheels) | ₹3,000 – 6,000 | ₹10,000 – 20,000 |
| Motors (DC gear motors → BLDC) | ₹1,500 – 3,000 | ₹6,000 – 12,000 |
| Motor driver | ₹500 – 1,200 | ₹2,000 – 4,000 |
| Microcontroller (e.g. STM32/Arduino-class, for low-level motor/encoder loop) | ₹500 – 1,500 | ₹1,500 – 3,000 |
| Edge computer | ₹4,000 – 6,000 (Raspberry Pi–class) | ₹25,000 – 45,000 (Jetson Orin Nano–class) |
| Battery + BMS | ₹2,000 – 4,000 | ₹6,000 – 12,000 |
| Localization (AprilTag camera setup) | ₹1,500 – 3,000 | — |
| Localization (2D LiDAR) | — | ₹15,000 – 35,000 |
| Obstacle sensors (ultrasonic/ToF set) | ₹800 – 2,000 | ₹3,000 – 6,000 (adds depth camera) |
| Communication (Wi-Fi, on-board) | usually included on Pi/Jetson | usually included |
| **Rough total per robot** | **≈ ₹14,000 – 27,000** | **≈ ₹68,000 – 1,37,000** |

A three-robot Phase 4 fleet at the low-cost tier is therefore very roughly ₹40,000 –
₹80,000 in components alone, before mounting hardware, cabling, a charging dock, and
engineering time — and this excludes any safety-certified components an industrial
deployment would require.

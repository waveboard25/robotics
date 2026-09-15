# MeshFleet — Simulation ↔ Hardware Mapping

Every simulated concept below is chosen so that it can be defended technically in front of
judges: what it maps to, and *why* that's a reasonable stand-in.

```
                 REAL WORLD                                SIMULATION
        ────────────────────────────            ─────────────────────────────
        LiDAR / depth camera / ultrasonic   →    CollisionEvent generation from
                                                  geometric distance checks between
                                                  robot, obstacle, and rack shapes
        ────────────────────────────────────────────────────────────────────────
        Wheel encoders                       →   Direct, exact odometry — position
                                                  is known perfectly in `RobotState.position`
                                                  (a real robot only *estimates* this)
        ────────────────────────────────────────────────────────────────────────
        IMU                                  →   `orientation` (yaw) field, updated
                                                  by the motion model each tick
        ────────────────────────────────────────────────────────────────────────
        Camera-based perception              →   None modelled directly; obstacles are
                                                  given ground-truth positions instead of
                                                  being "detected" — see limitations below
        ────────────────────────────────────────────────────────────────────────
        Motor controller + motors            →   Acceleration/deceleration-limited
                                                  velocity model (`ACCEL`, `DECEL`,
                                                  `MAX_SPEED` constants in engine.py)
        ────────────────────────────────────────────────────────────────────────
        Battery + BMS                        →   Linear battery-percentage model:
                                                  drains while moving, recovers at a
                                                  fixed rate at a charging station
        ────────────────────────────────────────────────────────────────────────
        Wi-Fi / mesh network                 →   `MockCommBus` — same-process function
                                                  calls with zero latency, zero packet loss
        ────────────────────────────────────────────────────────────────────────
        Raspberry Pi / Jetson (per robot)    →   One robot's state + control loop inside
                                                  the shared simulation process (no real
                                                  per-robot compute isolation)
        ────────────────────────────────────────────────────────────────────────
        Physical warehouse (racks, aisles,   →   `warehouse_layout.py` / the 3D scene in
        docks, chargers)                         `simulator.html` — same topology, to scale
        ────────────────────────────────────────────────────────────────────────
        Physical AMR chassis                 →   3D robot mesh + `RobotState` record
        ────────────────────────────────────────────────────────────────────────
        Emergency-stop button / hardware     →   `STOP` RobotCommand (software-only —
        safety circuit                           see limitations)
```

## Honest limitations of this mapping

These are the gaps a judge is entitled to press on, and the honest answers:

1. **Perception is ground-truth, not sensed.** The simulator knows exactly where every
   obstacle is; it does not simulate what a LiDAR scan or camera frame would actually
   look like, or the false negatives/latency a real perception stack has. A real AMR's
   `EnvironmentState` would be built from noisy sensor fusion, not handed to it perfectly.
2. **Odometry is perfect.** Real wheel encoders drift; real localization needs correction
   (SLAM, fiducials, sensor fusion). The simulation currently has no positional drift or
   sensor noise model.
3. **Network is idealized.** `MockCommBus` has no latency, no packet loss, no bandwidth
   limits. A real mesh network would need the `communication_status` field to genuinely
   reflect `STALE`/`OFFLINE` conditions and modules to handle stale data gracefully — the
   simulator's schema already reserves this field for that purpose, but the mock doesn't
   yet exercise it.
4. **`STOP` is a software command here; on real hardware it must also exist as a
   hardware-level circuit** independent of any onboard software, so a frozen or crashed
   process cannot prevent an e-stop from working.
5. **Battery model is simplified.** Real battery discharge depends on load, terrain,
   temperature, and battery chemistry/age — not just "moving vs. not moving."

None of this is a flaw in the simulator for its stated purpose (giving other software
modules something realistic enough to develop against, and giving a visual demo); it is
simply the boundary of what's implemented vs. what real hardware would additionally need.

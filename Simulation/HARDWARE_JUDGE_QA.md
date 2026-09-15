# MeshFleet — Hardware Judge Q&A

Every answer is tagged **[IMPLEMENTED SIMULATION]** (true today, in this project) or
**[FUTURE HARDWARE DEPLOYMENT]** (planned/plausible, not built). Never say we built
physical hardware — we didn't.

---

**1. What hardware would run MeshFleet?**
SHORT: A small edge computer per robot (Raspberry Pi or Jetson class), plus motors,
encoders, a battery, and obstacle sensors. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Each AMR would carry its own edge computer running the MeshFleet Node
software, talking to a motor controller for movement, encoders/IMU for odometry, one or
more obstacle-detection sensors, and a Wi-Fi radio for mesh communication with other
robots. Today, all of that is represented in software only, inside our simulator.
[FUTURE HARDWARE DEPLOYMENT]

**2. Why Raspberry Pi?**
SHORT: Cheap, low-power, enough compute for the coordination logic and sensor fusion.
[FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A Raspberry Pi 4/5 class board can comfortably run a ROS 2 node, encoder/IMU
fusion, rule-based obstacle avoidance, and mesh networking, at low cost and power draw —
appropriate when the robot doesn't need onboard camera-based deep learning at speed.
[FUTURE HARDWARE DEPLOYMENT]

**3. Why Jetson?**
SHORT: When you need onboard AI/vision, a Jetson gives you a GPU for real-time inference.
[FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: NVIDIA Jetson boards add a GPU for camera-based perception, SLAM, or the
edge-AI teammate's model to run locally without a cloud round trip — at higher cost and
power than a Pi. We'd choose Jetson if the edge-AI module needs to do real-time vision
inference on the robot itself. [FUTURE HARDWARE DEPLOYMENT]

**4. Why edge computing?**
SHORT: Lower latency, keeps working without internet, and safety decisions can't wait for
the cloud. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Time-critical decisions — obstacle reaction, local safety stops — need
millisecond response, not a network round trip. Edge computing also lets the fleet keep
operating if the facility's uplink goes down, since only local mesh connectivity between
robots is required. See `HARDWARE_ARCHITECTURE.md` §4. [FUTURE HARDWARE DEPLOYMENT]

**5. Why not cloud?**
SHORT: Cloud is fine for analytics and optimization, not for anything safety-critical or
latency-sensitive. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: We'd keep collision avoidance, emergency stop, and local motion control fully
on-device. The cloud (or a facility server) is a reasonable home for fleet-wide analytics,
long-horizon route optimization, and dashboards — none of which need millisecond response
or must work when the network is down. [FUTURE HARDWARE DEPLOYMENT]

**6. What sensors would you use?**
SHORT: Wheel encoders and IMU always; then LiDAR or AprilTags for localization, plus
ultrasonic/depth sensors for obstacles. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A practical student-level sensor set is wheel encoders + IMU for odometry,
AprilTag fiducials or 2D LiDAR for absolute localization, and an ultrasonic/ToF ring
(cheap) or a depth camera (richer) for obstacle detection. Full detail in
`HARDWARE_ARCHITECTURE.md` §3. [FUTURE HARDWARE DEPLOYMENT]

**7. How does localization work?**
SHORT: Combine wheel-encoder odometry with an absolute fix (tags or LiDAR) so drift gets
corrected. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Wheel encoders alone drift over time; a sensor-fusion approach (e.g. an
extended Kalman filter combining encoders, IMU, and periodic absolute fixes from AprilTags
or LiDAR-based SLAM) is the standard real-AMR approach. Our simulation currently gives
robots perfect ground-truth position instead of estimating it — see
`SIMULATION_TO_HARDWARE.md` limitation #2. [FUTURE HARDWARE DEPLOYMENT] for the real
approach; [IMPLEMENTED SIMULATION] for how position is currently represented (perfectly).

**8. How does the AMR know where it is?**
SHORT: Sensor fusion of odometry plus an absolute reference like tags or a LiDAR map.
[FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Same as Q7 — no single sensor is trusted alone in a real deployment; the
simulator today simply stores exact `(x, z)` coordinates in `RobotState.position`.
[IMPLEMENTED SIMULATION] (for the simulated representation) / [FUTURE HARDWARE
DEPLOYMENT] (for how a real robot would estimate it).

**9. How would you detect obstacles?**
SHORT: LiDAR, a depth camera, or ultrasonic sensors, backed by a hardware bumper as a
last resort. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: In the simulator, obstacles are geometric shapes checked against robot
position each tick, producing a `CollisionEvent`. [IMPLEMENTED SIMULATION] On real
hardware, this would come from LiDAR/depth-camera/ultrasonic sensing plus a physical
bumper switch as a hardware-level backstop. [FUTURE HARDWARE DEPLOYMENT]

**10. Would you use LiDAR?**
SHORT: Yes, ideally — it's accurate and works in most warehouse lighting. [FUTURE
HARDWARE DEPLOYMENT]
TECHNICAL: 2D LiDAR is a common, robust choice for structured indoor spaces like a
warehouse; it's more expensive than ultrasonic sensors but far more reliable at range and
in varied lighting than a camera alone. We'd budget for it in the "more capable
prototype" tier of `DEPLOYMENT_ROADMAP.md`. [FUTURE HARDWARE DEPLOYMENT]

**11. Would cameras work?**
SHORT: Yes, especially for AprilTag-based localization or richer perception, but they
need more compute and are lighting-sensitive. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A camera plus AprilTags is a cheap way to get absolute position fixes without
full SLAM, and cameras also feed the edge-AI module's perception. The trade-off is
sensitivity to lighting and the need for more onboard compute (favoring Jetson over Pi
if vision is central). [FUTURE HARDWARE DEPLOYMENT]

**12. How do wheel encoders help?**
SHORT: They measure wheel rotation, giving relative odometry (how far/which way the robot
moved). [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Encoders are the cheapest, most reliable way to estimate motion between
absolute position fixes; they drift over time (wheel slip, uneven load) so they're always
paired with a correction source. Our simulation doesn't need this because position is
tracked exactly, but a real robot depends on it as the odometry baseline. [FUTURE
HARDWARE DEPLOYMENT]

**13. How would robots communicate?**
SHORT: Peer-to-peer over Wi-Fi (or a mesh radio), sharing state and coordination messages
directly. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: The architecture is decentralized — each robot's MeshFleet Node talks to
nearby peers rather than routing everything through one server, so the fleet keeps
functioning even if any single robot or link drops. Today this is represented by
`MockCommBus`, a same-process mock with zero latency. [IMPLEMENTED SIMULATION] for the
mock; [FUTURE HARDWARE DEPLOYMENT] for the real mesh network.

**14. What happens if Wi-Fi fails?**
SHORT: The robot keeps using its last known safe state, obeys hard safety rules, and
slows or stops if it can't confirm the area is clear. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: See the 7-step behaviour in `HARDWARE_ARCHITECTURE.md` §5 — stale peer data is
discarded, hard safety stays active regardless of connectivity, and coordination is
recalculated once the link returns. This is documented intended behaviour, not yet
implemented or tested on hardware. [FUTURE HARDWARE DEPLOYMENT]

**15. What happens if one robot disconnects?**
SHORT: Peers time it out, stop planning around its stale data, and its task gets
reassigned. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A heartbeat/timeout mechanism would mark the robot's last state as stale
(`communication_status = STALE/OFFLINE` in our schema) so other modules stop trusting it;
task allocation would reassign its work. [FUTURE HARDWARE DEPLOYMENT] — the schema field
exists today but isn't yet driven by a real timeout mechanism. [IMPLEMENTED SIMULATION]
for the schema field.

**16. What happens if one robot crashes (software crash)?**
SHORT: It should fail safe — stop moving — and get removed from active coordination
until it recovers. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A watchdog timer on the edge computer would force a safe stop if the main
process hangs or crashes; peers detect the missing heartbeat the same way as a network
disconnect (Q15) and reassign its task. See `HARDWARE_ARCHITECTURE.md` §6. [FUTURE
HARDWARE DEPLOYMENT]

**17. How would you control motors?**
SHORT: A motor controller converts velocity commands into motor signals, closed-loop with
encoder feedback. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: The MeshFleet Node would send a target velocity to a motor controller (PWM/
current control for DC or BLDC motors), which uses encoder feedback for closed-loop speed
control. In the simulator, this whole layer is replaced by an acceleration-limited
velocity model (`ACCEL`/`DECEL`/`MAX_SPEED` in `engine.py`). [IMPLEMENTED SIMULATION] for
the simulated version; [FUTURE HARDWARE DEPLOYMENT] for the real motor layer.

**18. What microcontroller would you use?**
SHORT: A small microcontroller (e.g. STM32/Arduino-class) for the tight motor/encoder
control loop, separate from the main edge computer. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Splitting a fast, deterministic low-level control loop (motor PWM, encoder
reading, e-stop wiring) onto a microcontroller, while the Pi/Jetson runs the higher-level
MeshFleet Node, is a common pattern — it keeps hard real-time motor control isolated from
a Linux process that might lag. [FUTURE HARDWARE DEPLOYMENT]

**19. Why ROS 2?**
SHORT: It's the standard robotics middleware for message passing between sensors,
control, and navigation — and it's well suited to a real deployment. [FUTURE HARDWARE
DEPLOYMENT]
TECHNICAL: ROS 2 (built on DDS) gives standardized publish/subscribe messaging, existing
drivers for common sensors/motor controllers, and tooling for multi-node robot software —
useful if/when this becomes real hardware. Our current software stack (the simulator and
Python engine) does not use ROS 2; it's a plain Python/JS implementation chosen for speed
of development during the hackathon. [FUTURE HARDWARE DEPLOYMENT] for real use; not used
in [IMPLEMENTED SIMULATION].

**20. What is DDS?**
SHORT: Data Distribution Service — the publish/subscribe networking standard ROS 2 is
built on. [FUTURE HARDWARE DEPLOYMENT — background knowledge]
TECHNICAL: DDS is a decentralized pub/sub protocol with no single broker, which fits a
decentralized fleet well — robots can discover and talk to each other without a central
server. It's the transport ROS 2 uses under the hood. This is background knowledge for a
future ROS 2–based implementation; not used in the current codebase.

**21. How does simulation translate to hardware?**
SHORT: Same data interfaces (robot state, environment state, commands) — only the layer
underneath changes, from simulated physics to real sensors and motors. [Both — see
`SIMULATION_TO_HARDWARE.md`]
TECHNICAL: We designed `RobotState`/`EnvironmentState`/`RobotCommand`/`Task`/
`CollisionEvent` first, and built the simulator to only ever talk in those shapes. A real
MeshFleet Node would produce/consume identical shapes, sourced from real sensors instead
of simulated geometry. See the full mapping table in `SIMULATION_TO_HARDWARE.md`.
[IMPLEMENTED SIMULATION] for the interface; [FUTURE HARDWARE DEPLOYMENT] for the real
sourcing of that data.

**22. What part is actually implemented?**
SHORT: The full 3D simulation, the Python reference engine, and the documented
interfaces. No hardware. [IMPLEMENTED SIMULATION]
TECHNICAL: `simulator.html` (visual demo, physics, 8 scenarios), `meshfleet_sim` (headless
Python engine with identical behaviour), and the interface/schema documentation are all
built and runnable today. [IMPLEMENTED SIMULATION]

**23. What part is future work?**
SHORT: Every physical component, plus the real path planner, conflict resolution, task
allocation, edge-AI model, and dashboard (owned by teammates in software; not this
deliverable). [FUTURE HARDWARE DEPLOYMENT] / teammates' software
TECHNICAL: All of Phases 3–5 in `DEPLOYMENT_ROADMAP.md` (physical robots), plus the real
algorithmic content of the coordination modules — the simulator only provides the
interface they plug into, not their logic. [FUTURE HARDWARE DEPLOYMENT]

**24. How would you scale to 10 robots?**
SHORT: The simulator already supports configuring the fleet size to 10; the mesh network
and coordination logic would need to handle proportionally more peer traffic. [Both]
TECHNICAL: `simulator.html`'s fleet-size selector runs 10 robots today with the same
physics and scenarios. [IMPLEMENTED SIMULATION] On real hardware, 10 robots on a single
Wi-Fi mesh is generally fine bandwidth-wise; the harder part is making sure conflict
resolution and task allocation scale in message volume, not just robot count. [FUTURE
HARDWARE DEPLOYMENT]

**25. How would you scale to 100 robots?**
SHORT: That's beyond gossip-style peer-to-peer messaging for most Wi-Fi deployments —
you'd need zone-based coordination and network capacity planning. [FUTURE HARDWARE
DEPLOYMENT]
TECHNICAL: At 100 robots, broadcasting full state to every peer becomes network-heavy;
a real system would likely partition the warehouse into zones with local coordination
and only exchange summarized information across zone boundaries, plus consider
higher-capacity or multiple access points. This is explicitly not validated by our 3–10
robot simulation and would need real load testing. [FUTURE HARDWARE DEPLOYMENT]

**26. How do you prevent collisions?**
SHORT: The simulator detects them geometrically and reports them; avoiding them is the
conflict-resolution module's job, backed by hard safety hardware in the real system.
[IMPLEMENTED SIMULATION] (detection) + teammates' module (avoidance strategy) + [FUTURE
HARDWARE DEPLOYMENT] (hardware backstop)
TECHNICAL: Our engine checks pairwise robot-robot and robot-obstacle distances each tick
and emits `CollisionEvent`s, putting robots into `WAITING`/`AVOIDING` states as a
placeholder. The actual avoidance *strategy* (who yields, how routes are replanned) is
deliberately left to the conflict-resolution teammate. On hardware, this sits below
deterministic collision-avoidance rules and a hardware e-stop, per the safety hierarchy in
`HARDWARE_ARCHITECTURE.md` §7.

**27. How do you handle deadlocks?**
SHORT: Not solved by the simulator itself — it's a conflict-resolution/path-planning
responsibility; the simulator will faithfully show a deadlock if the coordination logic
allows one. [teammates' module]
TECHNICAL: If two robots both wait for each other indefinitely, the simulator won't break
the tie — that's exactly the kind of scenario conflict resolution is meant to solve
(e.g. priority rules, timeouts, or one robot being told to back off/reroute). Our
Scenario 3 (narrow-aisle face-off) is designed to surface this problem visibly for judges.
[IMPLEMENTED SIMULATION] for exposing it; [FUTURE] / teammates' module for solving it.

**28. How do you handle blocked aisles?**
SHORT: The simulator marks the aisle blocked, updates the world state, and notifies
listeners — an external planner then has to reroute around it. [IMPLEMENTED SIMULATION]
TECHNICAL: `block_aisle()`/`blockAisle()` adds a rectangular blocked zone; any waypoint
that falls inside it puts the robot into `BLOCKED` state; a `AISLE_BLOCKED` event fires so
a path planner can compute and send a new route via `REROUTE`. Scenario 4 demonstrates
this. [IMPLEMENTED SIMULATION]

**29. How does battery management work?**
SHORT: Battery drains while moving and slowly while idle, and recharges at a fixed rate
at a charging station. [IMPLEMENTED SIMULATION] (simplified model)
TECHNICAL: `engine.py` decrements battery each tick based on motion state and restores it
at a fixed rate while `CHARGING`; a robot below 2% automatically issues itself a
`GO_TO_CHARGER` command. This is intentionally simple — a real BMS would account for
load, temperature, and battery chemistry/age. [IMPLEMENTED SIMULATION] for the simplified
model; [FUTURE HARDWARE DEPLOYMENT] for a real BMS.

**30. How would robots recharge?**
SHORT: They autonomously route to the nearest charging station when battery is low.
[IMPLEMENTED SIMULATION] (simulated) / [FUTURE HARDWARE DEPLOYMENT] (physical docking)
TECHNICAL: `GO_TO_CHARGER` computes the nearest charging station and routes there;
arrival transitions the robot into `CHARGING`. On real hardware this would also need a
physical docking/alignment mechanism and contact or inductive charging — not modelled
here. [IMPLEMENTED SIMULATION] for the routing behaviour; [FUTURE HARDWARE DEPLOYMENT]
for physical docking.

**31. What happens during network congestion?**
SHORT: Not modelled in the simulator today (the mock comm layer has zero latency); on
real hardware, expect delayed/stale state and a need to degrade gracefully. [FUTURE
HARDWARE DEPLOYMENT]
TECHNICAL: `MockCommBus` assumes instant, lossless delivery. A real deployment would need
the `communication_status` field to reflect delay/staleness so consuming modules can
treat old data as suspect rather than authoritative — the schema supports this; the mock
doesn't yet exercise it. [FUTURE HARDWARE DEPLOYMENT]

**32. What happens if two robots want the same intersection?**
SHORT: The simulator will show both approaching and stopping short of collision; deciding
who goes first is conflict resolution's job. [IMPLEMENTED SIMULATION] (detection/display)
+ teammates' module (resolution)
TECHNICAL: This is exactly Scenario 2. The simulator detects the near-collision and puts
both robots in `WAITING`/`AVOIDING`, but has no notion of intersection priority — that
logic (e.g. first-come-first-served, priority by task urgency, or a reservation-based
scheme) belongs to the conflict-resolution module.

**33. Where does AI run?**
SHORT: On each robot's edge computer, not in the cloud and not inside the safety loop.
[FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Edge-AI (the teammate's model — e.g. traffic prediction, smarter task
sequencing) would run on the Jetson-class edge computer alongside the MeshFleet Node,
consuming `EnvironmentState` and producing suggestions (routes, task assignments) — never
directly issuing a `STOP` override or bypassing hard safety.

**34. Why shouldn't AI control safety?**
SHORT: AI is probabilistic and can be wrong or unpredictable; safety needs deterministic,
verifiable behaviour every time. [design principle]
TECHNICAL: The safety hierarchy in `HARDWARE_ARCHITECTURE.md` §7 puts hard safety and
deterministic collision avoidance strictly below any AI layer — AI can optimize *within*
the space that safety allows, but must never be the thing preventing a collision, because
its failure modes aren't guaranteed or easily certifiable the way a hardware e-stop or a
simple distance-threshold rule is.

**35. What is the latency requirement?**
SHORT: Safety-relevant reactions need to happen in milliseconds, on-device — not seconds,
and not round-tripped through a network. [FUTURE HARDWARE DEPLOYMENT — target, not
measured]
TECHNICAL: We haven't measured real hardware latency (none exists yet); the target for a
real deployment would be for obstacle-triggered stopping to happen within the motor
controller's control loop period (typically low tens of milliseconds), independent of
mesh network round-trip time. This is a design target, not a measured result.

**36. What happens if an edge device overheats/fails?**
SHORT: Same as a crash or disconnect — fail safe, get timed out by peers, get its task
reassigned. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: A hardware watchdog or thermal cutoff would force the robot to a safe stop
state; from the fleet's perspective this looks identical to Q15/Q16 — a missing
heartbeat that triggers peer timeout and task reassignment.

**37. What would the first physical prototype look like?**
SHORT: One small wheeled robot with a Raspberry Pi, basic motors/encoders, ultrasonic
sensors, and AprilTag-based localization. [FUTURE HARDWARE DEPLOYMENT]
TECHNICAL: Matches Phase 3 of `DEPLOYMENT_ROADMAP.md` — the low-cost tier of the cost
table, aimed at proving the simulated interfaces and basic behaviours (route following,
obstacle stop, low-battery charging) transfer to one real robot before adding fleet
complexity.

**38. How much would a physical prototype cost?**
SHORT: Roughly ₹14,000–27,000 per robot at the low-cost tier; more with LiDAR/Jetson.
[FUTURE HARDWARE DEPLOYMENT — estimate]
TECHNICAL: Full breakdown by component in `DEPLOYMENT_ROADMAP.md`'s cost table; these are
rough India-market estimates only and would need real vendor quotes before any purchase.

**39. What changes between simulation and deployment?**
SHORT: Perception, localization, networking, and motor control all go from idealized to
real and noisy; the data interfaces stay the same. [see `SIMULATION_TO_HARDWARE.md`]
TECHNICAL: Ground-truth obstacle positions become noisy sensor detections; perfect
odometry becomes drift-prone and needs correction; zero-latency mock comms become a real,
lossy Wi-Fi mesh; and the acceleration-limited velocity model becomes actual closed-loop
motor control. The full honest limitations list is in `SIMULATION_TO_HARDWARE.md`.

**40. What are the limitations of your current prototype?**
SHORT: It's a simulation only — no real sensors, no real network, no real motors, and
ground-truth data everywhere a real robot would have to estimate. [IMPLEMENTED
SIMULATION — stated limitation]
TECHNICAL: See the five limitations listed in `SIMULATION_TO_HARDWARE.md`: idealized
perception, perfect odometry, zero-latency/zero-loss networking, a software-only STOP
command (no hardware e-stop yet), and a simplified linear battery model. These are
explicit, known gaps between what's demoed and what real hardware would need — not
things we're claiming to have solved.

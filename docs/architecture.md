# MeshFleet architecture

Each deployed AMR runs `RobotNode`: UDP peer telemetry feeds a local reservation
table, priority/yield arbitration, and intersection token claims. Tasks use a
Contract-Net-style announcement/bid/award exchange; stale peers have their
reservations released.

For reproducible evaluation, `FleetSimulator` is an in-process digital twin. It
implements the proposed allocation (battery/workload-aware cost plus local,
explainable congestion estimate) and a nearest-robot baseline. It supports aisle
closures and robot-failure events, requeues abandoned work, records metrics, and
does not require network broadcast.

The UDP node is the deployment path; the deterministic simulator is the test and
benchmark path. Both share the grid, task, planning, reservation, and cost-model
modules.

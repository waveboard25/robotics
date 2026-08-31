"""Per-robot edge node — independent OS process."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.discovery import PeerTable
from communication.protocol import (
    Message,
    MessageType,
    aisle_blocked_payload,
    bid_payload,
    task_announce_payload,
    task_award_payload,
    telemetry_payload,
    token_payload,
)
from communication.transport_udp import UDPTransport
from conflict_resolution.deadlock_detector import detect_deadlock_cycle, lowest_id_in_cycle
from conflict_resolution.intersection_manager import IntersectionManager, TokenClaim
from conflict_resolution.priority import compute_priority, should_yield
from meshfleet.constants import (
    BROADCAST_PORT,
    HEARTBEAT_HZ,
    RESERVATION_HORIZON,
    TICK_DT,
)
from planning.global_planner import next_step_on_path, space_time_astar
from planning.local_avoidance import apply_orca_to_grid_move
from planning.reservation_table import ReservationTable
from robots.state import RobotState, TaskSpec
from simulation.engine.kinematics import hold_position, step_toward
from simulation.warehouse.grid import WarehouseGrid, load_warehouse
from task_allocation.auction import AuctionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(robot_id)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("robot")


class RobotNode:
    def __init__(
        self,
        robot_id: str,
        grid: WarehouseGrid,
        spawn: tuple[int, int],
        port: int = BROADCAST_PORT,
        headless: bool = False,
        use_auction: bool = True,
    ):
        self.robot_id = robot_id
        self.grid = grid
        self.headless = headless
        self.use_auction = use_auction

        self.state = RobotState(
            robot_id=robot_id,
            position=spawn,
            battery=100.0,
        )
        self.transport = UDPTransport(port=port, bind_port=port)
        self.peers = PeerTable()
        self.reservations = ReservationTable(horizon=RESERVATION_HORIZON)
        self.intersections = IntersectionManager()
        self.auctions = AuctionManager()
        self.pending_tasks: list[TaskSpec] = []
        self.active_task: Optional[TaskSpec] = None
        self.path: list[tuple[int, int]] = []
        self.phase: str = "to_pickup"  # to_pickup | to_dropoff
        self.blocked_aisles: set[str] = set()
        self.waiting_on: dict[str, str] = {}
        self.seq = 0
        self.running = True
        self.collision_count = 0
        self.idle_conflict_ticks = 0
        self.task_complete_at: Optional[int] = None

        log_adapter = logging.LoggerAdapter(logger, {"robot_id": robot_id})
        self.log = log_adapter

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def broadcast(self, msg: Message) -> None:
        self.transport.send(msg, redundant=2)

    def handle_messages(self) -> None:
        for msg in self.transport.recv_all():
            if msg.robot_id == self.robot_id:
                continue

            if msg.msg_type == MessageType.TELEMETRY:
                self.peers.update_from_message(msg, self.robot_id)
                p = msg.payload
                waypoints = [tuple(w) for w in p.get("next_waypoints", [])]
                self.reservations.merge_from_peer_waypoints(
                    msg.robot_id,
                    waypoints,
                    msg.tick,
                    p.get("reservation_horizon_id", 0),
                )

            elif msg.msg_type == MessageType.TASK_ANNOUNCE:
                p = msg.payload
                task = TaskSpec(
                    task_id=p["task_id"],
                    pickup=tuple(p["pickup"]),
                    dropoff=tuple(p["dropoff"]),
                    urgency=p.get("urgency", 1.0),
                    deadline_tick=p.get("deadline_tick"),
                )
                if not self.auctions.is_task_taken(task.task_id):
                    self.pending_tasks.append(task)
                    self.auctions.announce_task(task, self.state.tick)

            elif msg.msg_type == MessageType.BID:
                p = msg.payload
                self.auctions.record_peer_bid(p["task_id"], msg.robot_id, p["cost"])

            elif msg.msg_type == MessageType.TASK_AWARD:
                p = msg.payload
                self.auctions.awarded_tasks[p["task_id"]] = p["winner_id"]
                auction = self.auctions.open_auctions.get(p["task_id"])
                if auction:
                    auction.closed = True
                    auction.winner = p["winner_id"]

            elif msg.msg_type == MessageType.AISLE_BLOCKED:
                p = msg.payload
                self.blocked_aisles.add(p["aisle_id"])
                cells = [tuple(c) for c in p["cells"]]
                self.grid.block_cells(cells)
                if self.active_task and self._path_crosses_blocked():
                    self._replan()

            elif msg.msg_type == MessageType.TOKEN_CLAIM:
                p = msg.payload
                cell = tuple(p["cell"])
                self.intersections.update_from_claim_msg(
                    msg.robot_id, cell, msg.timestamp, msg.tick
                )

            elif msg.msg_type == MessageType.TOKEN_RELEASE:
                p = msg.payload
                cell = tuple(p["cell"])
                self.intersections.update_from_release(msg.robot_id, cell)

    def _path_crosses_blocked(self) -> bool:
        blocked = self.grid.dynamic_blocked
        return any(c in blocked for c in self.path)

    def _replan(self) -> None:
        goal = self._current_goal()
        if goal is None:
            return
        self.path = space_time_astar(
            self.grid,
            self.state.position,
            goal,
            self.state.tick,
            self.reservations,
            self.robot_id,
        )
        if self.path:
            self.reservations.reserve_path(self.robot_id, self.path, self.state.tick)
            self.state.reservation_horizon_id = self.reservations.horizon_id
            self.state.next_waypoints = self.path[1 : RESERVATION_HORIZON]
            self.log.info("Replanned to %s via %d cells", goal, len(self.path))

    def _current_goal(self) -> Optional[tuple[int, int]]:
        if not self.active_task:
            return self.state.goal
        if self.phase == "to_pickup":
            return self.active_task.pickup
        return self.active_task.dropoff

    def _process_auctions(self) -> None:
        for task in list(self.pending_tasks):
            if self.auctions.is_task_taken(task.task_id):
                continue
            auction = self.auctions.open_auctions.get(task.task_id)
            if not auction:
                continue

            if self.state.current_task or self.state.battery < 20:
                continue

            congestion = 0.0
            try:
                from edge_ai.congestion_predictor import predict_congestion

                congestion = predict_congestion(self.grid, self.state.position, task.pickup)
            except Exception:
                congestion = len(self.peers.get_active_peers()) * 0.5

            cost = self.auctions.compute_local_bid(
                self.state,
                auction,
                self.grid,
                congestion_penalty=congestion,
                blocked_aisles=self.blocked_aisles,
            )
            if cost < float("inf"):
                self.auctions.submit_bid(task.task_id, self.robot_id, cost)
                self.broadcast(
                    Message(
                        msg_type=MessageType.BID,
                        robot_id=self.robot_id,
                        seq=self._next_seq(),
                        tick=self.state.tick,
                        payload=bid_payload(task.task_id, cost),
                    )
                )

            # Wait one tick for bids then determine winner locally
            if self.state.tick - auction.announce_tick >= 2:
                winner = self.auctions.determine_winner(task.task_id)
                if winner:
                    win_cost = auction.bids.get(winner, 0)
                    self.broadcast(
                        Message(
                            msg_type=MessageType.TASK_AWARD,
                            robot_id="WMS",
                            seq=self._next_seq(),
                            tick=self.state.tick,
                            payload=task_award_payload(task.task_id, winner, win_cost),
                        )
                    )
                    if winner == self.robot_id:
                        self._assign_task(task)

    def _assign_task(self, task: TaskSpec) -> None:
        self.active_task = task
        self.state.current_task = task.task_id
        self.state.task_urgency = task.urgency
        self.phase = "to_pickup"
        self.state.goal = task.pickup
        self._replan()
        self.log.info("Assigned task %s", task.task_id)

    def _check_collision_at(self, cell: tuple[int, int]) -> Optional[str]:
        for rid, peer in self.peers.get_active_peers().items():
            if peer.position == cell:
                return rid
        return None

    def _resolve_move(self, next_cell: tuple[int, int]) -> bool:
        """Return True if robot may move to next_cell."""
        tick = self.state.tick + 1
        blocker = self.reservations.conflicting_robot(
            next_cell, tick, exclude_robot=self.robot_id
        )

        # Physical collision check
        occupant = self._check_collision_at(next_cell)
        if occupant:
            peer = self.peers.get_peer(occupant)
            if peer and should_yield(self.state, peer, self.grid):
                self.waiting_on[self.robot_id] = occupant
                return False
            elif peer:
                return True  # other yields

        if blocker and blocker != self.robot_id:
            peer = self.peers.get_peer(blocker)
            if peer and should_yield(self.state, peer, self.grid):
                self.waiting_on[self.robot_id] = blocker
                return False

        if self.grid.is_choke_point(next_cell):
            claims = [
                TokenClaim(c.robot_id, c.cell, c.timestamp, c.tick)
                for c in self.intersections.claims.values()
            ]
            claims.append(
                TokenClaim(
                    self.robot_id, next_cell, time.time(), self.state.tick
                )
            )
            self.broadcast(
                Message(
                    msg_type=MessageType.TOKEN_CLAIM,
                    robot_id=self.robot_id,
                    seq=self._next_seq(),
                    tick=self.state.tick,
                    payload=token_payload(next_cell),
                )
            )
            if not self.intersections.request_token(
                self.robot_id, next_cell, self.state.tick, claims
            ):
                return False

        cycle = detect_deadlock_cycle(self.robot_id, self.waiting_on)
        if cycle and lowest_id_in_cycle(cycle) == self.robot_id:
            self.log.info("Deadlock break — backing off")
            hold_position(self.state)
            self.path = []
            self._replan()
            return False

        return True

    def tick_once(self) -> None:
        self.state.tick += 1
        self.handle_messages()
        evicted = self.peers.evict_stale()
        for rid in evicted:
            self.reservations.release_robot(rid)
            self.log.info("Peer %s stale — released reservations", rid)

        self.reservations.prune_old(self.state.tick)
        self.state.priority_score = compute_priority(
            self.state, self.grid, self._current_goal()
        )

        if self.use_auction:
            self._process_auctions()

        goal = self._current_goal()
        if goal and (not self.path or self.state.position == goal):
            if self.active_task and self.phase == "to_pickup" and self.state.position == self.active_task.pickup:
                self.phase = "to_dropoff"
                self.state.goal = self.active_task.dropoff
                self._replan()
            elif self.active_task and self.phase == "to_dropoff" and self.state.position == self.active_task.dropoff:
                self.log.info("Task %s complete", self.active_task.task_id)
                self.task_complete_at = self.state.tick
                self.active_task = None
                self.state.current_task = None
                self.state.status = "IDLE"
                self.path = []
                self.phase = "to_pickup"
            elif not self.path and goal:
                self._replan()

        if not self.path:
            self.state.status = "IDLE"
            self._publish_telemetry()
            return

        next_cell = next_step_on_path(self.path, self.state.position)
        if next_cell is None:
            self._publish_telemetry()
            return

        # ORCA safety layer
        peer_velocities = []
        for rid, peer in self.peers.get_active_peers().items():
            pos_f = (float(peer.position[0]), float(peer.position[1]))
            peer_velocities.append((pos_f, peer.velocity))

        orca_vel = apply_orca_to_grid_move(
            self.state.position, self.state.velocity, next_cell, peer_velocities
        )

        if not self._resolve_move(next_cell):
            hold_position(self.state)
            self.idle_conflict_ticks += 1
        else:
            self.state.wait_ticks = 0
            self.waiting_on.pop(self.robot_id, None)
            old_pos = self.state.position
            step_toward(self.state, next_cell, orca_vel)

            # Collision detection
            for rid, peer in self.peers.get_active_peers().items():
                if peer.position == self.state.position:
                    self.collision_count += 1
                    self.log.warning("Collision with %s!", rid)
                    self.state.position = old_pos
                    hold_position(self.state)

            if self.state.position != old_pos:
                prev_cell = old_pos
                if self.intersections.held_tokens.get(self.robot_id) == prev_cell:
                    self.intersections.release_token(self.robot_id)
                    self.broadcast(
                        Message(
                            msg_type=MessageType.TOKEN_RELEASE,
                            robot_id=self.robot_id,
                            seq=self._next_seq(),
                            tick=self.state.tick,
                            payload=token_payload(prev_cell),
                        )
                    )

        self.state.next_waypoints = self.path[1:RESERVATION_HORIZON]
        self._publish_telemetry()

    def _publish_telemetry(self) -> None:
        self.broadcast(
            Message(
                msg_type=MessageType.TELEMETRY,
                robot_id=self.robot_id,
                seq=self._next_seq(),
                tick=self.state.tick,
                payload=telemetry_payload(
                    position=self.state.position,
                    velocity=self.state.velocity,
                    heading=self.state.heading,
                    battery=self.state.battery,
                    status=self.state.status,
                    current_task=self.state.current_task,
                    intent=self.state.intent,
                    next_waypoints=self.state.next_waypoints,
                    priority_score=self.state.priority_score,
                    reservation_horizon_id=self.state.reservation_horizon_id,
                    wait_ticks=self.state.wait_ticks,
                ),
            )
        )

    def run(self, max_ticks: int = 500) -> None:
        self.log.info("Starting at %s", self.state.position)
        while self.running and self.state.tick < max_ticks:
            t0 = time.perf_counter()
            self.tick_once()
            elapsed = time.perf_counter() - t0
            sleep_time = max(0, TICK_DT - elapsed)
            time.sleep(sleep_time)
        self.log.info(
            "Stopped tick=%d collisions=%d idle_conflict=%d",
            self.state.tick,
            self.collision_count,
            self.idle_conflict_ticks,
        )
        self.transport.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="MeshFleet robot node")
    parser.add_argument("--id", required=True, help="Robot ID e.g. R1")
    parser.add_argument("--spawn-x", type=int, default=1)
    parser.add_argument("--spawn-y", type=int, default=3)
    parser.add_argument("--map", default="configs/warehouse_layouts/default.yaml")
    parser.add_argument("--port", type=int, default=BROADCAST_PORT)
    parser.add_argument("--max-ticks", type=int, default=500)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-auction", action="store_true")
    args = parser.parse_args()

    map_path = ROOT / args.map
    grid = load_warehouse(map_path)
    node = RobotNode(
        robot_id=args.id,
        grid=grid,
        spawn=(args.spawn_x, args.spawn_y),
        port=args.port,
        headless=args.headless,
        use_auction=not args.no_auction,
    )
    node.run(max_ticks=args.max_ticks)


if __name__ == "__main__":
    main()

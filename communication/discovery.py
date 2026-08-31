"""Peer discovery and staleness tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from communication.protocol import Message, MessageType
from meshfleet.constants import STALE_THRESHOLD
from robots.state import RobotState


@dataclass
class PeerEntry:
    state: RobotState
    last_seen: float
    last_seq: int = -1


@dataclass
class PeerTable:
    peers: dict[str, PeerEntry] = field(default_factory=dict)
    stale_threshold: float = STALE_THRESHOLD

    def update_from_message(self, msg: Message, self_id: str) -> None:
        if msg.robot_id == self_id:
            return
        if msg.msg_type != MessageType.TELEMETRY:
            return

        p = msg.payload
        pos = tuple(p.get("position", [0, 0]))
        vel = tuple(p.get("velocity", [0.0, 0.0]))
        waypoints = [tuple(w) for w in p.get("next_waypoints", [])]

        state = RobotState(
            robot_id=msg.robot_id,
            seq=msg.seq,
            tick=msg.tick,
            position=(int(pos[0]), int(pos[1])),
            velocity=(float(vel[0]), float(vel[1])),
            heading=p.get("heading", 0.0),
            battery=p.get("battery", 100.0),
            status=p.get("status", "IDLE"),
            current_task=p.get("current_task"),
            intent=p.get("intent", "STOP"),
            next_waypoints=waypoints,
            priority_score=p.get("priority_score", 0.0),
            reservation_horizon_id=p.get("reservation_horizon_id", 0),
            wait_ticks=p.get("wait_ticks", 0),
        )

        entry = self.peers.get(msg.robot_id)
        if entry and msg.seq <= entry.last_seq:
            return

        self.peers[msg.robot_id] = PeerEntry(
            state=state, last_seen=msg.timestamp, last_seq=msg.seq
        )

    def evict_stale(self, now: Optional[float] = None) -> list[str]:
        now = now or time.time()
        evicted = []
        for rid, entry in list(self.peers.items()):
            if now - entry.last_seen > self.stale_threshold:
                evicted.append(rid)
                del self.peers[rid]
        return evicted

    def get_active_peers(self) -> dict[str, RobotState]:
        return {rid: e.state for rid, e in self.peers.items()}

    def get_peer(self, robot_id: str) -> Optional[RobotState]:
        entry = self.peers.get(robot_id)
        return entry.state if entry else None

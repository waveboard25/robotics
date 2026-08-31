"""UDP message protocol — JSON serialization."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MessageType(str, Enum):
    TELEMETRY = "TELEMETRY"
    TASK_ANNOUNCE = "TASK_ANNOUNCE"
    BID = "BID"
    TASK_AWARD = "TASK_AWARD"
    AISLE_BLOCKED = "AISLE_BLOCKED"
    TOKEN_CLAIM = "TOKEN_CLAIM"
    TOKEN_RELEASE = "TOKEN_RELEASE"
    TASK_COMPLETE = "TASK_COMPLETE"


@dataclass
class Message:
    msg_type: MessageType
    robot_id: str
    seq: int = 0
    timestamp: float = field(default_factory=time.time)
    tick: int = 0
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "msg_type": self.msg_type.value,
                "robot_id": self.robot_id,
                "seq": self.seq,
                "timestamp": self.timestamp,
                "tick": self.tick,
                "payload": self.payload,
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        data = json.loads(raw)
        return cls(
            msg_type=MessageType(data["msg_type"]),
            robot_id=data["robot_id"],
            seq=data.get("seq", 0),
            timestamp=data.get("timestamp", time.time()),
            tick=data.get("tick", 0),
            payload=data.get("payload", {}),
        )


def telemetry_payload(
    position: tuple[int, int],
    velocity: tuple[float, float],
    heading: float,
    battery: float,
    status: str,
    current_task: Optional[str],
    intent: str,
    next_waypoints: list[tuple[int, int]],
    priority_score: float,
    reservation_horizon_id: int,
    wait_ticks: int = 0,
) -> dict[str, Any]:
    return {
        "position": list(position),
        "velocity": list(velocity),
        "heading": heading,
        "battery": battery,
        "status": status,
        "current_task": current_task,
        "intent": intent,
        "next_waypoints": [list(w) for w in next_waypoints],
        "priority_score": priority_score,
        "reservation_horizon_id": reservation_horizon_id,
        "wait_ticks": wait_ticks,
    }


def task_announce_payload(
    task_id: str,
    pickup: tuple[int, int],
    dropoff: tuple[int, int],
    urgency: float = 1.0,
    deadline_tick: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "pickup": list(pickup),
        "dropoff": list(dropoff),
        "urgency": urgency,
        "deadline_tick": deadline_tick,
    }


def bid_payload(task_id: str, cost: float) -> dict[str, Any]:
    return {"task_id": task_id, "cost": cost}


def task_award_payload(task_id: str, winner_id: str, cost: float) -> dict[str, Any]:
    return {"task_id": task_id, "winner_id": winner_id, "cost": cost}


def aisle_blocked_payload(aisle_id: str, cells: list[tuple[int, int]]) -> dict[str, Any]:
    return {"aisle_id": aisle_id, "cells": [list(c) for c in cells]}


def token_payload(cell: tuple[int, int]) -> dict[str, Any]:
    return {"cell": list(cell)}

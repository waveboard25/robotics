"""Task generator — WMS stand-in broadcasting tasks."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from communication.protocol import Message, MessageType, aisle_blocked_payload, task_announce_payload
from communication.transport_udp import UDPTransport
from meshfleet.constants import BROADCAST_PORT, TICK_DT
from robots.state import TaskSpec


class TaskGenerator:
    def __init__(self, port: int = BROADCAST_PORT):
        self.transport = UDPTransport(port=port)
        self.seq = 0

    def announce(self, task: TaskSpec, tick: int = 0) -> None:
        self.seq += 1
        msg = Message(
            msg_type=MessageType.TASK_ANNOUNCE,
            robot_id="WMS",
            seq=self.seq,
            tick=tick,
            payload=task_announce_payload(
                task.task_id,
                task.pickup,
                task.dropoff,
                task.urgency,
                task.deadline_tick,
            ),
        )
        self.transport.send(msg, redundant=3)
        print(f"[WMS] Announced task {task.task_id} pickup={task.pickup} dropoff={task.dropoff}")

    def block_aisle(self, aisle_id: str, cells: list[tuple[int, int]], tick: int = 0) -> None:
        self.seq += 1
        msg = Message(
            msg_type=MessageType.AISLE_BLOCKED,
            robot_id="WMS",
            seq=self.seq,
            tick=tick,
            payload=aisle_blocked_payload(aisle_id, cells),
        )
        self.transport.send(msg, redundant=3)
        print(f"[WMS] Blocked aisle {aisle_id}")

    def close(self) -> None:
        self.transport.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds before first task")
    parser.add_argument("--port", type=int, default=BROADCAST_PORT)
    args = parser.parse_args()

    gen = TaskGenerator(port=args.port)
    time.sleep(args.delay)

    tasks = [
        TaskSpec("PICKUP_A", (1, 3), (18, 11), urgency=1.0),
        TaskSpec("PICKUP_B", (1, 7), (18, 5), urgency=1.5),
        TaskSpec("PICKUP_C", (1, 11), (18, 3), urgency=1.2),
    ]
    for i, task in enumerate(tasks):
        gen.announce(task, tick=i * 10)
        time.sleep(2.0)

    time.sleep(5.0)
    gen.block_aisle("aisle_4", [(8, 5), (9, 5), (10, 5), (11, 5)], tick=80)
    gen.close()


if __name__ == "__main__":
    main()

"""
SIMULATION COMMUNICATION MOCK
-----------------------------
This is NOT the real MeshFleet P2P/mesh network. It is a same-process,
zero-latency stand-in so the simulator and other Python modules can be
developed and tested before the real comms module exists.

The real P2P/mesh communication module (a teammate's responsibility) should
implement the same four operations against actual sockets / DDS / MQTT /
whatever transport they choose:

    send_state(robot_state)        -> broadcast this robot's state to peers
    receive_state()                -> get peers' most recent known states
    send_command(command)          -> deliver a RobotCommand to a robot
    receive_environment_update()   -> get the latest EnvironmentState

As long as a real implementation exposes these four calls with the same
signatures, it is a drop-in replacement for MockCommBus below — nothing
else in the codebase needs to change.
"""

from __future__ import annotations
from typing import Callable
from .schemas import RobotState, RobotCommand, EnvironmentState
from .engine import SimulationEngine


class MockCommBus:
    def __init__(self, engine: SimulationEngine):
        self._engine = engine
        self._inboxes: dict[str, list[RobotCommand]] = {}

    def send_state(self, robot_state: RobotState) -> None:
        """In the mock, state is always already visible via the engine —
        this exists purely so calling code doesn't need an if/else between
        mock and real transport."""
        return None

    def receive_state(self) -> list[RobotState]:
        env: EnvironmentState = self._engine.get_environment_state()
        return env.robot_states

    def send_command(self, command: RobotCommand) -> dict:
        return self._engine.send_command(command)

    def receive_environment_update(self) -> EnvironmentState:
        return self._engine.get_environment_state()

    def subscribe(self, fn: Callable[[str, dict], None]) -> None:
        self._engine.on_event(fn)

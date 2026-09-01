"""Scenario metrics written as JSON/CSV-friendly dictionaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class FleetMetrics:
    algorithm: str
    ticks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    collisions: int = 0
    replans: int = 0
    reassignments: int = 0
    deadlock_breaks: int = 0
    total_wait_ticks: int = 0
    mean_completion_tick: float = 0.0

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)

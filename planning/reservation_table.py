"""Windowed space-time reservation table."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Reservation:
    robot_id: str
    cell: tuple[int, int]
    start_tick: int
    end_tick: int


@dataclass
class ReservationTable:
    horizon: int = 20
    reservations: list[Reservation] = field(default_factory=list)
    horizon_id: int = 0

    def clear_robot(self, robot_id: str) -> None:
        self.reservations = [r for r in self.reservations if r.robot_id != robot_id]

    def reserve_path(
        self,
        robot_id: str,
        path: list[tuple[int, int]],
        start_tick: int,
    ) -> None:
        self.clear_robot(robot_id)
        for i, cell in enumerate(path):
            tick = start_tick + i
            if i == 0:
                continue  # current cell doesn't block others at same tick
            self.reservations.append(
                Reservation(robot_id=robot_id, cell=cell, start_tick=tick, end_tick=tick)
            )
        self.horizon_id += 1

    def is_reserved(self, cell: tuple[int, int], tick: int, exclude_robot: Optional[str] = None) -> bool:
        for r in self.reservations:
            if exclude_robot and r.robot_id == exclude_robot:
                continue
            if r.cell == cell and r.start_tick <= tick <= r.end_tick:
                return True
        return False

    def conflicting_robot(
        self, cell: tuple[int, int], tick: int, exclude_robot: Optional[str] = None
    ) -> Optional[str]:
        for r in self.reservations:
            if exclude_robot and r.robot_id == exclude_robot:
                continue
            if r.cell == cell and r.start_tick <= tick <= r.end_tick:
                return r.robot_id
        return None

    def merge_from_peer_waypoints(
        self,
        robot_id: str,
        waypoints: list[tuple[int, int]],
        start_tick: int,
        horizon_id: int,
    ) -> None:
        if not waypoints:
            return
        self.clear_robot(robot_id)
        for i, cell in enumerate(waypoints):
            tick = start_tick + i + 1
            if tick - start_tick > self.horizon:
                break
            self.reservations.append(
                Reservation(robot_id=robot_id, cell=cell, start_tick=tick, end_tick=tick)
            )

    def prune_old(self, current_tick: int) -> None:
        self.reservations = [r for r in self.reservations if r.end_tick >= current_tick]

    def release_robot(self, robot_id: str) -> None:
        self.clear_robot(robot_id)

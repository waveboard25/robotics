"""Warehouse grid map loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class WarehouseGrid:
    width: int
    height: int
    static_blocked: set[tuple[int, int]] = field(default_factory=set)
    dynamic_blocked: set[tuple[int, int]] = field(default_factory=set)
    choke_points: set[tuple[int, int]] = field(default_factory=set)
    intersections: set[tuple[int, int]] = field(default_factory=set)
    pickups: dict[str, tuple[int, int]] = field(default_factory=dict)
    dropoffs: dict[str, tuple[int, int]] = field(default_factory=dict)
    charging: list[tuple[int, int]] = field(default_factory=list)
    aisle_labels: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and (x, y) not in self.static_blocked and (x, y) not in self.dynamic_blocked

    def block_cells(self, cells: list[tuple[int, int]]) -> None:
        for c in cells:
            self.dynamic_blocked.add(c)

    def unblock_aisle(self, aisle_id: str) -> None:
        cells = self.aisle_labels.get(aisle_id, [])
        for c in cells:
            self.dynamic_blocked.discard(c)

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        result = []
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if self.is_passable(nx, ny):
                result.append((nx, ny))
        return result

    def manhattan(self, a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def is_choke_point(self, cell: tuple[int, int]) -> bool:
        return cell in self.choke_points or cell in self.intersections


def load_warehouse(path: Path | str) -> WarehouseGrid:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    grid = WarehouseGrid(width=data["width"], height=data["height"])

    for cell in data.get("static_blocked", []):
        grid.static_blocked.add(tuple(cell))

    for cell in data.get("choke_points", []):
        grid.choke_points.add(tuple(cell))

    for cell in data.get("intersections", []):
        grid.intersections.add(tuple(cell))

    for name, cell in data.get("pickups", {}).items():
        grid.pickups[name] = tuple(cell)

    for name, cell in data.get("dropoffs", {}).items():
        grid.dropoffs[name] = tuple(cell)

    grid.charging = [tuple(c) for c in data.get("charging", [])]

    for aisle_id, cells in data.get("aisles", {}).items():
        grid.aisle_labels[aisle_id] = [tuple(c) for c in cells]

    return grid

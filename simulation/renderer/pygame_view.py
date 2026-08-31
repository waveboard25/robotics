"""Pygame warehouse visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore

from simulation.warehouse.grid import WarehouseGrid


CELL_SIZE = 32
COLORS = {
    "background": (30, 30, 40),
    "free": (50, 50, 60),
    "blocked": (80, 80, 90),
    "dynamic": (120, 60, 60),
    "intersection": (70, 70, 100),
    "pickup": (60, 120, 60),
    "robot": (100, 180, 255),
    "yielding": (255, 180, 80),
    "path": (100, 200, 100),
    "text": (220, 220, 220),
}


class PygameRenderer:
    def __init__(self, grid: WarehouseGrid, title: str = "MeshFleet"):
        if pygame is None:
            raise ImportError("pygame is required for visualization")
        self.grid = grid
        self.width = grid.width * CELL_SIZE
        self.height = grid.height * CELL_SIZE + 40
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(title)
        self.font = pygame.font.SysFont("consolas", 14)
        self.clock = pygame.time.Clock()

    def draw(
        self,
        robots: dict[str, dict],
        fps: int = 10,
    ) -> bool:
        """Draw frame. Returns False if user quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

        self.screen.fill(COLORS["background"])

        for y in range(self.grid.height):
            for x in range(self.grid.width):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if (x, y) in self.grid.dynamic_blocked:
                    color = COLORS["dynamic"]
                elif (x, y) in self.grid.static_blocked:
                    color = COLORS["blocked"]
                elif (x, y) in self.grid.intersections:
                    color = COLORS["intersection"]
                elif (x, y) in self.grid.pickups.values():
                    color = COLORS["pickup"]
                else:
                    color = COLORS["free"]
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (40, 40, 50), rect, 1)

        for rid, info in robots.items():
            pos = info.get("position", (0, 0))
            px = pos[0] * CELL_SIZE + CELL_SIZE // 2
            py = pos[1] * CELL_SIZE + CELL_SIZE // 2
            status = info.get("status", "IDLE")
            color = COLORS["yielding"] if status == "YIELDING" else COLORS["robot"]
            pygame.draw.circle(self.screen, color, (px, py), CELL_SIZE // 3)
            label = self.font.render(rid, True, COLORS["text"])
            self.screen.blit(label, (px - 10, py - 20))

            for wp in info.get("next_waypoints", [])[:5]:
                wx = wp[0] * CELL_SIZE + CELL_SIZE // 2
                wy = wp[1] * CELL_SIZE + CELL_SIZE // 2
                pygame.draw.circle(self.screen, COLORS["path"], (wx, wy), 3)

        status_line = self.font.render(
            f"Robots: {len(robots)} | ESC to close", True, COLORS["text"]
        )
        self.screen.blit(status_line, (10, self.height - 30))

        pygame.display.flip()
        self.clock.tick(fps)
        return True

    def close(self) -> None:
        if pygame:
            pygame.quit()

"""Distributed token/mutex for choke points and intersections."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenClaim:
    robot_id: str
    cell: tuple[int, int]
    timestamp: float
    tick: int


@dataclass
class IntersectionManager:
    claims: dict[tuple[int, int], TokenClaim] = field(default_factory=dict)
    held_tokens: dict[str, tuple[int, int]] = field(default_factory=dict)

    def request_token(
        self,
        robot_id: str,
        cell: tuple[int, int],
        tick: int,
        all_claims: list[TokenClaim],
    ) -> bool:
        """Return True if this robot may enter the choke cell."""
        relevant = [c for c in all_claims if c.cell == cell]
        if not relevant:
            return True

        # Sort by timestamp then robot_id tie-break
        winner = min(relevant, key=lambda c: (c.timestamp, c.robot_id))
        if winner.robot_id == robot_id:
            self.held_tokens[robot_id] = cell
            self.claims[cell] = winner
            return True
        return False

    def release_token(self, robot_id: str) -> None:
        cell = self.held_tokens.pop(robot_id, None)
        if cell and cell in self.claims:
            if self.claims[cell].robot_id == robot_id:
                del self.claims[cell]

    def has_token(self, robot_id: str, cell: tuple[int, int]) -> bool:
        return self.held_tokens.get(robot_id) == cell

    def update_from_claim_msg(
        self, robot_id: str, cell: tuple[int, int], timestamp: float, tick: int
    ) -> None:
        existing = self.claims.get(cell)
        claim = TokenClaim(robot_id=robot_id, cell=cell, timestamp=timestamp, tick=tick)
        if existing is None or (timestamp, robot_id) < (existing.timestamp, existing.robot_id):
            self.claims[cell] = claim

    def update_from_release(self, robot_id: str, cell: tuple[int, int]) -> None:
        existing = self.claims.get(cell)
        if existing and existing.robot_id == robot_id:
            del self.claims[cell]
        if self.held_tokens.get(robot_id) == cell:
            del self.held_tokens[robot_id]

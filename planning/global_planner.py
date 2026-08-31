"""Grid A* and space-time A* path planning."""

from __future__ import annotations

import heapq
from typing import Optional

from planning.reservation_table import ReservationTable
from simulation.warehouse.grid import WarehouseGrid


def grid_astar(
    grid: WarehouseGrid,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    if start == goal:
        return [start]

    open_set: list[tuple[int, int, tuple[int, int]]] = []
    heapq.heappush(open_set, (grid.manhattan(start, goal), 0, start))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], int] = {start: 0}

    while open_set:
        _, g, current = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        if g > g_score.get(current, float("inf")):
            continue

        for neighbor in grid.neighbors(*current):
            tentative = g + 1
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                f = tentative + grid.manhattan(neighbor, goal)
                heapq.heappush(open_set, (f, tentative, neighbor))

    return []


def space_time_astar(
    grid: WarehouseGrid,
    start: tuple[int, int],
    goal: tuple[int, int],
    start_tick: int,
    reservations: ReservationTable,
    robot_id: str,
    max_time: int = 200,
) -> list[tuple[int, int]]:
    """Plan spatial path with time reservations; wait-in-place allowed."""
    if start == goal:
        return [start]

    # State: (x, y, tick)
    start_state = (start[0], start[1], start_tick)
    open_set: list[tuple[int, int, int, int, int]] = []
    heapq.heappush(
        open_set,
        (grid.manhattan(start, goal), 0, start[0], start[1], start_tick),
    )
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    g_score: dict[tuple[int, int, int], int] = {start_state: 0}

    while open_set:
        _, g, x, y, tick = heapq.heappop(open_set)
        state = (x, y, tick)
        if (x, y) == goal:
            path = [(x, y)]
            while state in came_from:
                state = came_from[state]
                path.append((state[0], state[1]))
            path.reverse()
            # Deduplicate consecutive same cells from waiting
            deduped = [path[0]]
            for p in path[1:]:
                if p != deduped[-1]:
                    deduped.append(p)
            return deduped

        if g > g_score.get(state, float("inf")):
            continue
        if tick - start_tick > max_time:
            continue

        # Actions: wait or move to neighbor
        actions: list[tuple[int, int, int]] = [(x, y, tick + 1)]  # wait
        for nx, ny in grid.neighbors(x, y):
            actions.append((nx, ny, tick + 1))

        for nx, ny, nt in actions:
            if reservations.is_reserved((nx, ny), nt, exclude_robot=robot_id):
                continue
            tentative = g + 1
            nstate = (nx, ny, nt)
            if tentative < g_score.get(nstate, float("inf")):
                came_from[nstate] = state
                g_score[nstate] = tentative
                f = tentative + grid.manhattan((nx, ny), goal)
                heapq.heappush(open_set, (f, tentative, nx, ny, nt))

    # Fallback to spatial-only A*
    return grid_astar(grid, start, goal)


def next_step_on_path(
    path: list[tuple[int, int]], current: tuple[int, int]
) -> Optional[tuple[int, int]]:
    if not path:
        return None
    try:
        idx = path.index(current)
        if idx + 1 < len(path):
            return path[idx + 1]
    except ValueError:
        if path:
            return path[0]
    return None

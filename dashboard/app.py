"""FastAPI dashboard bridge for MeshFleet's UDP telemetry."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from communication.discovery import PeerTable
from communication.transport_udp import UDPTransport
from meshfleet.constants import BROADCAST_PORT, PROJECT_ROOT
from simulation.warehouse.grid import load_warehouse

STATIC_DIR = Path(__file__).parent / "static"


class DashboardState:
    def __init__(self, scenario_path: Path, port: int = BROADCAST_PORT) -> None:
        scenario_path = Path(scenario_path)
        with scenario_path.open(encoding="utf-8") as scenario_file:
            self.scenario = yaml.safe_load(scenario_file) or {}

        map_path = Path(self.scenario.get("map", "configs/warehouse_layouts/default.yaml"))
        if not map_path.is_absolute():
            map_path = PROJECT_ROOT / map_path
        self.grid = load_warehouse(map_path)
        self.peers = PeerTable()
        self.transport = UDPTransport(port=port, bind_port=port)
        self.clients: set[WebSocket] = set()

    def snapshot(self) -> dict[str, Any]:
        active = self.peers.get_active_peers()
        tick = max((state.tick for state in active.values()), default=0)
        fired_events = [
            event for event in self.scenario.get("events", []) if event.get("at_tick", 0) <= tick
        ]
        dynamic_blocked = set(self.grid.dynamic_blocked)
        for event in fired_events:
            if event.get("type") == "block_aisle":
                dynamic_blocked.update(tuple(cell) for cell in event.get("cells", []))
        robots = [
            {
                "id": state.robot_id,
                "position": list(state.position),
                "velocity": list(state.velocity),
                "heading": state.heading,
                "battery": round(state.battery, 1),
                "status": state.status,
                "task": state.current_task,
                "intent": state.intent,
                "waypoints": [list(point) for point in state.next_waypoints],
                "wait_ticks": state.wait_ticks,
                "priority": round(state.priority_score, 2),
                "last_seen": self.peers.peers[state.robot_id].last_seen,
            }
            for state in sorted(active.values(), key=lambda item: item.robot_id)
        ]
        assigned = {robot["task"] for robot in robots if robot["task"]}
        tasks = []
        for task in self.scenario.get("tasks", []):
            task_id = task["id"]
            tasks.append(
                {
                    "id": task_id,
                    "pickup": task["pickup"],
                    "dropoff": task["dropoff"],
                    "urgency": task.get("urgency", 1.0),
                    "status": "assigned" if task_id in assigned else "queued",
                    "robot": next((robot["id"] for robot in robots if robot["task"] == task_id), None),
                }
            )

        return {
            "scenario": self.scenario.get("name", "MeshFleet live fleet"),
            "tick": tick,
            "updated_at": time.time(),
            "robots": robots,
            "tasks": tasks,
            "events": fired_events,
            "map": {
                "width": self.grid.width,
                "height": self.grid.height,
                "static_blocked": [list(cell) for cell in sorted(self.grid.static_blocked)],
                "dynamic_blocked": [list(cell) for cell in sorted(dynamic_blocked)],
                "charging": [list(cell) for cell in self.grid.charging],
                "intersections": [list(cell) for cell in sorted(self.grid.intersections)],
                "pickups": {name: list(cell) for name, cell in self.grid.pickups.items()},
                "dropoffs": {name: list(cell) for name, cell in self.grid.dropoffs.items()},
            },
        }

    def receive(self) -> None:
        for message in self.transport.recv_all():
            self.peers.update_from_message(message, "DASHBOARD")
        self.peers.evict_stale()

    def close(self) -> None:
        self.transport.close()


def create_app(state: DashboardState) -> FastAPI:
    app = FastAPI(title="MeshFleet Dashboard")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.on_event("startup")
    async def start_receiver() -> None:
        async def receive_loop() -> None:
            while True:
                state.receive()
                await asyncio.sleep(0.1)

        app.state.receiver = asyncio.create_task(receive_loop())

    @app.on_event("shutdown")
    async def stop_receiver() -> None:
        app.state.receiver.cancel()
        state.close()

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict[str, Any]:
        return state.snapshot()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        state.clients.add(websocket)
        try:
            while True:
                await websocket.send_text(json.dumps(state.snapshot()))
                await asyncio.sleep(0.25)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            state.clients.discard(websocket)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MeshFleet browser dashboard")
    parser.add_argument("--scenario", default="configs/scenarios/scenario_03.yaml")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--udp-port", type=int, default=BROADCAST_PORT)
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.is_absolute():
        scenario_path = PROJECT_ROOT / scenario_path

    import uvicorn

    uvicorn.run(create_app(DashboardState(scenario_path, args.udp_port)), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

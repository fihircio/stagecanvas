from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from typing import Any
from urllib import request

import websockets


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def heartbeat_loop(base_url: str, node_id: str, state: dict[str, Any]) -> None:
    endpoint = f"{base_url}/api/v1/nodes/{node_id}/heartbeat"
    while True:
        if state["status"] == "PLAYING":
            state["position_ms"] += 1000
            state["drift_ms"] = random.uniform(-2.5, 2.5)
        payload = {
            "status": state["status"],
            "show_id": state.get("show_id"),
            "position_ms": state["position_ms"],
            "drift_ms": state["drift_ms"],
            "metrics": {
                "cpu_pct": random.uniform(20.0, 55.0),
                "gpu_pct": random.uniform(35.0, 80.0),
                "fps": random.uniform(58.0, 60.0),
                "dropped_frames": state["dropped_frames"],
            },
        }
        try:
            post_json(endpoint, payload)
        except Exception:
            pass
        await asyncio.sleep(1)


async def ws_loop(base_url: str, node_id: str, state: dict[str, Any]) -> None:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    uri = f"{ws_url}/ws/nodes/{node_id}"

    while True:
        try:
            async with websockets.connect(uri) as ws:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") != "COMMAND":
                        continue

                    command = msg.get("command")
                    payload = msg.get("payload", {})
                    if command == "PLAY_AT":
                        target = msg.get("target_time_ms", int(time.time() * 1000))
                        now = int(time.time() * 1000)
                        await asyncio.sleep(max(0, target - now) / 1000.0)
                        state["status"] = "PLAYING"
                        state["show_id"] = payload.get("show_id", state.get("show_id"))
                    elif command == "PAUSE":
                        state["status"] = "PAUSED"
                    elif command == "STOP":
                        state["status"] = "READY"
                        state["position_ms"] = 0
                    elif command == "LOAD_SHOW":
                        state["show_id"] = payload.get("show_id", state.get("show_id"))
                        state["status"] = "READY"
                    elif command == "SEEK":
                        state["position_ms"] = int(payload.get("position_ms", state["position_ms"]))
        except Exception:
            await asyncio.sleep(1)


async def main() -> None:
    parser = argparse.ArgumentParser(description="StageCanvas mock render node")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--node-id", default="mock-node-1")
    parser.add_argument("--label", default="Mock Node 1")
    args = parser.parse_args()

    post_json(
        f"{args.base_url}/api/v1/nodes/register",
        {
            "node_id": args.node_id,
            "label": args.label,
            "capabilities": {"type": "mock", "outputs": 1},
        },
    )

    state: dict[str, Any] = {
        "status": "READY",
        "show_id": "demo-show",
        "position_ms": 0,
        "drift_ms": 0.0,
        "dropped_frames": 0,
    }

    await asyncio.gather(
        heartbeat_loop(args.base_url, args.node_id, state),
        ws_loop(args.base_url, args.node_id, state),
    )


if __name__ == "__main__":
    asyncio.run(main())


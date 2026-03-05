from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any, cast

import httpx
import websockets

from .bridge import MockUnityBridge, NullRendererBridge, RendererBridge
from .state import CommandType, NodeState


class RenderNodeAgent:
    def __init__(
        self,
        base_url: str,
        node_id: str,
        label: str,
        outputs: int = 1,
        bridge: RendererBridge | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.node_id = node_id
        self.label = label
        self.outputs = outputs
        self.bridge = bridge or NullRendererBridge()
        self.state = NodeState(node_id=node_id, label=label, bridge=self.bridge)
        self._client = httpx.AsyncClient(timeout=5.0)

    async def register(self) -> None:
        payload = {
            "node_id": self.node_id,
            "label": self.label,
            "capabilities": {
                "type": "render-node-agent",
                "outputs": self.outputs,
                "protocol_version": "v1",
            },
        }
        resp = await self._client.post(f"{self.base_url}/api/v1/nodes/register", json=payload)
        resp.raise_for_status()

    async def heartbeat_loop(self) -> None:
        endpoint = f"{self.base_url}/api/v1/nodes/{self.node_id}/heartbeat"
        while True:
            payload = await self.state.heartbeat_payload()
            try:
                resp = await self._client.post(endpoint, json=payload)
                resp.raise_for_status()
            except Exception:
                pass
            await asyncio.sleep(1.0)

    async def playback_loop(self) -> None:
        last = int(time.time() * 1000)
        while True:
            now = int(time.time() * 1000)
            await self.state.tick(max(0, now - last))
            last = now
            await asyncio.sleep(0.2)

    async def ws_command_loop(self) -> None:
        ws_base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        uri = f"{ws_base}/ws/nodes/{self.node_id}"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") != "COMMAND":
                            continue
                        await self.state.apply_command(
                            command=cast(CommandType, msg.get("command")),
                            seq=int(msg.get("seq", 0)),
                            payload=cast(dict[str, Any] | None, msg.get("payload")),
                            target_time_ms=cast(int | None, msg.get("target_time_ms")),
                        )
            except Exception:
                await asyncio.sleep(1.0)

    async def run(self) -> None:
        await self.bridge.connect(self.node_id, self.label)
        await self.register()
        await asyncio.gather(
            self.heartbeat_loop(),
            self.playback_loop(),
            self.ws_command_loop(),
        )

    async def close(self) -> None:
        await self._client.aclose()
        await self.bridge.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="StageCanvas render-node agent")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--node-id", default="render-node-1")
    parser.add_argument("--label", default="Render Node 1")
    parser.add_argument("--outputs", type=int, default=1)
    parser.add_argument("--bridge", choices=["null", "mock-unity"], default="null")
    args = parser.parse_args()

    bridge: RendererBridge
    if args.bridge == "mock-unity":
        bridge = MockUnityBridge()
    else:
        bridge = NullRendererBridge()

    agent = RenderNodeAgent(
        base_url=args.base_url,
        node_id=args.node_id,
        label=args.label,
        outputs=args.outputs,
        bridge=bridge,
    )
    try:
        await agent.run()
    finally:
        await agent.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

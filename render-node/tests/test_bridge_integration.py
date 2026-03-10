from __future__ import annotations

import unittest
from typing import Any

from app.bridge import RendererBridge
from app.state import NodeState


class RecordingBridge(RendererBridge):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def connect(self, node_id: str, label: str) -> None:
        self.calls.append(("connect", {"node_id": node_id, "label": label}))

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        self.calls.append(("load_show", {"show_id": show_id, "payload": payload}))

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        self.calls.append(
            ("play_at", {"show_id": show_id, "target_time_ms": target_time_ms, "payload": payload})
        )

    async def pause(self) -> None:
        self.calls.append(("pause", {}))

    async def seek(self, position_ms: int) -> None:
        self.calls.append(("seek", {"position_ms": position_ms}))

    async def stop(self) -> None:
        self.calls.append(("stop", {}))

    async def ping(self) -> None:
        self.calls.append(("ping", {}))

    async def tick(self, snapshot: dict[str, Any]) -> None:
        return

    async def close(self) -> None:
        return


class FaultyBridge(RecordingBridge):
    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        raise RuntimeError("bridge_failure")


class BridgeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_call_order_load_play(self) -> None:
        bridge = RecordingBridge()
        state = NodeState(node_id="node-1", label="Node 1", bridge=bridge)

        await state.apply_command("LOAD_SHOW", seq=1, payload={"show_id": "demo-show"}, target_time_ms=None)
        await state.apply_command(
            "PLAY_AT", seq=2, payload={"show_id": "demo-show"}, target_time_ms=1_700_000_000_000
        )

        self.assertEqual(bridge.calls[0][0], "load_show")
        self.assertEqual(bridge.calls[1][0], "play_at")
        self.assertEqual(bridge.calls[1][1]["target_time_ms"], 1_700_000_000_000)

    async def test_bridge_error_marks_node_error(self) -> None:
        bridge = FaultyBridge()
        state = NodeState(node_id="node-1", label="Node 1", bridge=bridge)

        await state.apply_command(
            "PLAY_AT", seq=1, payload={"show_id": "demo-show"}, target_time_ms=1_700_000_000_000
        )

        self.assertEqual(state.status, "ERROR")
        self.assertTrue(state.command_history)
        self.assertEqual(state.command_history[-1]["status"], "error")
        self.assertIn("bridge_failure", state.command_history[-1]["detail"])


if __name__ == "__main__":
    unittest.main()

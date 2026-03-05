from __future__ import annotations

import unittest
from typing import Any

from app.bridge import RendererBridge
from app.state import NodeState


class RecordingBridge(RendererBridge):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def connect(self, node_id: str, label: str) -> None:
        self.events.append(("connect", {"node_id": node_id, "label": label}))

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        self.events.append(("load_show", {"show_id": show_id, "payload": payload}))

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        self.events.append(("play_at", {"show_id": show_id, "target_time_ms": target_time_ms, "payload": payload}))

    async def pause(self) -> None:
        self.events.append(("pause", {}))

    async def seek(self, position_ms: int) -> None:
        self.events.append(("seek", {"position_ms": position_ms}))

    async def stop(self) -> None:
        self.events.append(("stop", {}))

    async def ping(self) -> None:
        self.events.append(("ping", {}))

    async def tick(self, snapshot: dict[str, Any]) -> None:
        self.events.append(("tick", snapshot))

    async def close(self) -> None:
        self.events.append(("close", {}))


class FailingSeekBridge(RecordingBridge):
    async def seek(self, position_ms: int) -> None:
        raise RuntimeError("seek_failed")


class NodeStateBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_bridge_receives_commands_in_order(self) -> None:
        bridge = RecordingBridge()
        state = NodeState(node_id="r1", label="Render 1", bridge=bridge)

        await state.apply_command("LOAD_SHOW", seq=1, payload={"show_id": "show-x"}, target_time_ms=None)
        await state.apply_command("PLAY_AT", seq=2, payload={"show_id": "show-x"}, target_time_ms=None)
        await state.apply_command("PAUSE", seq=3, payload={}, target_time_ms=None)
        await state.apply_command("STOP", seq=4, payload={}, target_time_ms=None)

        names = [name for name, _ in bridge.events]
        self.assertEqual(names, ["load_show", "play_at", "pause", "stop"])

    async def test_bridge_error_sets_state_error_and_history(self) -> None:
        bridge = FailingSeekBridge()
        state = NodeState(node_id="r2", label="Render 2", bridge=bridge)

        await state.apply_command("SEEK", seq=5, payload={"position_ms": 900}, target_time_ms=None)

        self.assertEqual(state.status, "ERROR")
        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_command"]["status"], "error")
        self.assertIn("seek_failed", snapshot["last_command"]["detail"])


if __name__ == "__main__":
    unittest.main()

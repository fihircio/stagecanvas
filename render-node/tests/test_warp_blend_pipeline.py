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

    async def set_mapping(self, mapping_config: dict[str, Any]) -> None:
        self.events.append(("set_mapping", {"mapping_config": mapping_config}))

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        self.events.append(("load_show", {"show_id": show_id, "payload": payload}))

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        self.events.append(("play_at", {"show_id": show_id, "target_time_ms": target_time_ms, "payload": payload}))

    async def play_clip(self, asset_id: str, start_time_ms: int = 0) -> None:
        pass

    async def pause(self) -> None:
        self.events.append(("pause", {}))

    async def seek(self, position_ms: int) -> None:
        self.events.append(("seek", {"position_ms": position_ms}))

    async def stop(self) -> None:
        self.events.append(("stop", {}))

    async def ping(self) -> None:
        self.events.append(("ping", {}))

    async def update_layers(self, layers: list[dict[str, Any]]) -> None:
        self.events.append(("update_layers", {"layers": layers}))

    async def tick(self, snapshot: dict[str, Any]) -> None:
        self.events.append(("tick", snapshot))

    async def close(self) -> None:
        self.events.append(("close", {}))

    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None:
        self.events.append(("hot_swap", {"layer_id": layer_id, "payload": payload}))


class FailingMappingBridge(RecordingBridge):
    async def set_mapping(self, mapping_config: dict[str, Any]) -> None:
        raise RuntimeError("mapping_failed")


class WarpBlendPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_mapping_config_propagates_to_bridge(self) -> None:
        bridge = RecordingBridge()
        state = NodeState(node_id="w1", label="Warp 1", bridge=bridge)
        mapping_config = {"outputs": [{"output_id": "A", "mesh": "mesh-a"}]}

        await state.apply_command(
            "LOAD_SHOW",
            seq=1,
            payload={"show_id": "show-warp", "mapping_config": mapping_config},
            target_time_ms=None,
        )

        self.assertEqual(state.mapping_config, mapping_config)
        names = [name for name, _ in bridge.events]
        self.assertEqual(names[:2], ["set_mapping", "load_show"])

    async def test_mapping_config_error_marks_state_error(self) -> None:
        bridge = FailingMappingBridge()
        state = NodeState(node_id="w2", label="Warp 2", bridge=bridge)
        mapping_config = {"outputs": [{"output_id": "B", "mesh": "mesh-b"}]}

        await state.apply_command(
            "LOAD_SHOW",
            seq=2,
            payload={"show_id": "show-warp", "mapping_config": mapping_config},
            target_time_ms=None,
        )

        self.assertEqual(state.status, "ERROR")
        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_command"]["status"], "error")
        self.assertIn("mapping_failed", snapshot["last_command"]["detail"])


if __name__ == "__main__":
    unittest.main()

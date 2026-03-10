from __future__ import annotations

import unittest

from app.bridge import NullRendererBridge
from app.state import NodeState


class RecordingBridge(NullRendererBridge):
    def __init__(self) -> None:
        super().__init__()
        self.mapping_calls: list[dict] = []
        self.load_calls: list[dict] = []

    async def set_mapping(self, mapping_config: dict) -> None:
        self.mapping_calls.append(mapping_config)

    async def load_show(self, show_id: str, payload: dict) -> None:
        self.load_calls.append({"show_id": show_id, "payload": payload})


class MappingConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_load_show_applies_mapping_config(self) -> None:
        bridge = RecordingBridge()
        state = NodeState(node_id="node-map", label="Node Map", bridge=bridge)
        mapping_config = {
            "version": "v1",
            "outputs": [
                {
                    "output_id": "out-1",
                    "mesh": {
                        "vertices": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
                        "uvs": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
                        "indices": [0, 1, 2],
                    },
                    "blend": {"gamma": 1.0, "brightness": 1.0, "black_level": 0.0},
                }
            ],
        }
        await state.apply_command(
            "LOAD_SHOW",
            seq=1,
            payload={"show_id": "show-map", "mapping_config": mapping_config},
            target_time_ms=None,
        )

        self.assertEqual(state.mapping_config, mapping_config)
        self.assertEqual(len(bridge.mapping_calls), 1)
        self.assertEqual(bridge.mapping_calls[0], mapping_config)
        self.assertEqual(len(bridge.load_calls), 1)
        self.assertEqual(bridge.load_calls[0]["payload"].get("mapping_config"), mapping_config)


if __name__ == "__main__":
    unittest.main()

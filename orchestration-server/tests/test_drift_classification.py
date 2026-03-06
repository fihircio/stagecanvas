from __future__ import annotations

import sys
import unittest
from pathlib import Path

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.models import HeartbeatRequest, RegisterNodeRequest
from app.registry import NodeRegistry


def hb(drift_ms: float) -> HeartbeatRequest:
    return HeartbeatRequest.model_validate(
        {
            "status": "READY",
            "metrics": {
                "cpu_pct": 10.0,
                "gpu_pct": 20.0,
                "fps": 60.0,
                "dropped_frames": 0,
            },
            "position_ms": 100,
            "drift_ms": drift_ms,
            "show_id": "demo-show",
        }
    )


class DriftClassificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_boundaries_match_determinism_spec(self) -> None:
        registry = NodeRegistry()
        await registry.register(RegisterNodeRequest(node_id="n1", label="Node 1", capabilities={}))
        await registry.register(RegisterNodeRequest(node_id="n2", label="Node 2", capabilities={}))
        await registry.register(RegisterNodeRequest(node_id="n3", label="Node 3", capabilities={}))

        await registry.heartbeat("n1", hb(1.99))
        await registry.heartbeat("n2", hb(2.0))
        await registry.heartbeat("n3", hb(8.0))

        nodes = {node["node_id"]: node for node in await registry.list_nodes()}
        self.assertEqual(nodes["n1"]["drift_level"], "OK")
        self.assertEqual(nodes["n2"]["drift_level"], "WARN")
        self.assertEqual(nodes["n3"]["drift_level"], "CRITICAL")

        slo = await registry.drift_summary()
        self.assertEqual(slo["ok"], 1)
        self.assertEqual(slo["warn"], 1)
        self.assertEqual(slo["critical"], 1)

    async def test_negative_drift_uses_absolute_value(self) -> None:
        registry = NodeRegistry()
        await registry.register(RegisterNodeRequest(node_id="n1", label="Node 1", capabilities={}))

        await registry.heartbeat("n1", hb(-8.1))
        node = (await registry.list_nodes())[0]

        self.assertEqual(node["drift_level"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()

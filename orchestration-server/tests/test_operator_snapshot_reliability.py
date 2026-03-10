from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

import app.main as main_mod
from app.command_ledger import CommandLedger
from app.registry import NodeRegistry


class OperatorSnapshotReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-reliability.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

        reg = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-r1", "label": "Node R1", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_operator_snapshot_contains_reliability_counters(self) -> None:
        # Queue one command for offline node and create a replay/stale command attempt.
        first = self.client.post(
            "/api/v1/nodes/node-r1/commands",
            json={"version": "v1", "command": "PING", "payload": {}, "seq": 10, "origin": "system"},
        )
        self.assertEqual(first.status_code, 200, first.text)

        duplicate = self.client.post(
            "/api/v1/nodes/node-r1/commands",
            json={"version": "v1", "command": "PING", "payload": {}, "seq": 10, "origin": "system"},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)

        # Establish and close node WS twice to produce reconnect_count >= 1.
        with self.client.websocket_connect("/ws/nodes/node-r1") as ws:
            _ = json.loads(ws.receive_text())
        with self.client.websocket_connect("/ws/nodes/node-r1"):
            pass

        for drift_ms in (0.5, 2.6, 9.2):
            hb = self.client.post(
                "/api/v1/nodes/node-r1/heartbeat",
                json={
                    "version": "v1",
                    "status": "READY",
                    "show_id": "demo-show",
                    "position_ms": 0,
                    "drift_ms": drift_ms,
                    "metrics": {"cpu_pct": 12.0, "gpu_pct": 10.0, "fps": 60.0, "dropped_frames": 0},
                },
            )
            self.assertEqual(hb.status_code, 200, hb.text)

        with self.client.websocket_connect("/ws/operators") as ws:
            snapshot = ws.receive_json()

        self.assertEqual(snapshot["type"], "NODES_SNAPSHOT")
        node = snapshot["nodes"][0]
        self.assertIn("replay_count", node)
        self.assertIn("queued_count", node)
        self.assertIn("reconnect_count", node)
        self.assertIn("queue_depth", node)
        self.assertGreaterEqual(int(node["queued_count"]), 1)
        self.assertGreaterEqual(int(node["replay_count"]), 1)
        self.assertGreaterEqual(int(node["reconnect_count"]), 1)
        self.assertIn("drift_history_summary", node)
        summary = node["drift_history_summary"]
        self.assertGreaterEqual(int(summary["sample_count"]), 3)
        self.assertGreaterEqual(float(summary["max_abs_drift_ms"]), 9.0)
        self.assertGreaterEqual(int(summary["warn_samples"]), 1)
        self.assertGreaterEqual(int(summary["critical_samples"]), 1)


if __name__ == "__main__":
    unittest.main()

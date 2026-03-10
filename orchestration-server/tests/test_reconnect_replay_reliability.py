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


class ReconnectReplayReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-reconnect.db"
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

    def _pending_count(self) -> int:
        nodes = self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        return int(nodes.json()["nodes"][0]["pending_commands"])

    def test_offline_queue_replays_once_and_preserves_order_on_reconnect(self) -> None:
        stop = self.client.post(
            "/api/v1/operators/stop",
            json={"payload": {}, "node_ids": ["node-r1"], "request_id": "reconnect-stop-1"},
        )
        self.assertEqual(stop.status_code, 200, stop.text)
        stop_seq = int(stop.json()["seq"])
        self.assertEqual(self._pending_count(), 1)

        with self.client.websocket_connect("/ws/nodes/node-r1") as ws:
            first = json.loads(ws.receive_text())
            self.assertEqual(first["command"], "STOP")
            self.assertEqual(int(first["seq"]), stop_seq)
        self.assertEqual(self._pending_count(), 0)

        # Reconnect alone must not requeue/replay old command.
        with self.client.websocket_connect("/ws/nodes/node-r1"):
            pass
        self.assertEqual(self._pending_count(), 0)

        pause = self.client.post(
            "/api/v1/operators/pause",
            json={"payload": {}, "node_ids": ["node-r1"], "request_id": "reconnect-pause-1"},
        )
        self.assertEqual(pause.status_code, 200, pause.text)
        pause_seq = int(pause.json()["seq"])
        self.assertGreater(pause_seq, stop_seq)
        self.assertEqual(self._pending_count(), 1)

        with self.client.websocket_connect("/ws/nodes/node-r1") as ws:
            second = json.loads(ws.receive_text())
            self.assertEqual(second["command"], "PAUSE")
            self.assertEqual(int(second["seq"]), pause_seq)
            self.assertGreater(int(second["seq"]), int(first["seq"]))
        self.assertEqual(self._pending_count(), 0)


if __name__ == "__main__":
    unittest.main()

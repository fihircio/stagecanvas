from __future__ import annotations

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


class PreviewPipelineStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preview.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

        reg = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-p1", "label": "Node P1", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_preview_snapshot_stub(self) -> None:
        res = self.client.post(
            "/api/v1/preview/snapshot",
            json={"node_ids": ["node-p1"], "show_id": "demo-show"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["requested_count"], 1)
        self.assertEqual(len(payload["snapshots"]), 1)
        snapshot = payload["snapshots"][0]
        self.assertEqual(snapshot["node_id"], "node-p1")
        self.assertIn("timestamp_ms", snapshot)
        self.assertTrue(snapshot["ok"])


if __name__ == "__main__":
    unittest.main()

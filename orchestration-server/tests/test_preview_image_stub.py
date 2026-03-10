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


class PreviewImageStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preview-image.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        self._orig_preview = main_mod.preview_image_last_request

        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        main_mod.preview_image_last_request = {}
        self.client = TestClient(main_mod.app)

        reg = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-img", "label": "Node IMG", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        main_mod.preview_image_last_request = self._orig_preview
        self._tmp.cleanup()

    def test_preview_image_stub_updates_last_request(self) -> None:
        res = self.client.post(
            "/api/v1/preview/image",
            json={"node_ids": ["node-img"], "show_id": "demo-show", "width": 320, "height": 180},
        )
        self.assertEqual(res.status_code, 200, res.text)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["requested_count"], 1)
        entry = payload["images"][0]
        self.assertEqual(entry["node_id"], "node-img")
        self.assertIn("image_data", entry)
        self.assertIn("timestamp_ms", entry)
        self.assertIn("node-img", main_mod.preview_image_last_request)


if __name__ == "__main__":
    unittest.main()

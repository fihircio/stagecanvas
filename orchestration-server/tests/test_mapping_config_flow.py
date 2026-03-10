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
from app.timeline_repository import TimelineRepository


class MappingConfigFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp.name) / "timeline.db"
        self._ledger_path = Path(self._tmp.name) / "orchestration.db"
        self._orig_registry = main_mod.registry
        self._orig_timeline = main_mod.timeline_repo
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.timeline_repo = TimelineRepository(self._db_path)
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

        reg = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-map", "label": "Node Map", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.timeline_repo = self._orig_timeline
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_mapping_config_flow_from_show_to_load_show(self) -> None:
        mapping_config = {
            "version": "v1",
            "outputs": [
                {
                    "output_id": "out-1",
                    "target_node_id": None,
                    "mesh": {
                        "vertices": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
                        "uvs": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
                        "indices": [0, 1, 2],
                    },
                    "blend": {"gamma": 1.0, "brightness": 1.0, "black_level": 0.0},
                    "canvas_region": {"global_x": 0, "global_y": 0, "width": 1920, "height": 1080},
                }
            ],
            "fixture_profiles": [],
        }
        show_id = "show-map"
        res = self.client.put(
            f"/api/v1/timeline/shows/{show_id}",
            json={"duration_ms": 120000, "mapping_config": mapping_config},
        )
        self.assertEqual(res.status_code, 200, res.text)

        load = self.client.post(
            "/api/v1/operators/load_show",
            json={"payload": {"show_id": show_id}, "node_ids": ["node-map"]},
        )
        self.assertEqual(load.status_code, 200, load.text)

        node_record = main_mod.registry._nodes["node-map"]
        self.assertTrue(node_record.pending_commands)
        payload = node_record.pending_commands[0]["payload"]
        self.assertEqual(payload.get("mapping_config"), mapping_config)

    def test_invalid_mapping_config_rejected(self) -> None:
        bad_config = {"version": "v1", "outputs": []}
        res = self.client.post(
            "/api/v1/operators/load_show",
            json={"payload": {"show_id": "demo-show", "mapping_config": bad_config}, "node_ids": ["node-map"]},
        )
        self.assertEqual(res.status_code, 422, res.text)
        detail = res.json().get("detail", {})
        self.assertEqual(detail.get("reason_code"), "INVALID_MAPPING_CONFIG")


if __name__ == "__main__":
    unittest.main()

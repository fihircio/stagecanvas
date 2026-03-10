from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from pydantic import ValidationError

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

import app.main as main_mod
from app.command_ledger import CommandLedger
from app.models import MappingConfig
from app.registry import NodeRegistry


class MappingConfigSchemaTests(unittest.TestCase):
    def test_mapping_config_validates(self) -> None:
        payload = {
            "version": "v1",
            "outputs": [
                {
                    "output_id": "out-1",
                    "mesh": {
                        "vertices": [0.0, 0.0, 1.0, 0.0, 1.0, 1.0],
                        "uvs": [0.0, 0.0, 1.0, 0.0, 1.0, 1.0],
                        "indices": [0, 1, 2],
                    },
                    "blend": {"gamma": 1.0, "brightness": 1.0, "black_level": 0.0},
                }
            ],
        }
        cfg = MappingConfig.model_validate(payload)
        self.assertEqual(cfg.version, "v1")
        self.assertEqual(len(cfg.outputs), 1)

    def test_mapping_config_rejects_bad_version(self) -> None:
        with self.assertRaises(ValidationError):
            MappingConfig.model_validate({"version": "v2", "outputs": []})

    def test_mapping_config_rejects_uv_mismatch(self) -> None:
        with self.assertRaises(ValidationError):
            MappingConfig.model_validate(
                {
                    "version": "v1",
                    "outputs": [
                        {
                            "output_id": "out-1",
                            "mesh": {
                                "vertices": [0.0, 0.0, 1.0, 0.0, 1.0, 1.0],
                                "uvs": [0.0, 0.0, 1.0, 0.0],
                                "indices": [0, 1, 2],
                            },
                        }
                    ],
                }
            )


class MappingConfigEndpointValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-mapping.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

        reg = self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-m1", "label": "Node M1", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_operator_load_show_rejects_invalid_mapping(self) -> None:
        response = self.client.post(
            "/api/v1/operators/load_show",
            json={
                "node_ids": ["node-m1"],
                "payload": {
                    "show_id": "demo-show",
                    "mapping_config": {"version": "v9", "outputs": []},
                },
                "request_id": "load-mapping-1",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["reason_code"], "INVALID_MAPPING_CONFIG")

    def test_timeline_upsert_show_rejects_invalid_mapping(self) -> None:
        response = self.client.put(
            "/api/v1/timeline/shows/demo-show",
            json={
                "duration_ms": 5_000,
                "mapping_config": {"version": "v2", "outputs": []},
            },
        )
        self.assertEqual(response.status_code, 422, response.text)


if __name__ == "__main__":
    unittest.main()

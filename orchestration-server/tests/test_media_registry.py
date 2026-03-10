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
from app.registry import MediaRegistry, NodeRegistry


class MediaRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-media.db"
        self._orig_registry = main_mod.registry
        self._orig_media_registry = main_mod.media_registry
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.media_registry = MediaRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.media_registry = self._orig_media_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_media_registry_crud_and_idempotency(self) -> None:
        payload = {
            "asset_id": "asset-001",
            "label": "Intro clip",
            "codec_profile": "h264-main",
            "duration_ms": 12_000,
            "size_bytes": 50_000_000,
            "checksum": "abc123",
            "uri": "s3://bucket/intro.mp4",
        }

        first = self.client.post("/api/v1/media", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        first_data = first.json()
        self.assertTrue(first_data["ok"])
        self.assertFalse(first_data["idempotent"])
        asset = first_data["asset"]
        self.assertEqual(asset["asset_id"], payload["asset_id"])
        self.assertEqual(asset["status"], "REGISTERED")

        second = self.client.post("/api/v1/media", json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertTrue(second.json()["idempotent"])

        conflict = self.client.post(
            "/api/v1/media",
            json={
                **payload,
                "codec_profile": "h265",
            },
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(conflict.json()["detail"]["reason_code"], "ASSET_ID_MISMATCH")

        listing = self.client.get("/api/v1/media")
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual(len(listing.json()["assets"]), 1)

        detail = self.client.get("/api/v1/media/asset-001")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["asset"]["codec_profile"], "h264-main")

        update = self.client.patch(
            "/api/v1/media/asset-001",
            json={"status": "READY", "error_message": None},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["asset"]["status"], "READY")

        missing = self.client.patch(
            "/api/v1/media/asset-missing",
            json={"status": "FAILED", "error_message": "missing"},
        )
        self.assertEqual(missing.status_code, 404, missing.text)


if __name__ == "__main__":
    unittest.main()

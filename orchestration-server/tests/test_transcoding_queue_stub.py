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
from app.registry import MediaRegistry, NodeRegistry, TranscodeQueue


class TranscodingQueueStubTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-transcode.db"
        self._orig_registry = main_mod.registry
        self._orig_media_registry = main_mod.media_registry
        self._orig_transcode_queue = main_mod.transcode_queue
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.media_registry = MediaRegistry()
        main_mod.transcode_queue = TranscodeQueue()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = TestClient(main_mod.app)

        asset = self.client.post(
            "/api/v1/media",
            json={
                "asset_id": "asset-1",
                "codec_profile": "H264",
                "duration_ms": 12000,
                "size_bytes": 1024,
            },
        )
        self.assertEqual(asset.status_code, 200, asset.text)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.registry = self._orig_registry
        main_mod.media_registry = self._orig_media_registry
        main_mod.transcode_queue = self._orig_transcode_queue
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    def test_enqueue_update_and_query(self) -> None:
        enqueue = self.client.post("/api/v1/media/asset-1/transcode", json={"target_profile": "HAP"})
        self.assertEqual(enqueue.status_code, 200, enqueue.text)
        job = enqueue.json()["job"]
        job_id = job["job_id"]
        self.assertEqual(job["status"], "QUEUED")

        listing = self.client.get("/api/v1/transcode/jobs")
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertTrue(listing.json()["jobs"])

        update = self.client.patch(
            f"/api/v1/transcode/jobs/{job_id}",
            json={"status": "RUNNING"},
        )
        self.assertEqual(update.status_code, 200, update.text)
        self.assertEqual(update.json()["job"]["status"], "RUNNING")

        finish = self.client.patch(
            f"/api/v1/transcode/jobs/{job_id}",
            json={"status": "DONE"},
        )
        self.assertEqual(finish.status_code, 200, finish.text)
        self.assertEqual(finish.json()["job"]["status"], "DONE")

        get_job = self.client.get(f"/api/v1/transcode/jobs/{job_id}")
        self.assertEqual(get_job.status_code, 200, get_job.text)
        self.assertEqual(get_job.json()["job"]["job_id"], job_id)

    def test_missing_asset_rejected(self) -> None:
        res = self.client.post("/api/v1/media/missing/transcode", json={"target_profile": "HAP"})
        self.assertEqual(res.status_code, 404, res.text)


if __name__ == "__main__":
    unittest.main()

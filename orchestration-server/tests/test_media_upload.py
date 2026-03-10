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
from app.registry import MediaRegistry


class MediaUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._media_dir = Path(self._tmp.name) / "media"
        self._registry_path = Path(self._tmp.name) / "media_registry.json"
        self._orig_media_dir = main_mod.MEDIA_STORAGE_DIR
        self._orig_registry = main_mod.media_registry

        main_mod.MEDIA_STORAGE_DIR = self._media_dir
        main_mod.media_registry = MediaRegistry(self._registry_path)
        self.client = TestClient(main_mod.app)

    def tearDown(self) -> None:
        self.client.close()
        main_mod.MEDIA_STORAGE_DIR = self._orig_media_dir
        main_mod.media_registry = self._orig_registry
        self._tmp.cleanup()

    def test_media_upload_creates_registry_entry(self) -> None:
        payload = {
            "asset_id": "asset-upload-1",
            "codec_profile": "H264",
            "duration_ms": "1200",
        }
        files = {"file": ("clip.mov", b"hello-world", "application/octet-stream")}
        res = self.client.post("/api/v1/media/upload", data=payload, files=files)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        asset = body["asset"]
        self.assertEqual(asset["asset_id"], "asset-upload-1")
        self.assertEqual(asset["label"], "clip.mov")
        self.assertEqual(asset["size_bytes"], len(b"hello-world"))
        self.assertIsNotNone(asset["checksum"])
        self.assertTrue(asset["checksum"])
        self.assertIn("file://", asset["uri"])

        stored_files = list(self._media_dir.glob("asset-upload-1_*"))
        self.assertEqual(len(stored_files), 1)
        self.assertTrue(stored_files[0].exists())
        self.assertEqual(stored_files[0].read_bytes(), b"hello-world")


if __name__ == "__main__":
    unittest.main()

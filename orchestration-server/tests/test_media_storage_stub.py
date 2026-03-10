from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.models import MediaAssetCreateRequest, MediaAssetUpdateRequest
from app.registry import MediaRegistry


class MediaStorageStubTests(unittest.IsolatedAsyncioTestCase):
    async def test_media_registry_persists_to_disk_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "media_registry.json"
            registry = MediaRegistry(storage_path)
            record, is_new, _ = await registry.register(
                MediaAssetCreateRequest(
                    asset_id="asset-100",
                    label="Intro",
                    codec_profile="h264",
                    duration_ms=1000,
                    size_bytes=2048,
                    checksum="abc",
                    uri="file:///intro.mp4",
                )
            )
            self.assertTrue(is_new)

            await registry.update("asset-100", MediaAssetUpdateRequest(status="READY"))

            reloaded = MediaRegistry(storage_path)
            fetched = await reloaded.get("asset-100")
            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched.status, "READY")
            listing = await reloaded.list_assets()
            self.assertEqual(len(listing), 1)
            self.assertEqual(listing[0].asset_id, "asset-100")


if __name__ == "__main__":
    unittest.main()

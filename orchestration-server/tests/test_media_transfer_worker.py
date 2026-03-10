from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.models import MediaAssetCreateRequest, RegisterNodeRequest
from app.registry import AssetTransferWorker, MediaRegistry, NodeRegistry, TransferTask


class MediaTransferWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_transfer_worker_copies_media_to_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            media_dir = Path(tmpdir) / "media"
            cache_dir = Path(tmpdir) / "cache"
            media_dir.mkdir(parents=True, exist_ok=True)
            cache_dir.mkdir(parents=True, exist_ok=True)
            registry_path = Path(tmpdir) / "media_registry.json"

            source_path = media_dir / "asset-a.bin"
            source_bytes = b"transfer-me"
            source_path.write_bytes(source_bytes)

            media_registry = MediaRegistry(registry_path)
            await media_registry.register(
                MediaAssetCreateRequest(
                    asset_id="asset-a",
                    label="asset-a.bin",
                    codec_profile="H264",
                    duration_ms=0,
                    size_bytes=len(source_bytes),
                    checksum="abc",
                    uri=f"file://{source_path}",
                    status="READY",
                )
            )

            registry = NodeRegistry()
            await registry.register(RegisterNodeRequest(node_id="node-1", label="Node 1", capabilities={}))
            record = await registry.get("node-1")
            assert record is not None
            record.cache = {
                **record.cache,
                "asset_total": 1,
                "cached_assets": 0,
                "bytes_total": len(source_bytes),
                "bytes_cached": 0,
                "preload_state": "LOADING",
            }

            worker = AssetTransferWorker(
                registry,
                media_registry=media_registry,
                media_root=media_dir,
                cache_root=cache_dir,
            )
            task = TransferTask(
                node_id="node-1",
                show_id="show-x",
                media_id="asset-a",
                size_bytes=0,
                next_run_ms=0,
            )
            worker.enqueue(task)
            await registry.update_transfer_queue_depth("node-1", worker.pending_count())

            ran = await worker.run_once(now_ms=0)
            self.assertTrue(ran)

            dest_path = cache_dir / "node-1" / source_path.name
            self.assertTrue(dest_path.exists())
            self.assertEqual(dest_path.read_bytes(), source_bytes)

            record = await registry.get("node-1")
            assert record is not None
            self.assertEqual(record.cache.get("cached_assets"), 1)
            self.assertEqual(record.cache.get("bytes_cached"), len(source_bytes))
            self.assertEqual(record.cache.get("preload_state"), "READY")


if __name__ == "__main__":
    unittest.main()

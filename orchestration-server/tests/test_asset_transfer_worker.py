from __future__ import annotations

import unittest
from pathlib import Path
import sys

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.models import RegisterNodeRequest
from app.registry import AssetTransferWorker, NodeRegistry, TransferTask


class AssetTransferWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_retries_with_backoff_and_updates_cache(self) -> None:
        registry = NodeRegistry()
        await registry.register(RegisterNodeRequest(node_id="node-1", label="Node 1", capabilities={}))
        record = await registry.get("node-1")
        assert record is not None
        record.cache = {
            **record.cache,
            "asset_total": 1,
            "cached_assets": 0,
            "bytes_total": 100,
            "bytes_cached": 0,
            "preload_state": "LOADING",
        }

        attempts: list[int] = []

        def handler(task: TransferTask) -> bool:
            attempts.append(task.attempt)
            return task.attempt >= 1

        worker = AssetTransferWorker(registry, handler=handler)
        now_ms = 1000
        task = TransferTask(
            node_id="node-1",
            show_id="show-a",
            media_id="m1",
            size_bytes=100,
            next_run_ms=now_ms,
        )
        worker.enqueue(task)
        await registry.update_transfer_queue_depth("node-1", worker.pending_count())

        ran = await worker.run_once(now_ms=now_ms)
        self.assertTrue(ran)
        self.assertEqual(worker.pending_count(), 1)
        self.assertEqual(record.transfer_worker_state, "IDLE")
        self.assertEqual(task.attempt, 1)
        self.assertGreater(task.next_run_ms, now_ms)

        ran = await worker.run_once(now_ms=task.next_run_ms)
        self.assertTrue(ran)
        self.assertEqual(worker.pending_count(), 0)
        self.assertEqual(record.cache["cached_assets"], 1)
        self.assertEqual(record.cache["bytes_cached"], 100)
        self.assertEqual(record.cache["preload_state"], "READY")
        self.assertEqual(record.transfer_queue_depth, 0)
        self.assertEqual(attempts, [0, 1])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from httpx import ASGITransport, AsyncClient

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

import app.main as main_mod
from app.command_ledger import CommandLedger
from app.registry import NodeRegistry


class AssetTransferStubTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-transfer.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

        reg = await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-x", "label": "Node X", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_transfer_stub_updates_cache_and_returns_commands(self) -> None:
        response = await self.client.post(
            "/api/v1/assets/transfer",
            json={
                "show_id": "show-1",
                "request_id": "transfer-1",
                "node_ids": ["node-x"],
                "assets": [
                    {"media_id": "clip-1", "uri": "s3://bucket/clip-1.mov", "size_bytes": 1000},
                    {"media_id": "clip-2", "uri": "s3://bucket/clip-2.mov", "size_bytes": 2000},
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["asset_count"], 2)
        self.assertEqual(len(body["transfer_commands"]), 2)

        nodes = await self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        cache = nodes.json()["nodes"][0]["cache"]
        self.assertEqual(cache["preload_state"], "LOADING")
        self.assertEqual(cache["asset_total"], 2)
        self.assertEqual(cache["bytes_total"], 3000)
        self.assertEqual(cache["cached_assets"], 0)

        # Simulate progress callback via heartbeat cache update.
        hb = await self.client.post(
            "/api/v1/nodes/node-x/heartbeat",
            json={
                "version": "v1",
                "status": "READY",
                "show_id": "show-1",
                "position_ms": 0,
                "drift_ms": 0.0,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                "cache": {
                    "show_id": "show-1",
                    "preload_state": "READY",
                    "asset_total": 2,
                    "cached_assets": 2,
                    "bytes_total": 3000,
                    "bytes_cached": 3000,
                    "progress_assets_pct": 100.0,
                    "progress_bytes_pct": 100.0,
                    "progress_message": "transfer",
                    "last_preload_request_id": "transfer-1",
                },
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

        nodes = await self.client.get("/api/v1/nodes")
        cache = nodes.json()["nodes"][0]["cache"]
        self.assertEqual(cache["preload_state"], "READY")
        self.assertEqual(cache["cached_assets"], 2)


if __name__ == "__main__":
    unittest.main()

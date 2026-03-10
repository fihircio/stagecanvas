from __future__ import annotations

import tempfile
import time
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


class PreloadContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preload.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

        reg = await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-preload", "label": "Node Preload", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_preload_dispatches_additive_load_show_contract(self) -> None:
        response = await self.client.post(
            "/api/v1/shows/preload",
            json={
                "show_id": "show-1",
                "request_id": "preload-1",
                "node_ids": ["node-preload"],
                "assets": [
                    {"media_id": "clip-1", "uri": "s3://bucket/clip-1.mov", "size_bytes": 1000},
                    {"media_id": "clip-2", "uri": "s3://bucket/clip-2.mov", "size_bytes": 2000},
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["preload_requested"])
        self.assertEqual(body["asset_count"], 2)
        self.assertEqual(body["dispatch"]["queued_count"], 1)

        record = await main_mod.registry.get("node-preload")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(len(record.pending_commands), 1)
        command = record.pending_commands[0]
        self.assertEqual(command["command"], "LOAD_SHOW")
        self.assertTrue(command["payload"]["preload_only"])
        self.assertEqual(command["payload"]["show_id"], "show-1")
        self.assertEqual(command["payload"]["request_id"], "preload-1")
        self.assertEqual(len(command["payload"]["assets"]), 2)

    async def test_node_cache_state_reports_via_heartbeat(self) -> None:
        hb = await self.client.post(
            "/api/v1/nodes/node-preload/heartbeat",
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
                    "asset_total": 3,
                    "cached_assets": 3,
                    "bytes_total": 3000,
                    "bytes_cached": 3000,
                    "last_preload_request_id": f"pr-{int(time.time())}",
                },
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

        nodes = await self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        node = nodes.json()["nodes"][0]
        self.assertIn("cache", node)
        self.assertEqual(node["cache"]["preload_state"], "READY")
        self.assertEqual(node["cache"]["cached_assets"], 3)


if __name__ == "__main__":
    unittest.main()

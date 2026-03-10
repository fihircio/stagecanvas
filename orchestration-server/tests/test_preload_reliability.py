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


class PreloadReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preload-rel.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

        for node_id in ("node-a", "node-b"):
            reg = await self.client.post(
                "/api/v1/nodes/register",
                json={"node_id": node_id, "label": node_id.upper(), "capabilities": {}},
            )
            self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_multi_node_preload_success_and_partial_failure(self) -> None:
        response = await self.client.post(
            "/api/v1/shows/preload",
            json={
                "show_id": "show-preload",
                "request_id": "preload-rel-1",
                "node_ids": ["node-a", "node-b"],
                "assets": [
                    {"media_id": "clip-1", "uri": "s3://bucket/clip-1.mov", "size_bytes": 1000},
                    {"media_id": "clip-2", "uri": "s3://bucket/clip-2.mov", "size_bytes": 1000},
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        dispatch = response.json()["dispatch"]
        self.assertEqual(dispatch["queued_count"], 2)

        for node_id, state, cached in (
            ("node-a", "READY", 2),
            ("node-b", "FAILED", 1),
        ):
            hb = await self.client.post(
                f"/api/v1/nodes/{node_id}/heartbeat",
                json={
                    "version": "v1",
                    "status": "READY",
                    "show_id": "show-preload",
                    "position_ms": 0,
                    "drift_ms": 0.0,
                    "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                    "cache": {
                        "show_id": "show-preload",
                        "preload_state": state,
                        "asset_total": 2,
                        "cached_assets": cached,
                        "bytes_total": 2000,
                        "bytes_cached": cached * 1000,
                    },
                },
            )
            self.assertEqual(hb.status_code, 200, hb.text)

        nodes = await self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        cache_states = {n["node_id"]: n["cache"]["preload_state"] for n in nodes.json()["nodes"]}
        self.assertEqual(cache_states["node-a"], "READY")
        self.assertEqual(cache_states["node-b"], "FAILED")

    async def test_preload_retry_new_request_dispatches_again(self) -> None:
        first = await self.client.post(
            "/api/v1/shows/preload",
            json={"show_id": "show-preload", "request_id": "preload-rel-2", "node_ids": ["node-a"], "assets": []},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second = await self.client.post(
            "/api/v1/shows/preload",
            json={"show_id": "show-preload", "request_id": "preload-rel-3", "node_ids": ["node-a"], "assets": []},
        )
        self.assertEqual(second.status_code, 200, second.text)

        record = await main_mod.registry.get("node-a")
        assert record is not None
        self.assertGreaterEqual(len(record.pending_commands), 2)


if __name__ == "__main__":
    unittest.main()

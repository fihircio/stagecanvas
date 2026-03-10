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


class PlayAtPreloadGateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preload-gate.db"
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

    async def test_play_at_rejected_when_preload_not_ready(self) -> None:
        hb = await self.client.post(
            "/api/v1/nodes/node-a/heartbeat",
            json={
                "version": "v1",
                "status": "READY",
                "show_id": "show-gate",
                "position_ms": 0,
                "drift_ms": 0.0,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                "cache": {
                    "show_id": "show-gate",
                    "preload_state": "READY",
                    "asset_total": 1,
                    "cached_assets": 1,
                    "bytes_total": 1000,
                    "bytes_cached": 1000,
                },
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

        resp = await self.client.post(
            "/api/v1/shows/play_at",
            json={
                "show_id": "show-gate",
                "target_time_ms": int(time.time() * 1000) + 5_000,
                "node_ids": ["node-a", "node-b"],
                "request_id": "gate-1",
                "payload": {},
            },
        )
        self.assertEqual(resp.status_code, 409, resp.text)
        detail = resp.json()["detail"]
        self.assertEqual(detail["reason_code"], "PLAY_AT_PRELOAD_NOT_READY")
        self.assertGreaterEqual(len(detail["not_ready"]), 1)

    async def test_play_at_allowed_when_all_ready(self) -> None:
        for node_id in ("node-a", "node-b"):
            hb = await self.client.post(
                f"/api/v1/nodes/{node_id}/heartbeat",
                json={
                    "version": "v1",
                    "status": "READY",
                    "show_id": "show-gate",
                    "position_ms": 0,
                    "drift_ms": 0.0,
                    "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                    "cache": {
                        "show_id": "show-gate",
                        "preload_state": "READY",
                        "asset_total": 1,
                        "cached_assets": 1,
                        "bytes_total": 1000,
                        "bytes_cached": 1000,
                    },
                },
            )
            self.assertEqual(hb.status_code, 200, hb.text)

        resp = await self.client.post(
            "/api/v1/shows/play_at",
            json={
                "show_id": "show-gate",
                "target_time_ms": int(time.time() * 1000) + 5_000,
                "node_ids": ["node-a", "node-b"],
                "request_id": "gate-2",
                "payload": {},
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["dispatch"]["queued_count"] >= 0)


if __name__ == "__main__":
    unittest.main()

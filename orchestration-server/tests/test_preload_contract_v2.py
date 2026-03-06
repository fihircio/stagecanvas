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


class PreloadContractV2Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-preload-v2.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

        reg = await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-preload-v2", "label": "Node Preload V2", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_legacy_state_is_normalized_to_v2_and_progress_computed(self) -> None:
        hb = await self.client.post(
            "/api/v1/nodes/node-preload-v2/heartbeat",
            json={
                "version": "v1",
                "status": "READY",
                "show_id": "show-v2",
                "position_ms": 0,
                "drift_ms": 0.0,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                "cache": {
                    "show_id": "show-v2",
                    "preload_state": "PRELOADING",
                    "asset_total": 5,
                    "cached_assets": 2,
                    "bytes_total": 5000,
                    "bytes_cached": 1500,
                },
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

        nodes = await self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        cache = nodes.json()["nodes"][0]["cache"]
        self.assertEqual(cache["preload_state"], "LOADING")
        self.assertEqual(cache["progress_assets_pct"], 40.0)
        self.assertEqual(cache["progress_bytes_pct"], 30.0)

    async def test_ready_state_without_totals_defaults_to_100_percent(self) -> None:
        hb = await self.client.post(
            "/api/v1/nodes/node-preload-v2/heartbeat",
            json={
                "version": "v1",
                "status": "READY",
                "show_id": "show-v2",
                "position_ms": 0,
                "drift_ms": 0.0,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
                "cache": {
                    "show_id": "show-v2",
                    "preload_state": "READY",
                    "asset_total": 0,
                    "cached_assets": 0,
                    "bytes_total": 0,
                    "bytes_cached": 0,
                },
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

        nodes = await self.client.get("/api/v1/nodes")
        cache = nodes.json()["nodes"][0]["cache"]
        self.assertEqual(cache["preload_state"], "READY")
        self.assertEqual(cache["progress_assets_pct"], 100.0)
        self.assertEqual(cache["progress_bytes_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()

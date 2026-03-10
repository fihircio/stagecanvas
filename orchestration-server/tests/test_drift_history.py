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
from app.config import DRIFT_HISTORY_MAXLEN
from app.registry import NodeRegistry


class DriftHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-drift-history.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

        reg = await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-drift", "label": "Node Drift", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def _heartbeat(self, drift_ms: float) -> None:
        hb = await self.client.post(
            "/api/v1/nodes/node-drift/heartbeat",
            json={
                "version": "v1",
                "status": "PLAYING",
                "show_id": "demo-show",
                "position_ms": 1000,
                "drift_ms": drift_ms,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 20.0, "fps": 59.9, "dropped_frames": 0},
            },
        )
        self.assertEqual(hb.status_code, 200, hb.text)

    async def test_drift_history_ring_buffer_caps(self) -> None:
        for _ in range(DRIFT_HISTORY_MAXLEN + 10):
            await self._heartbeat(0.5)

        history = await self.client.get("/api/v1/nodes/node-drift/drift_history")
        self.assertEqual(history.status_code, 200, history.text)
        items = history.json()["history"]
        self.assertEqual(len(items), DRIFT_HISTORY_MAXLEN)


if __name__ == "__main__":
    unittest.main()

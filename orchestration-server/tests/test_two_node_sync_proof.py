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


class TwoNodeSyncProofTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-sync.db"
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

    async def test_two_nodes_receive_same_play_at_and_stay_within_slo(self) -> None:
        target_time_ms = int(time.time() * 1000) + 5_000
        response = await self.client.post(
            "/api/v1/shows/play_at",
            json={
                "show_id": "demo-show",
                "target_time_ms": target_time_ms,
                "node_ids": ["node-a", "node-b"],
                "request_id": "sync-proof-r1",
                "payload": {},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        dispatch = response.json()["dispatch"]
        self.assertEqual(dispatch["queued_count"], 2)

        record_a = await main_mod.registry.get("node-a")
        record_b = await main_mod.registry.get("node-b")
        self.assertIsNotNone(record_a)
        self.assertIsNotNone(record_b)
        assert record_a is not None and record_b is not None
        self.assertEqual(len(record_a.pending_commands), 1)
        self.assertEqual(len(record_b.pending_commands), 1)
        cmd_a = record_a.pending_commands[0]
        cmd_b = record_b.pending_commands[0]

        # Deterministic proof: both nodes receive identical scheduled target and seq.
        self.assertEqual(cmd_a["command"], "PLAY_AT")
        self.assertEqual(cmd_b["command"], "PLAY_AT")
        self.assertEqual(cmd_a["target_time_ms"], target_time_ms)
        self.assertEqual(cmd_b["target_time_ms"], target_time_ms)
        self.assertEqual(cmd_a["seq"], cmd_b["seq"])

        # Simulate post-start drift for both nodes staying inside SLO OK (<2ms).
        for node_id, drift_ms in (("node-a", 1.1), ("node-b", -1.4)):
            hb = await self.client.post(
                f"/api/v1/nodes/{node_id}/heartbeat",
                json={
                    "version": "v1",
                    "status": "PLAYING",
                    "show_id": "demo-show",
                    "position_ms": 12_000,
                    "drift_ms": drift_ms,
                    "metrics": {"cpu_pct": 18.0, "gpu_pct": 26.0, "fps": 59.8, "dropped_frames": 0},
                },
            )
            self.assertEqual(hb.status_code, 200, hb.text)

        slo = await self.client.get("/api/v1/slo")
        self.assertEqual(slo.status_code, 200, slo.text)
        drift = slo.json()["drift_slo"]
        self.assertEqual(drift["warn"], 0)
        self.assertEqual(drift["critical"], 0)
        self.assertLess(drift["max_abs_drift_ms"], drift["warn_ms"])


if __name__ == "__main__":
    unittest.main()

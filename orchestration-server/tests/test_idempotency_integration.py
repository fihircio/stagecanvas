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


class OrchestrationIdempotencyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-test.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger

        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)

        transport = ASGITransport(app=main_mod.app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        reg = await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "node-a", "label": "Node A", "capabilities": {}},
        )
        self.assertEqual(reg.status_code, 200, reg.text)

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_play_at_request_id_replay_and_mismatch(self) -> None:
        request_id = "req-001"
        target_time_ms = int(time.time() * 1000) + 5_000
        ready = await self.client.post(
            "/api/v1/nodes/node-a/heartbeat",
            json={
                "version": "v1",
                "status": "READY",
                "show_id": "demo-show",
                "position_ms": 0,
                "drift_ms": 0.0,
                "metrics": {"cpu_pct": 10.0, "gpu_pct": 12.0, "fps": 60.0, "dropped_frames": 0},
                "cache": {
                    "show_id": "demo-show",
                    "preload_state": "READY",
                    "asset_total": 0,
                    "cached_assets": 0,
                    "bytes_total": 0,
                    "bytes_cached": 0,
                },
            },
        )
        self.assertEqual(ready.status_code, 200, ready.text)
        payload = {
            "show_id": "demo-show",
            "target_time_ms": target_time_ms,
            "payload": {"scene": "A"},
            "node_ids": ["node-a"],
            "request_id": request_id,
        }

        first = await self.client.post("/api/v1/shows/play_at", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        first_data = first.json()
        self.assertTrue(first_data["ok"])
        self.assertEqual(first_data["dispatch"]["queued_count"], 1)

        second = await self.client.post("/api/v1/shows/play_at", json=payload)
        self.assertEqual(second.status_code, 200, second.text)
        second_data = second.json()
        self.assertTrue(second_data["idempotent_replay"])
        self.assertEqual(second_data["reason_code"], "DUPLICATE_REQUEST")

        nodes = await self.client.get("/api/v1/nodes")
        self.assertEqual(nodes.status_code, 200, nodes.text)
        node = nodes.json()["nodes"][0]
        self.assertEqual(node["pending_commands"], 1)

        mismatch = await self.client.post(
            "/api/v1/shows/play_at",
            json={
                **payload,
                "payload": {"scene": "B"},
            },
        )
        self.assertEqual(mismatch.status_code, 409, mismatch.text)
        detail = mismatch.json()["detail"]
        self.assertEqual(detail["reason_code"], "REQUEST_ID_PAYLOAD_MISMATCH")

    async def test_sequence_is_monotonic_across_ledger_restart(self) -> None:
        first = await self.client.post(
            "/api/v1/operators/pause",
            json={"payload": {}, "node_ids": ["node-a"], "request_id": "pause-1"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        first_seq = int(first.json()["seq"])
        self.assertGreater(first_seq, 0)

        # Simulate process restart with same persistent DB path.
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)

        second = await self.client.post(
            "/api/v1/operators/stop",
            json={"payload": {}, "node_ids": ["node-a"], "request_id": "stop-1"},
        )
        self.assertEqual(second.status_code, 200, second.text)
        second_seq = int(second.json()["seq"])
        self.assertGreater(second_seq, first_seq)


if __name__ == "__main__":
    unittest.main()

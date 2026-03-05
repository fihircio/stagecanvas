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


class OperatorContractsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._ledger_path = Path(self._tmp.name) / "orchestration-contracts.db"
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path, ttl_ms=600_000)
        self.client = AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        self._tmp.cleanup()

    async def test_play_at_rejects_short_lead_time_with_reason_code(self) -> None:
        response = await self.client.post(
            "/api/v1/shows/play_at",
            json={
                "show_id": "demo-show",
                "target_time_ms": int(time.time() * 1000) + 300,
                "payload": {},
                "request_id": "short-lead",
            },
        )
        self.assertEqual(response.status_code, 422, response.text)
        detail = response.json()["detail"]
        self.assertEqual(detail["reason_code"], "PLAY_AT_LEAD_TIME_TOO_SHORT")
        self.assertIn("min_lead_ms", detail)

    async def test_broadcast_no_targets_returns_reason_code(self) -> None:
        response = await self.client.post(
            "/api/v1/commands/broadcast",
            json={"version": "v1", "command": "PING", "payload": {}, "seq": 1, "origin": "system"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["reason_code"], "NO_TARGETS")

    async def test_operator_pause_replay_returns_duplicate_request_reason(self) -> None:
        await self.client.post(
            "/api/v1/nodes/register",
            json={"node_id": "n1", "label": "Node 1", "capabilities": {}},
        )
        body = {"payload": {}, "node_ids": ["n1"], "request_id": "pause-replay"}

        first = await self.client.post("/api/v1/operators/pause", json=body)
        self.assertEqual(first.status_code, 200, first.text)

        second = await self.client.post("/api/v1/operators/pause", json=body)
        self.assertEqual(second.status_code, 200, second.text)
        payload = second.json()
        self.assertTrue(payload["idempotent_replay"])
        self.assertEqual(payload["reason_code"], "DUPLICATE_REQUEST")


if __name__ == "__main__":
    unittest.main()

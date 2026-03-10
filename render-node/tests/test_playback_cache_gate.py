from __future__ import annotations

import time
import unittest

from app.state import NodeState


class PlaybackCacheGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_play_at_fails_when_asset_missing(self) -> None:
        state = NodeState(node_id="n1", label="Node 1")
        await state.apply_command(
            "PLAY_AT",
            seq=1,
            payload={"show_id": "show-a", "required_assets": ["asset-missing"]},
            target_time_ms=int(time.time() * 1000) + 1000,
        )
        self.assertEqual(state.status, "ERROR")
        snapshot = await state.diagnostics_snapshot()
        last = snapshot["last_command"]
        self.assertEqual(last["status"], "error")
        self.assertEqual(last["reason_code"], "CACHE_MISS")

    async def test_play_at_succeeds_when_cached(self) -> None:
        state = NodeState(node_id="n2", label="Node 2")
        state.cache_index.add("asset-ok", 512, now_ms=int(time.time() * 1000))
        await state.apply_command(
            "PLAY_AT",
            seq=2,
            payload={"show_id": "show-a", "required_assets": ["asset-ok"]},
            target_time_ms=int(time.time() * 1000) + 1000,
        )
        self.assertEqual(state.status, "READY")
        self.assertIsNotNone(state.scheduled_play_time_ms)


if __name__ == "__main__":
    unittest.main()

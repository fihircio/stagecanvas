from __future__ import annotations

import time
import unittest

from app.state import NodeState


class NodeStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_or_old_seq_is_ignored(self) -> None:
        state = NodeState(node_id="n1", label="Node 1")

        await state.apply_command("LOAD_SHOW", seq=3, payload={"show_id": "show-a"}, target_time_ms=None)
        await state.apply_command("STOP", seq=3, payload={}, target_time_ms=None)

        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_seq"], 3)
        self.assertEqual(snapshot["status"], "READY")
        self.assertIsNotNone(snapshot["last_command"])
        self.assertEqual(snapshot["last_command"]["status"], "ignored")
        self.assertEqual(snapshot["command_history_size"], 2)
        self.assertEqual(snapshot["command_history_limit"], 50)

    async def test_play_at_transitions_to_playing_on_tick(self) -> None:
        state = NodeState(node_id="n2", label="Node 2")

        target = int(time.time() * 1000) - 1
        await state.apply_command(
            "PLAY_AT",
            seq=4,
            payload={"show_id": "show-sync"},
            target_time_ms=target,
        )

        self.assertEqual(state.status, "READY")
        self.assertIsNotNone(state.scheduled_play_time_ms)

        await state.tick(50)
        self.assertEqual(state.status, "PLAYING")
        self.assertIsNone(state.scheduled_play_time_ms)

    async def test_diagnostics_snapshot_includes_last_command(self) -> None:
        state = NodeState(node_id="n3", label="Node 3")

        await state.apply_command("SEEK", seq=7, payload={"position_ms": 1200}, target_time_ms=None)
        snapshot = await state.diagnostics_snapshot()

        self.assertEqual(snapshot["node_id"], "n3")
        self.assertEqual(snapshot["position_ms"], 1200)
        self.assertIsNotNone(snapshot["last_command"])
        self.assertEqual(snapshot["last_command"]["command"], "SEEK")
        self.assertEqual(snapshot["last_command"]["status"], "accepted")
        self.assertGreaterEqual(snapshot["command_history_size"], 1)

    async def test_command_history_is_capped(self) -> None:
        state = NodeState(node_id="n4", label="Node 4")

        for seq in range(1, 61):
            await state.apply_command("PING", seq=seq, payload={}, target_time_ms=None)

        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["command_history_limit"], 50)
        self.assertEqual(snapshot["command_history_size"], 50)
        self.assertEqual(snapshot["last_seq"], 60)
        self.assertEqual(snapshot["last_command"]["seq"], 60)

    async def test_preload_only_load_show_updates_cache_contract(self) -> None:
        state = NodeState(node_id="n5", label="Node 5")
        await state.apply_command(
            "LOAD_SHOW",
            seq=8,
            payload={
                "show_id": "show-preload",
                "preload_only": True,
                "request_id": "preload-r1",
                "assets": [
                    {"media_id": "m1", "size_bytes": 1024},
                    {"media_id": "m2", "size_bytes": 2048},
                ],
            },
            target_time_ms=None,
        )

        hb = await state.heartbeat_payload()
        self.assertIn("cache", hb)
        cache = hb["cache"]
        self.assertEqual(cache["show_id"], "show-preload")
        self.assertEqual(cache["preload_state"], "READY")
        self.assertEqual(cache["asset_total"], 2)
        self.assertEqual(cache["cached_assets"], 2)
        self.assertEqual(cache["bytes_total"], 3072)
        self.assertEqual(cache["bytes_cached"], 3072)
        self.assertEqual(cache["last_preload_request_id"], "preload-r1")

    async def test_transfer_only_load_show_updates_cache_contract(self) -> None:
        state = NodeState(node_id="n6", label="Node 6")
        await state.apply_command(
            "LOAD_SHOW",
            seq=9,
            payload={
                "show_id": "show-transfer",
                "transfer_only": True,
                "request_id": "transfer-r1",
                "assets": [
                    {"media_id": "m1", "size_bytes": 1500},
                    {"media_id": "m2", "size_bytes": 2500},
                ],
            },
            target_time_ms=None,
        )

        hb = await state.heartbeat_payload()
        cache = hb["cache"]
        self.assertEqual(cache["preload_state"], "READY")
        self.assertEqual(cache["asset_total"], 2)
        self.assertEqual(cache["cached_assets"], 2)
        self.assertEqual(cache["bytes_total"], 4000)
        self.assertEqual(cache["bytes_cached"], 4000)
        self.assertEqual(cache["progress_message"], "transfer")


if __name__ == "__main__":
    unittest.main()

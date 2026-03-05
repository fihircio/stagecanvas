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


if __name__ == "__main__":
    unittest.main()

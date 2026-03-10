from __future__ import annotations

import time
import unittest

from app.state import NodeState


class PlaybackStubTests(unittest.IsolatedAsyncioTestCase):
    async def test_playback_stub_emits_frames_after_play_at(self) -> None:
        state = NodeState(node_id="p1", label="Playback 1")
        target = int(time.time() * 1000) - 1
        await state.apply_command(
            "PLAY_AT",
            seq=1,
            payload={"show_id": "show-a"},
            target_time_ms=target,
        )

        await state.tick(100)
        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["status"], "PLAYING")
        self.assertGreaterEqual(snapshot["playback_frames_emitted"], 3)

    async def test_pause_and_stop_freeze_playback_stub(self) -> None:
        state = NodeState(node_id="p2", label="Playback 2")
        target = int(time.time() * 1000) - 1
        await state.apply_command(
            "PLAY_AT",
            seq=1,
            payload={"show_id": "show-a"},
            target_time_ms=target,
        )
        await state.tick(100)
        frames_before = (await state.diagnostics_snapshot())["playback_frames_emitted"]

        await state.apply_command("PAUSE", seq=2, payload={}, target_time_ms=None)
        await state.tick(100)
        frames_after_pause = (await state.diagnostics_snapshot())["playback_frames_emitted"]
        self.assertEqual(frames_before, frames_after_pause)

        await state.apply_command("STOP", seq=3, payload={}, target_time_ms=None)
        await state.tick(100)
        snapshot = await state.diagnostics_snapshot()
        self.assertEqual(snapshot["playback_frames_emitted"], 0)


if __name__ == "__main__":
    unittest.main()

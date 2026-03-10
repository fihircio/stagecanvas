from __future__ import annotations

import time
import unittest
from typing import Any

from app.bridge import Decoder
from app.state import NodeState


class RecordingDecoder(Decoder):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        self.calls.append(("load_show", {"show_id": show_id, "payload": payload}))

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        self.calls.append(("play_at", {"show_id": show_id, "target_time_ms": target_time_ms, "payload": payload}))

    async def close(self) -> None:
        return


class FailingDecoder(RecordingDecoder):
    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        raise RuntimeError("decoder_failed")


class DecoderStubTests(unittest.IsolatedAsyncioTestCase):
    async def test_decoder_called_on_load_and_play(self) -> None:
        decoder = RecordingDecoder()
        state = NodeState(node_id="n1", label="Node 1", decoder=decoder)
        await state.apply_command("LOAD_SHOW", seq=1, payload={"show_id": "show-a"}, target_time_ms=None)
        await state.apply_command(
            "PLAY_AT",
            seq=2,
            payload={"show_id": "show-a", "required_assets": []},
            target_time_ms=int(time.time() * 1000) + 1000,
        )
        self.assertEqual(decoder.calls[0][0], "load_show")
        self.assertEqual(decoder.calls[1][0], "play_at")

    async def test_decoder_failure_marks_error(self) -> None:
        decoder = FailingDecoder()
        state = NodeState(node_id="n2", label="Node 2", decoder=decoder)
        await state.apply_command(
            "PLAY_AT",
            seq=1,
            payload={"show_id": "show-b", "required_assets": []},
            target_time_ms=int(time.time() * 1000) + 1000,
        )
        self.assertEqual(state.status, "ERROR")
        snapshot = await state.diagnostics_snapshot()
        last = snapshot["last_command"]
        self.assertEqual(last["status"], "error")
        self.assertEqual(last["reason_code"], "DECODER_ERROR")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.agent import RenderNodeAgent
from app.bridge import NullRendererBridge


class RenderNodeAgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        if hasattr(self, "agent"):
            await self.agent.close()

    async def test_constructor_normalizes_intervals(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n1",
            label="Node",
            bridge=NullRendererBridge(),
            heartbeat_interval_sec=0,
            tick_interval_sec=0,
            ws_reconnect_initial_sec=0,
            ws_reconnect_max_sec=0,
        )

        self.assertGreaterEqual(self.agent.heartbeat_interval_sec, 0.1)
        self.assertGreaterEqual(self.agent.tick_interval_sec, 0.05)
        self.assertGreaterEqual(self.agent.ws_reconnect_initial_sec, 0.1)
        self.assertGreaterEqual(self.agent.ws_reconnect_max_sec, self.agent.ws_reconnect_initial_sec)

    async def test_process_ws_message_ignores_unknown_command(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n2",
            label="Node",
            bridge=NullRendererBridge(),
        )
        await self.agent.process_ws_message({"type": "COMMAND", "command": "INVALID", "seq": 1})

        snapshot = await self.agent.state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_seq"], 0)
        self.assertIn("unsupported_command", self.agent._last_ws_error or "")


if __name__ == "__main__":
    unittest.main()

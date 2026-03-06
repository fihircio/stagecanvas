from __future__ import annotations

import asyncio
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

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
        self.assertEqual(self.agent.diagnostics_sample_every, 1)
        self.assertGreaterEqual(self.agent.warn_rate_window_sec, 1.0)
        self.assertGreaterEqual(self.agent.warn_rate_burst, 1)

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

    async def test_process_ws_message_ignores_invalid_seq(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n3",
            label="Node",
            bridge=NullRendererBridge(),
        )
        await self.agent.process_ws_message({"type": "COMMAND", "command": "PING", "seq": "abc"})
        await self.agent.process_ws_message({"type": "COMMAND", "command": "PING", "seq": -1})

        snapshot = await self.agent.state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_seq"], 0)
        self.assertGreaterEqual(self.agent._command_ignored_count, 2)
        self.assertIn("command_seq", self.agent._last_ws_error or "")

    async def test_process_ws_message_applies_valid_command(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n4",
            label="Node",
            bridge=NullRendererBridge(),
        )
        await self.agent.process_ws_message({"type": "COMMAND", "command": "SEEK", "seq": 4, "payload": {"position_ms": 333}})

        snapshot = await self.agent.state.diagnostics_snapshot()
        self.assertEqual(snapshot["last_seq"], 4)
        self.assertEqual(snapshot["position_ms"], 333)
        self.assertEqual(self.agent._command_received_count, 1)

    async def test_agent_diagnostics_snapshot_exposes_counters(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n5",
            label="Node",
            bridge=NullRendererBridge(),
        )
        await self.agent.process_ws_message({"type": "COMMAND", "command": "PING", "seq": 1})
        snapshot = await self.agent.diagnostics_snapshot()

        self.assertIn("heartbeat_ok_count", snapshot)
        self.assertIn("heartbeat_error_count", snapshot)
        self.assertIn("heartbeat_consecutive_error_count", snapshot)
        self.assertIn("ws_reconnect_attempts", snapshot)
        self.assertIn("diagnostics_sample_every", snapshot)
        self.assertIn("diagnostics_emitted_count", snapshot)
        self.assertIn("diagnostics_skipped_count", snapshot)
        self.assertIn("warn_rate_window_sec", snapshot)
        self.assertIn("warn_rate_burst", snapshot)
        self.assertIn("warn_emitted_count", snapshot)
        self.assertIn("warn_suppressed_count", snapshot)
        self.assertEqual(snapshot["command_received_count"], 1)

    async def test_diagnostics_loop_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics_path = f"{tmp}/diag.jsonl"
            self.agent = RenderNodeAgent(
                base_url="http://localhost:8010",
                node_id="n6",
                label="Node",
                bridge=NullRendererBridge(),
                log_state_every_sec=0.01,
                diagnostics_file=diagnostics_path,
            )
            with patch("builtins.print"):
                task = asyncio.create_task(self.agent.diagnostics_loop())
                await asyncio.sleep(0.03)
                await self.agent.close()
                await task

            with open(diagnostics_path, "r", encoding="utf-8") as fh:
                lines = [line.strip() for line in fh.readlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 1)

    async def test_should_emit_diagnostics_sampling(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n7",
            label="Node",
            bridge=NullRendererBridge(),
            diagnostics_sample_every=3,
        )
        self.assertFalse(self.agent._should_emit_diagnostics(1))
        self.assertFalse(self.agent._should_emit_diagnostics(2))
        self.assertTrue(self.agent._should_emit_diagnostics(3))
        self.assertTrue(self.agent._should_emit_diagnostics(6))

    async def test_log_routing_stdout_vs_stderr(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n8",
            label="Node",
            bridge=NullRendererBridge(),
        )
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.agent._log("info", "hello")
            self.agent._log("warn", "oops")
            self.agent._log("error", "boom")
        self.assertIn("[render-node/info] hello", out.getvalue())
        self.assertIn("[render-node/warn] oops", err.getvalue())
        self.assertIn("[render-node/error] boom", err.getvalue())

    async def test_warn_rate_limiter_suppresses_repeated_events(self) -> None:
        self.agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="n9",
            label="Node",
            bridge=NullRendererBridge(),
            warn_rate_window_sec=10.0,
            warn_rate_burst=2,
        )
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.agent._log_warn_limited("heartbeat_failed", "heartbeat_failed node=n9", now_ms=1_000)
            self.agent._log_warn_limited("heartbeat_failed", "heartbeat_failed node=n9", now_ms=1_100)
            self.agent._log_warn_limited("heartbeat_failed", "heartbeat_failed node=n9", now_ms=1_200)
            # Move beyond window to force summary + fresh emit.
            self.agent._log_warn_limited("heartbeat_failed", "heartbeat_failed node=n9", now_ms=12_500)

        text = err.getvalue()
        self.assertEqual(text.count("heartbeat_failed node=n9"), 3)
        self.assertIn("rate_limited_summary key=heartbeat_failed suppressed=1", text)
        self.assertEqual(self.agent._warn_suppressed_count, 1)
        self.assertEqual(self.agent._warn_emitted_count, 4)


if __name__ == "__main__":
    unittest.main()

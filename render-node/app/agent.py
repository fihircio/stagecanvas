from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

import httpx
import websockets

from .bridge import MockUnityBridge, NullRendererBridge, RendererBridge
from .state import CommandType, NodeState

SUPPORTED_COMMANDS: set[str] = {"LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING"}


class RenderNodeAgent:
    def __init__(
        self,
        base_url: str,
        node_id: str,
        label: str,
        outputs: int = 1,
        bridge: RendererBridge | None = None,
        log_state_every_sec: float = 0.0,
        heartbeat_interval_sec: float = 1.0,
        tick_interval_sec: float = 0.2,
        ws_reconnect_initial_sec: float = 1.0,
        ws_reconnect_max_sec: float = 8.0,
        max_runtime_sec: float = 0.0,
        diagnostics_file: str | None = None,
        diagnostics_sample_every: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.node_id = node_id
        self.label = label
        self.outputs = outputs
        self.log_state_every_sec = max(0.0, log_state_every_sec)
        self.heartbeat_interval_sec = max(0.1, heartbeat_interval_sec)
        self.tick_interval_sec = max(0.05, tick_interval_sec)
        self.ws_reconnect_initial_sec = max(0.1, ws_reconnect_initial_sec)
        self.ws_reconnect_max_sec = max(self.ws_reconnect_initial_sec, ws_reconnect_max_sec)
        self.max_runtime_sec = max(0.0, max_runtime_sec)
        self.diagnostics_file = diagnostics_file
        self.diagnostics_sample_every = max(1, diagnostics_sample_every)
        self.bridge = bridge or NullRendererBridge()
        self.state = NodeState(node_id=node_id, label=label, bridge=self.bridge)
        self._client = httpx.AsyncClient(timeout=5.0)
        self._stop_event = asyncio.Event()
        self._ws_connected = False
        self._last_register_error: str | None = None
        self._last_heartbeat_error: str | None = None
        self._last_ws_error: str | None = None
        self._heartbeat_ok_count = 0
        self._heartbeat_error_count = 0
        self._heartbeat_consecutive_error_count = 0
        self._command_received_count = 0
        self._command_ignored_count = 0
        self._ws_reconnect_attempts = 0
        self._diagnostics_emitted_count = 0
        self._diagnostics_skipped_count = 0

    async def _sleep_or_stop(self, seconds: float) -> bool:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False

    def _log(self, level: str, message: str) -> None:
        text = f"[render-node/{level}] {message}"
        if level in {"warn", "error"}:
            print(text, file=sys.stderr)
        else:
            print(text)

    def _should_emit_diagnostics(self, tick_index: int) -> bool:
        return tick_index % self.diagnostics_sample_every == 0

    async def register(self) -> None:
        payload = {
            "node_id": self.node_id,
            "label": self.label,
            "capabilities": {
                "type": "render-node-agent",
                "outputs": self.outputs,
                "protocol_version": "v1",
            },
        }
        resp = await self._client.post(f"{self.base_url}/api/v1/nodes/register", json=payload)
        resp.raise_for_status()

    async def register_with_retry(self) -> None:
        wait_sec = 1.0
        while not self._stop_event.is_set():
            try:
                await self.register()
                self._last_register_error = None
                return
            except Exception as exc:
                self._last_register_error = str(exc)
                self._log("warn", f"register_failed node={self.node_id} error={self._last_register_error}")
                if await self._sleep_or_stop(wait_sec):
                    return
                wait_sec = min(8.0, wait_sec * 2.0)

    async def heartbeat_loop(self) -> None:
        endpoint = f"{self.base_url}/api/v1/nodes/{self.node_id}/heartbeat"
        while not self._stop_event.is_set():
            payload = await self.state.heartbeat_payload()
            try:
                resp = await self._client.post(endpoint, json=payload)
                resp.raise_for_status()
                self._last_heartbeat_error = None
                self._heartbeat_ok_count += 1
                self._heartbeat_consecutive_error_count = 0
            except Exception as exc:
                self._last_heartbeat_error = str(exc)
                self._heartbeat_error_count += 1
                self._heartbeat_consecutive_error_count += 1
                self._log("warn", f"heartbeat_failed node={self.node_id} error={self._last_heartbeat_error}")
            if await self._sleep_or_stop(self.heartbeat_interval_sec):
                return

    async def playback_loop(self) -> None:
        last = int(time.time() * 1000)
        while not self._stop_event.is_set():
            now = int(time.time() * 1000)
            await self.state.tick(max(0, now - last))
            last = now
            if await self._sleep_or_stop(self.tick_interval_sec):
                return

    async def ws_command_loop(self) -> None:
        ws_base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        uri = f"{ws_base}/ws/nodes/{self.node_id}"
        wait_sec = self.ws_reconnect_initial_sec
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(uri) as ws:
                    self._ws_connected = True
                    self._last_ws_error = None
                    wait_sec = self.ws_reconnect_initial_sec
                    self._ws_reconnect_attempts = 0
                    async for raw in ws:
                        if self._stop_event.is_set():
                            return
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            self._command_ignored_count += 1
                            self._last_ws_error = "invalid_json_frame"
                            self._log("warn", f"ws_invalid_json node={self.node_id}")
                            continue
                        await self.process_ws_message(msg)
            except Exception as exc:
                self._last_ws_error = str(exc)
                self._log("warn", f"ws_loop_error node={self.node_id} error={self._last_ws_error}")
            finally:
                self._ws_connected = False
                self._ws_reconnect_attempts += 1
                if await self._sleep_or_stop(wait_sec):
                    return
                wait_sec = min(self.ws_reconnect_max_sec, wait_sec * 2.0)

    async def process_ws_message(self, msg: dict[str, Any]) -> None:
        if msg.get("type") != "COMMAND":
            return
        command = str(msg.get("command", ""))
        if command not in SUPPORTED_COMMANDS:
            self._command_ignored_count += 1
            self._last_ws_error = f"unsupported_command:{command or 'EMPTY'}"
            self._log("warn", f"ws_unsupported_command node={self.node_id} command={command or 'EMPTY'}")
            return

        raw_seq = msg.get("seq", 0)
        try:
            seq = int(raw_seq)
        except (TypeError, ValueError):
            self._command_ignored_count += 1
            self._last_ws_error = "invalid_command_seq"
            self._log("warn", f"ws_invalid_seq node={self.node_id} seq={raw_seq!r}")
            return
        if seq < 0:
            self._command_ignored_count += 1
            self._last_ws_error = "negative_command_seq"
            self._log("warn", f"ws_negative_seq node={self.node_id} seq={seq}")
            return

        self._command_received_count += 1
        await self.state.apply_command(
            command=cast(CommandType, command),
            seq=seq,
            payload=cast(dict[str, Any] | None, msg.get("payload")),
            target_time_ms=cast(int | None, msg.get("target_time_ms")),
        )

    async def diagnostics_snapshot(self) -> dict[str, Any]:
        snapshot = await self.state.diagnostics_snapshot()
        snapshot["ws_connected"] = self._ws_connected
        snapshot["last_register_error"] = self._last_register_error
        snapshot["last_heartbeat_error"] = self._last_heartbeat_error
        snapshot["last_ws_error"] = self._last_ws_error
        snapshot["heartbeat_ok_count"] = self._heartbeat_ok_count
        snapshot["heartbeat_error_count"] = self._heartbeat_error_count
        snapshot["heartbeat_consecutive_error_count"] = self._heartbeat_consecutive_error_count
        snapshot["command_received_count"] = self._command_received_count
        snapshot["command_ignored_count"] = self._command_ignored_count
        snapshot["ws_reconnect_attempts"] = self._ws_reconnect_attempts
        snapshot["diagnostics_sample_every"] = self.diagnostics_sample_every
        snapshot["diagnostics_emitted_count"] = self._diagnostics_emitted_count
        snapshot["diagnostics_skipped_count"] = self._diagnostics_skipped_count
        return snapshot

    async def diagnostics_loop(self) -> None:
        if self.log_state_every_sec <= 0:
            while not self._stop_event.is_set():
                await self._sleep_or_stop(3600)
            return
        tick_index = 0
        while not self._stop_event.is_set():
            tick_index += 1
            if not self._should_emit_diagnostics(tick_index):
                self._diagnostics_skipped_count += 1
                if await self._sleep_or_stop(self.log_state_every_sec):
                    return
                continue

            snapshot = await self.diagnostics_snapshot()
            line = json.dumps(snapshot, separators=(",", ":"))
            self._log("info", line)
            self._diagnostics_emitted_count += 1
            if self.diagnostics_file:
                path = Path(self.diagnostics_file)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(f"{line}\n")
            if await self._sleep_or_stop(self.log_state_every_sec):
                return

    async def run(self) -> None:
        await self.bridge.connect(self.node_id, self.label)
        await self.register_with_retry()
        if self._stop_event.is_set():
            return

        tasks = [
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.playback_loop()),
            asyncio.create_task(self.ws_command_loop()),
            asyncio.create_task(self.diagnostics_loop()),
        ]
        try:
            if self.max_runtime_sec > 0:
                await self._sleep_or_stop(self.max_runtime_sec)
                self._stop_event.set()
            await asyncio.gather(*tasks)
        finally:
            self._stop_event.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        self._stop_event.set()
        await self._client.aclose()
        await self.bridge.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="StageCanvas render-node agent")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--node-id", default="render-node-1")
    parser.add_argument("--label", default="Render Node 1")
    parser.add_argument("--outputs", type=int, default=1)
    parser.add_argument("--bridge", choices=["null", "mock-unity"], default="null")
    parser.add_argument(
        "--log-state-every-sec",
        type=float,
        default=0.0,
        help="Print render-node diagnostics JSON at interval; 0 disables periodic logs.",
    )
    parser.add_argument("--heartbeat-interval-sec", type=float, default=1.0)
    parser.add_argument("--tick-interval-sec", type=float, default=0.2)
    parser.add_argument("--ws-reconnect-initial-sec", type=float, default=1.0)
    parser.add_argument("--ws-reconnect-max-sec", type=float, default=8.0)
    parser.add_argument(
        "--max-runtime-sec",
        type=float,
        default=0.0,
        help="Optional auto-stop runtime budget for smoke tests; 0 runs until interrupted.",
    )
    parser.add_argument(
        "--diagnostics-file",
        default=None,
        help="Optional path to append diagnostics JSONL snapshots.",
    )
    parser.add_argument(
        "--diagnostics-sample-every",
        type=int,
        default=1,
        help="Emit one diagnostics sample every N intervals (N>=1).",
    )
    args = parser.parse_args()

    bridge: RendererBridge
    if args.bridge == "mock-unity":
        bridge = MockUnityBridge()
    else:
        bridge = NullRendererBridge()

    agent = RenderNodeAgent(
        base_url=args.base_url,
        node_id=args.node_id,
        label=args.label,
        outputs=args.outputs,
        bridge=bridge,
        log_state_every_sec=args.log_state_every_sec,
        heartbeat_interval_sec=args.heartbeat_interval_sec,
        tick_interval_sec=args.tick_interval_sec,
        ws_reconnect_initial_sec=args.ws_reconnect_initial_sec,
        ws_reconnect_max_sec=args.ws_reconnect_max_sec,
        max_runtime_sec=args.max_runtime_sec,
        diagnostics_file=args.diagnostics_file,
        diagnostics_sample_every=args.diagnostics_sample_every,
    )
    try:
        await agent.run()
    finally:
        await agent.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

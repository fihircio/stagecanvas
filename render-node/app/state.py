from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from .bridge import NullRendererBridge, RendererBridge

NodeStatus = Literal["IDLE", "LOADING", "READY", "PLAYING", "PAUSED", "ERROR"]
CommandType = Literal["LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING"]


@dataclass
class NodeState:
    node_id: str
    label: str
    show_id: str | None = "demo-show"
    status: NodeStatus = "READY"
    position_ms: int = 0
    drift_ms: float = 0.0
    dropped_frames: int = 0
    cpu_pct: float = 18.0
    gpu_pct: float = 26.0
    fps: float = 60.0
    last_seq: int = 0
    scheduled_play_time_ms: int | None = None
    cache_show_id: str | None = None
    cache_preload_state: Literal["IDLE", "PRELOADING", "READY", "ERROR"] = "IDLE"
    cache_asset_total: int = 0
    cache_cached_assets: int = 0
    cache_bytes_total: int = 0
    cache_bytes_cached: int = 0
    cache_last_preload_request_id: str | None = None
    bridge: RendererBridge = field(default_factory=NullRendererBridge)
    command_history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def apply_command(
        self,
        command: CommandType,
        seq: int,
        payload: dict[str, Any] | None,
        target_time_ms: int | None,
    ) -> None:
        payload = payload or {}
        bridge_call: tuple[str, dict[str, Any]] | None = None
        history = {
            "at_ms": int(time.time() * 1000),
            "seq": seq,
            "command": command,
            "status": "accepted",
            "detail": "",
        }
        async with self._lock:
            if seq <= self.last_seq:
                history["status"] = "ignored"
                history["detail"] = f"duplicate_or_old_seq(last={self.last_seq})"
                self.command_history.append(history)
                return
            self.last_seq = seq

            if command == "LOAD_SHOW":
                self.show_id = str(payload.get("show_id", self.show_id or "demo-show"))
                bridge_call = ("load_show", {"show_id": self.show_id, "payload": payload})
                if bool(payload.get("preload_only", False)):
                    assets = payload.get("assets", [])
                    if not isinstance(assets, list):
                        assets = []
                    total_bytes = 0
                    for asset in assets:
                        if isinstance(asset, dict):
                            size = asset.get("size_bytes", 0)
                            if isinstance(size, (int, float)):
                                total_bytes += max(0, int(size))
                    self.cache_show_id = self.show_id
                    self.cache_preload_state = "PRELOADING"
                    self.cache_asset_total = len(assets)
                    self.cache_cached_assets = len(assets)
                    self.cache_bytes_total = total_bytes
                    self.cache_bytes_cached = total_bytes
                    self.cache_last_preload_request_id = (
                        str(payload["request_id"]) if payload.get("request_id") is not None else None
                    )
                    self.cache_preload_state = "READY"
                    history["detail"] = "preloaded"
                else:
                    self.status = "LOADING"
                    self.status = "READY"
                    self.position_ms = 0
                    self.scheduled_play_time_ms = None
            elif command == "PLAY_AT":
                self.show_id = str(payload.get("show_id", self.show_id or "demo-show"))
                if target_time_ms is not None:
                    self.scheduled_play_time_ms = target_time_ms
                else:
                    self.status = "PLAYING"
                    self.scheduled_play_time_ms = None
                bridge_call = (
                    "play_at",
                    {"show_id": self.show_id, "target_time_ms": target_time_ms, "payload": payload},
                )
            elif command == "PAUSE":
                self.status = "PAUSED"
                self.scheduled_play_time_ms = None
                bridge_call = ("pause", {})
            elif command == "SEEK":
                self.position_ms = int(payload.get("position_ms", self.position_ms))
                bridge_call = ("seek", {"position_ms": self.position_ms})
            elif command == "STOP":
                self.status = "READY"
                self.position_ms = 0
                self.scheduled_play_time_ms = None
                bridge_call = ("stop", {})
            elif command == "PING":
                bridge_call = ("ping", {})

        if bridge_call is None:
            return

        try:
            name, args = bridge_call
            if name == "load_show":
                await self.bridge.load_show(args["show_id"], args["payload"])
            elif name == "play_at":
                await self.bridge.play_at(args["show_id"], args["target_time_ms"], args["payload"])
            elif name == "pause":
                await self.bridge.pause()
            elif name == "seek":
                await self.bridge.seek(args["position_ms"])
            elif name == "stop":
                await self.bridge.stop()
            elif name == "ping":
                await self.bridge.ping()
            history["detail"] = "applied"
        except Exception as exc:
            history["status"] = "error"
            history["detail"] = str(exc)[:200]
            async with self._lock:
                self.status = "ERROR"
        finally:
            async with self._lock:
                self.command_history.append(history)

    async def tick(self, dt_ms: int) -> None:
        now = int(time.time() * 1000)
        snapshot: dict[str, Any] | None = None
        async with self._lock:
            if self.scheduled_play_time_ms is not None and now >= self.scheduled_play_time_ms:
                self.status = "PLAYING"
                self.scheduled_play_time_ms = None

            if self.status == "PLAYING":
                self.position_ms += dt_ms
                self.fps = 59.7
                self.cpu_pct = min(65.0, self.cpu_pct + 0.8)
                self.gpu_pct = min(88.0, self.gpu_pct + 0.9)
                self.drift_ms = ((now % 7) - 3) * 0.4
            elif self.status == "PAUSED":
                self.fps = 0.0
                self.cpu_pct = max(14.0, self.cpu_pct - 0.5)
                self.gpu_pct = max(18.0, self.gpu_pct - 0.6)
                self.drift_ms = 0.0
            else:
                self.fps = 58.8 if self.status == "READY" else 0.0
                self.cpu_pct = max(10.0, self.cpu_pct - 0.3)
                self.gpu_pct = max(14.0, self.gpu_pct - 0.4)
                self.drift_ms = 0.0
            snapshot = {
                "status": self.status,
                "show_id": self.show_id,
                "position_ms": self.position_ms,
                "drift_ms": self.drift_ms,
            }

        if snapshot is not None:
            await self.bridge.tick(snapshot)

    async def heartbeat_payload(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "version": "v1",
                "status": self.status,
                "show_id": self.show_id,
                "position_ms": self.position_ms,
                "drift_ms": self.drift_ms,
                "metrics": {
                    "cpu_pct": self.cpu_pct,
                    "gpu_pct": self.gpu_pct,
                    "fps": self.fps,
                    "dropped_frames": self.dropped_frames,
                },
                "cache": {
                    "show_id": self.cache_show_id,
                    "preload_state": self.cache_preload_state,
                    "asset_total": self.cache_asset_total,
                    "cached_assets": self.cache_cached_assets,
                    "bytes_total": self.cache_bytes_total,
                    "bytes_cached": self.cache_bytes_cached,
                    "last_preload_request_id": self.cache_last_preload_request_id,
                },
            }

    async def diagnostics_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "node_id": self.node_id,
                "status": self.status,
                "show_id": self.show_id,
                "position_ms": self.position_ms,
                "drift_ms": self.drift_ms,
                "last_seq": self.last_seq,
                "scheduled_play_time_ms": self.scheduled_play_time_ms,
                "metrics": {
                    "cpu_pct": self.cpu_pct,
                    "gpu_pct": self.gpu_pct,
                    "fps": self.fps,
                    "dropped_frames": self.dropped_frames,
                },
                "command_history_size": len(self.command_history),
                "command_history_limit": self.command_history.maxlen,
                "last_command": self.command_history[-1] if self.command_history else None,
                "cache": {
                    "show_id": self.cache_show_id,
                    "preload_state": self.cache_preload_state,
                    "asset_total": self.cache_asset_total,
                    "cached_assets": self.cache_cached_assets,
                    "bytes_total": self.cache_bytes_total,
                    "bytes_cached": self.cache_bytes_cached,
                    "last_preload_request_id": self.cache_last_preload_request_id,
                },
            }

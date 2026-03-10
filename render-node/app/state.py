from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .bridge import Decoder, NullDecoder, NullRendererBridge, RendererBridge

NodeStatus = Literal["IDLE", "LOADING", "READY", "PLAYING", "PAUSED", "ERROR"]
CommandType = Literal["LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING", "UPDATE_LAYERS"]


@dataclass
class CacheAssetEntry:
    asset_id: str
    size_bytes: int
    last_access_ms: int


@dataclass
class CacheIndex:
    max_bytes: int = 500_000_000
    _entries: OrderedDict[str, CacheAssetEntry] = field(default_factory=OrderedDict)
    _current_bytes: int = 0

    @property
    def current_bytes(self) -> int:
        return self._current_bytes

    def list_assets(self) -> list[CacheAssetEntry]:
        return list(self._entries.values())

    def touch(self, asset_id: str, now_ms: int) -> bool:
        entry = self._entries.get(asset_id)
        if entry is None:
            return False
        entry.last_access_ms = now_ms
        self._entries.move_to_end(asset_id)
        return True

    def add(self, asset_id: str, size_bytes: int, now_ms: int) -> list[CacheAssetEntry]:
        size_bytes = max(0, int(size_bytes))
        entry = self._entries.get(asset_id)
        if entry is None:
            entry = CacheAssetEntry(asset_id=asset_id, size_bytes=size_bytes, last_access_ms=now_ms)
            self._entries[asset_id] = entry
            self._current_bytes += size_bytes
        else:
            self._current_bytes -= entry.size_bytes
            entry.size_bytes = size_bytes
            entry.last_access_ms = now_ms
            self._current_bytes += size_bytes
            self._entries.move_to_end(asset_id)
        return self._evict_if_needed()

    def remove(self, asset_id: str) -> CacheAssetEntry | None:
        entry = self._entries.pop(asset_id, None)
        if entry is not None:
            self._current_bytes -= entry.size_bytes
        return entry

    def _evict_if_needed(self) -> list[CacheAssetEntry]:
        evicted: list[CacheAssetEntry] = []
        while self._current_bytes > self.max_bytes and self._entries:
            _, entry = self._entries.popitem(last=False)
            self._current_bytes -= entry.size_bytes
            evicted.append(entry)
        return evicted

    def to_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "asset_id": entry.asset_id,
                "size_bytes": entry.size_bytes,
                "last_access_ms": entry.last_access_ms,
            }
            for entry in self._entries.values()
        ]

    @classmethod
    def from_payload(cls, payload: list[dict[str, Any]], max_bytes: int) -> "CacheIndex":
        cache = cls(max_bytes=max_bytes)
        for item in payload:
            asset_id = str(item.get("asset_id", ""))
            if not asset_id:
                continue
            size_bytes = int(item.get("size_bytes", 0))
            last_access_ms = int(item.get("last_access_ms", 0))
            cache._entries[asset_id] = CacheAssetEntry(
                asset_id=asset_id,
                size_bytes=size_bytes,
                last_access_ms=last_access_ms,
            )
            cache._current_bytes += size_bytes
        return cache


@dataclass
class NodeState:
    node_id: str
    label: str
    show_id: str | None = "demo-show"
    status: NodeStatus = "READY"
    position_ms: float = 0.0
    drift_ms: float = 0.0
    dropped_frames: int = 0
    cpu_pct: float = 18.0
    gpu_pct: float = 26.0
    fps: float = 60.0
    last_seq: int = 0
    scheduled_play_time_ms: float | None = None
    cache_show_id: str | None = None
    cache_preload_state: Literal["EMPTY", "LOADING", "READY", "FAILED"] = "EMPTY"
    cache_asset_total: int = 0
    cache_cached_assets: int = 0
    cache_bytes_total: int = 0
    cache_bytes_cached: int = 0
    cache_progress_assets_pct: float = 0.0
    cache_progress_bytes_pct: float = 0.0
    cache_progress_message: str | None = None
    cache_last_preload_request_id: str | None = None
    cache_index: CacheIndex = field(default_factory=CacheIndex)
    cache_index_path: Path | None = None
    mapping_config: dict[str, Any] | None = None
    playback_frame_interval_ms: int = 33
    playback_accumulator_ms: int = 0
    playback_frames_emitted: int = 0
    playback_started_ms: int | None = None
    bridge: RendererBridge = field(default_factory=NullRendererBridge)
    decoder: Decoder = field(default_factory=NullDecoder)
    command_history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        if self.cache_index_path is None:
            self.cache_index_path = Path(__file__).resolve().parent.parent / "data" / f"cache-{self.node_id}.json"
        self._load_cache_index()

    def _persist_cache_index(self) -> None:
        if self.cache_index_path is None:
            return
        self.cache_index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.cache_index.to_payload()
        tmp_path = self.cache_index_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(self.cache_index_path)

    def _load_cache_index(self) -> None:
        if self.cache_index_path is None or not self.cache_index_path.exists():
            return
        raw = json.loads(self.cache_index_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return
        self.cache_index = CacheIndex.from_payload(raw, max_bytes=self.cache_index.max_bytes)

    def cache_contains(self, asset_id: str) -> bool:
        return self.cache_index.touch(asset_id, now_ms=int(time.time() * 1000))

    async def apply_command(
        self,
        command: CommandType,
        seq: int,
        payload: dict[str, Any] | None,
        target_time_ms: int | None,
    ) -> None:
        payload = payload or {}
        bridge_call: tuple[str, dict[str, Any]] | None = None
        decoder_call: tuple[str, dict[str, Any]] | None = None
        history = {
            "at_ms": int(time.time() * 1000),
            "seq": seq,
            "command": command,
            "status": "accepted",
            "detail": "",
            "reason_code": None,
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
                decoder_call = ("load_show", {"show_id": self.show_id, "payload": payload})
                mapping_config = payload.get("mapping_config")
                if isinstance(mapping_config, dict):
                    self.mapping_config = mapping_config
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
                            media_id = asset.get("media_id")
                            if isinstance(media_id, str) and media_id:
                                self.cache_index.add(media_id, int(size or 0), now_ms=history["at_ms"])
                    self.cache_show_id = self.show_id
                    self.cache_preload_state = "LOADING"
                    self.cache_asset_total = len(assets)
                    self.cache_cached_assets = len(assets)
                    self.cache_bytes_total = total_bytes
                    self.cache_bytes_cached = total_bytes
                    self.cache_progress_assets_pct = 100.0 if assets else 0.0
                    self.cache_progress_bytes_pct = 100.0 if total_bytes > 0 else 0.0
                    self.cache_progress_message = "preload"
                    self.cache_last_preload_request_id = (
                        str(payload["request_id"]) if payload.get("request_id") is not None else None
                    )
                    self.cache_preload_state = "READY"
                    self._persist_cache_index()
                    history["detail"] = "preloaded"
                elif bool(payload.get("transfer_only", False)):
                    assets = payload.get("assets", [])
                    if not isinstance(assets, list):
                        assets = []
                    total_bytes = 0
                    for asset in assets:
                        if isinstance(asset, dict):
                            size = asset.get("size_bytes", 0)
                            if isinstance(size, (int, float)):
                                total_bytes += max(0, int(size))
                            media_id = asset.get("media_id")
                            if isinstance(media_id, str) and media_id:
                                self.cache_index.add(media_id, int(size or 0), now_ms=history["at_ms"])
                    self.cache_show_id = self.show_id
                    self.cache_preload_state = "LOADING"
                    self.cache_asset_total = len(assets)
                    self.cache_cached_assets = 0
                    self.cache_bytes_total = total_bytes
                    self.cache_bytes_cached = 0
                    self.cache_progress_assets_pct = 0.0
                    self.cache_progress_bytes_pct = 0.0
                    self.cache_progress_message = "transfer"
                    self.cache_last_preload_request_id = (
                        str(payload["request_id"]) if payload.get("request_id") is not None else None
                    )
                    self.cache_cached_assets = len(assets)
                    self.cache_bytes_cached = total_bytes
                    self.cache_progress_assets_pct = 100.0 if assets else 0.0
                    self.cache_progress_bytes_pct = 100.0 if total_bytes > 0 else 0.0
                    self.cache_preload_state = "READY"
                    self._persist_cache_index()
                    history["detail"] = "transfer"
                else:
                    self.status = "LOADING"
                    self.status = "READY"
                    self.position_ms = 0
                    self.scheduled_play_time_ms = None
                    self.playback_frames_emitted = 0
                    self.playback_accumulator_ms = 0
                    self.playback_started_ms = None
            elif command == "PLAY_AT":
                self.show_id = str(payload.get("show_id", self.show_id or "demo-show"))
                required_assets = payload.get("required_assets") or payload.get("assets")
                missing: list[str] = []
                if isinstance(required_assets, list):
                    for asset in required_assets:
                        media_id = None
                        if isinstance(asset, str):
                            media_id = asset
                        elif isinstance(asset, dict):
                            media_id = asset.get("media_id")
                        if isinstance(media_id, str) and media_id:
                            if not self.cache_contains(media_id):
                                missing.append(media_id)
                if missing:
                    history["status"] = "error"
                    history["reason_code"] = "CACHE_MISS"
                    history["detail"] = f"missing_assets:{','.join(missing)}"
                    self.status = "ERROR"
                    self.command_history.append(history)
                    return
                if target_time_ms is not None:
                    self.scheduled_play_time_ms = target_time_ms
                else:
                    self.status = "PLAYING"
                    self.scheduled_play_time_ms = None
                bridge_call = (
                    "play_at",
                    {"show_id": self.show_id, "target_time_ms": target_time_ms, "payload": payload},
                )
                decoder_call = (
                    "play_at",
                    {"show_id": self.show_id, "target_time_ms": target_time_ms, "payload": payload},
                )
            elif command == "PAUSE":
                self.status = "PAUSED"
                self.scheduled_play_time_ms = None
                self.playback_started_ms = None
                bridge_call = ("pause", {})
            elif command == "SEEK":
                self.position_ms = float(payload.get("position_ms", self.position_ms))
                bridge_call = ("seek", {"position_ms": int(self.position_ms)})
            elif command == "STOP":
                self.status = "READY"
                self.position_ms = 0
                self.scheduled_play_time_ms = None
                self.playback_frames_emitted = 0
                self.playback_accumulator_ms = 0
                self.playback_started_ms = None
                bridge_call = ("stop", {})
            elif command == "PING":
                bridge_call = ("ping", {})
            elif command == "UPDATE_LAYERS":
                bridge_call = ("update_layers", {"layers": payload.get("layers", [])})

        if bridge_call is None:
            return

        try:
            decoder_failed = False
            if decoder_call is not None:
                try:
                    name, args = decoder_call
                    if name == "load_show":
                        await self.decoder.load_show(args["show_id"], args["payload"])
                    elif name == "play_at":
                        await self.decoder.play_at(args["show_id"], args["target_time_ms"], args["payload"])
                except Exception:
                    decoder_failed = True
                    raise
            if self.mapping_config is not None:
                await self.bridge.set_mapping(self.mapping_config)
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
            if history["reason_code"] is None:
                history["reason_code"] = "DECODER_ERROR" if decoder_failed else "BRIDGE_ERROR"
            history["detail"] = str(exc)[:200]
            async with self._lock:
                self.status = "ERROR"
        finally:
            async with self._lock:
                self.command_history.append(history)

    async def tick(self, dt_ms: float) -> None:
        now_ms = time.time() * 1000
        async with self._lock:
            if self.scheduled_play_time_ms is not None and now_ms >= self.scheduled_play_time_ms:
                self.status = "PLAYING"
                self.scheduled_play_time_ms = None

            if self.status == "PLAYING":
                self.position_ms += dt_ms
                self.fps = 59.7
                self.cpu_pct = min(65.0, self.cpu_pct + 0.8)
                self.gpu_pct = min(88.0, self.gpu_pct + 0.9)
                # Drift relative to system clock if we were supposed to start at scheduled_play_time_ms
                if self.playback_started_ms is not None:
                    expected_position = now_ms - self.playback_started_ms
                    self.drift_ms = self.position_ms - expected_position
                else:
                    self.playback_started_ms = now_ms
                    self.drift_ms = 0.0

                self.playback_accumulator_ms += int(dt_ms)
                while self.playback_accumulator_ms >= self.playback_frame_interval_ms:
                    self.playback_frames_emitted += 1
                    self.playback_accumulator_ms -= self.playback_frame_interval_ms
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
                    "progress_assets_pct": self.cache_progress_assets_pct,
                    "progress_bytes_pct": self.cache_progress_bytes_pct,
                    "progress_message": self.cache_progress_message,
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
                    "progress_assets_pct": self.cache_progress_assets_pct,
                    "progress_bytes_pct": self.cache_progress_bytes_pct,
                    "progress_message": self.cache_progress_message,
                    "last_preload_request_id": self.cache_last_preload_request_id,
                },
                "playback_frames_emitted": self.playback_frames_emitted,
                "playback_started_ms": self.playback_started_ms,
            }

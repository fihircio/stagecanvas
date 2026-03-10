from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import WebSocket

from .config import (
    DRIFT_CRITICAL_MS,
    DRIFT_HISTORY_MAXLEN,
    DRIFT_SUSTAINED_CRITICAL_SAMPLES,
    DRIFT_SUSTAINED_WARN_SAMPLES,
    DRIFT_WARN_MS,
)
from .models import ControlCommand, HeartbeatRequest, NodeStatus, RegisterNodeRequest

DriftLevel = Literal["OK", "WARN", "CRITICAL"]


@dataclass
class NodeRecord:
    node_id: str
    label: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    status: NodeStatus = "IDLE"
    protocol_version: str = "v1"
    show_id: str | None = None
    position_ms: int = 0
    drift_ms: float = 0.0
    drift_level: DriftLevel = "OK"
    drift_alert_level: DriftLevel = "OK"
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "cpu_pct": 0.0,
            "gpu_pct": 0.0,
            "fps": 0.0,
            "dropped_frames": 0,
        }
    )
    last_seen_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    connected: bool = False
    command_seq: int = 0
    pending_commands: list[dict[str, Any]] = field(default_factory=list)
    replay_count: int = 0
    queued_count: int = 0
    reconnect_count: int = 0
    ws_connect_count: int = 0
    drift_history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=DRIFT_HISTORY_MAXLEN))
    sustained_warn_samples: int = 0
    sustained_critical_samples: int = 0
    cache: dict[str, Any] = field(
        default_factory=lambda: {
            "show_id": None,
            "preload_state": "EMPTY",
            "asset_total": 0,
            "cached_assets": 0,
            "bytes_total": 0,
            "bytes_cached": 0,
            "progress_assets_pct": 0.0,
            "progress_bytes_pct": 0.0,
            "progress_message": None,
            "last_preload_request_id": None,
        }
    )
    ws: WebSocket | None = None


class NodeRegistry:
    def __init__(self) -> None:
        self._nodes: dict[str, NodeRecord] = {}
        self._lock = asyncio.Lock()

    async def register(self, body: RegisterNodeRequest) -> NodeRecord:
        async with self._lock:
            existing = self._nodes.get(body.node_id)
            if existing:
                existing.label = body.label or existing.label
                existing.capabilities.update(body.capabilities)
                existing.last_seen_ms = int(time.time() * 1000)
                return existing

            record = NodeRecord(
                node_id=body.node_id,
                label=body.label,
                capabilities=body.capabilities,
            )
            self._nodes[body.node_id] = record
            return record

    async def heartbeat(self, node_id: str, hb: HeartbeatRequest) -> NodeRecord | None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return None
            record.status = hb.status
            record.protocol_version = hb.version
            record.metrics = hb.metrics.model_dump()
            record.position_ms = hb.position_ms
            record.drift_ms = hb.drift_ms
            record.drift_level = self.classify_drift_level(record.drift_ms)
            record.drift_history.append(
                {
                    "timestamp_ms": int(time.time() * 1000),
                    "drift_ms": record.drift_ms,
                    "drift_level": record.drift_level,
                }
            )
            if record.drift_level == "CRITICAL":
                record.sustained_critical_samples += 1
                record.sustained_warn_samples = 0
            elif record.drift_level == "WARN":
                record.sustained_warn_samples += 1
                record.sustained_critical_samples = 0
            else:
                record.sustained_warn_samples = 0
                record.sustained_critical_samples = 0

            if record.sustained_critical_samples >= DRIFT_SUSTAINED_CRITICAL_SAMPLES:
                record.drift_alert_level = "CRITICAL"
            elif record.sustained_warn_samples >= DRIFT_SUSTAINED_WARN_SAMPLES:
                record.drift_alert_level = "WARN"
            else:
                record.drift_alert_level = "OK"
            record.show_id = hb.show_id
            if hb.cache is not None:
                record.cache = self.normalize_cache(hb.cache.model_dump(mode="json"))
            record.last_seen_ms = int(time.time() * 1000)
            return record

    async def set_connection(self, node_id: str, ws: WebSocket) -> NodeRecord | None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return None
            record.ws = ws
            record.connected = True
            record.ws_connect_count += 1
            if record.ws_connect_count > 1:
                record.reconnect_count += 1
            record.last_seen_ms = int(time.time() * 1000)
            return record

    async def clear_connection(self, node_id: str) -> None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return
            record.connected = False
            record.ws = None
            record.last_seen_ms = int(time.time() * 1000)

    async def list_nodes(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [self._public_node_view(r) for r in self._nodes.values()]

    async def get(self, node_id: str) -> NodeRecord | None:
        async with self._lock:
            return self._nodes.get(node_id)

    async def get_drift_history(self, node_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return []
            return list(record.drift_history)

    async def enqueue_command(
        self,
        node_id: str,
        cmd: ControlCommand,
    ) -> tuple[NodeRecord | None, dict[str, Any] | None, str]:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return None, None, "NOT_REGISTERED"
            if cmd.seq <= record.command_seq:
                record.replay_count += 1
                return record, None, "DUPLICATE_OR_STALE_SEQ"
            envelope = {
                "type": "COMMAND",
                "version": cmd.version,
                "node_id": node_id,
                "timestamp_ms": int(time.time() * 1000),
                "message_id": f"{node_id}:{cmd.seq}:{int(time.time()*1000)}",
                "command": cmd.command,
                "payload": cmd.payload,
                "target_time_ms": cmd.target_time_ms,
                "seq": cmd.seq,
                "origin": cmd.origin,
            }
            record.command_seq = max(record.command_seq, cmd.seq)
            record.pending_commands.append(envelope)
            record.queued_count += 1
            return record, envelope, "QUEUED"

    async def dequeue_pending(self, node_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return []
            pending = list(record.pending_commands)
            record.pending_commands.clear()
            return pending

    async def active_node_ids(self) -> list[str]:
        async with self._lock:
            return list(self._nodes.keys())

    async def drift_summary(self) -> dict[str, Any]:
        async with self._lock:
            ok = 0
            warn = 0
            critical = 0
            max_abs_drift_ms = 0.0
            for record in self._nodes.values():
                max_abs_drift_ms = max(max_abs_drift_ms, abs(record.drift_ms))
                drift_level = self.classify_drift_level(record.drift_ms)
                if drift_level == "CRITICAL":
                    critical += 1
                elif drift_level == "WARN":
                    warn += 1
                else:
                    ok += 1
            return {
                "ok": ok,
                "warn": warn,
                "critical": critical,
                "max_abs_drift_ms": max_abs_drift_ms,
                "warn_ms": DRIFT_WARN_MS,
                "critical_ms": DRIFT_CRITICAL_MS,
            }

    def _public_node_view(self, record: NodeRecord) -> dict[str, Any]:
        drift_level = self.classify_drift_level(record.drift_ms)
        return {
            "node_id": record.node_id,
            "label": record.label,
            "connected": record.connected,
            "status": record.status,
            "protocol_version": record.protocol_version,
            "show_id": record.show_id,
            "position_ms": record.position_ms,
            "drift_ms": record.drift_ms,
            "drift_level": drift_level,
            "drift_alert_level": record.drift_alert_level,
            "drift_alert_active": record.drift_alert_level != "OK",
            "metrics": record.metrics,
            "last_seen_ms": record.last_seen_ms,
            "capabilities": record.capabilities,
            "command_seq": record.command_seq,
            "pending_commands": len(record.pending_commands),
            "queue_depth": len(record.pending_commands),
            "replay_count": record.replay_count,
            "queued_count": record.queued_count,
            "reconnect_count": record.reconnect_count,
            "cache": record.cache,
            "drift_history_summary": self._drift_history_summary(record),
        }

    @staticmethod
    def _drift_history_summary(record: NodeRecord) -> dict[str, Any]:
        history = list(record.drift_history)
        if not history:
            return {
                "sample_count": 0,
                "window_ms": 0,
                "avg_abs_drift_ms": 0.0,
                "max_abs_drift_ms": 0.0,
                "warn_samples": 0,
                "critical_samples": 0,
                "last_drift_ms": record.drift_ms,
                "last_level": record.drift_level,
                "last_timestamp_ms": record.last_seen_ms,
            }

        first_ts = int(history[0]["timestamp_ms"])
        last = history[-1]
        last_ts = int(last["timestamp_ms"])
        window_ms = max(0, last_ts - first_ts)

        abs_values: list[float] = []
        warn_samples = 0
        critical_samples = 0
        for entry in history:
            drift_ms = float(entry.get("drift_ms", 0.0))
            abs_values.append(abs(drift_ms))
            level = entry.get("drift_level")
            if level == "CRITICAL":
                critical_samples += 1
            elif level == "WARN":
                warn_samples += 1

        avg_abs = sum(abs_values) / len(abs_values)
        max_abs = max(abs_values) if abs_values else 0.0

        return {
            "sample_count": len(history),
            "window_ms": window_ms,
            "avg_abs_drift_ms": round(avg_abs, 3),
            "max_abs_drift_ms": round(max_abs, 3),
            "warn_samples": warn_samples,
            "critical_samples": critical_samples,
            "last_drift_ms": float(last.get("drift_ms", 0.0)),
            "last_level": last.get("drift_level", record.drift_level),
            "last_timestamp_ms": last_ts,
        }

    @staticmethod
    def classify_drift_level(drift_ms: float) -> DriftLevel:
        abs_drift = abs(drift_ms)
        if abs_drift >= DRIFT_CRITICAL_MS:
            return "CRITICAL"
        if abs_drift >= DRIFT_WARN_MS:
            return "WARN"
        return "OK"

    @staticmethod
    def normalize_cache(raw: dict[str, Any]) -> dict[str, Any]:
        legacy_state = str(raw.get("preload_state", "EMPTY"))
        state_map = {
            "IDLE": "EMPTY",
            "PRELOADING": "LOADING",
            "ERROR": "FAILED",
        }
        preload_state = state_map.get(legacy_state, legacy_state)
        if preload_state not in {"EMPTY", "LOADING", "READY", "FAILED"}:
            preload_state = "FAILED"

        asset_total = max(0, int(raw.get("asset_total", 0)))
        cached_assets = max(0, int(raw.get("cached_assets", 0)))
        bytes_total = max(0, int(raw.get("bytes_total", 0)))
        bytes_cached = max(0, int(raw.get("bytes_cached", 0)))

        def pct(done: int, total: int, fallback_state: str) -> float:
            if total > 0:
                return max(0.0, min(100.0, (done / total) * 100.0))
            if fallback_state == "READY":
                return 100.0
            if fallback_state == "EMPTY":
                return 0.0
            return 0.0

        progress_assets_pct = raw.get("progress_assets_pct")
        if progress_assets_pct is None:
            progress_assets_pct = pct(cached_assets, asset_total, preload_state)
        progress_bytes_pct = raw.get("progress_bytes_pct")
        if progress_bytes_pct is None:
            progress_bytes_pct = pct(bytes_cached, bytes_total, preload_state)

        return {
            "show_id": raw.get("show_id"),
            "preload_state": preload_state,
            "asset_total": asset_total,
            "cached_assets": cached_assets,
            "bytes_total": bytes_total,
            "bytes_cached": bytes_cached,
            "progress_assets_pct": round(float(progress_assets_pct), 1),
            "progress_bytes_pct": round(float(progress_bytes_pct), 1),
            "progress_message": raw.get("progress_message"),
            "last_preload_request_id": raw.get("last_preload_request_id"),
        }

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import WebSocket

from .config import DRIFT_CRITICAL_MS, DRIFT_WARN_MS
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
            record.drift_level = self._drift_level(record.drift_ms)
            record.show_id = hb.show_id
            record.last_seen_ms = int(time.time() * 1000)
            return record

    async def set_connection(self, node_id: str, ws: WebSocket) -> NodeRecord | None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return None
            record.ws = ws
            record.connected = True
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
                if record.drift_level == "CRITICAL":
                    critical += 1
                elif record.drift_level == "WARN":
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
        return {
            "node_id": record.node_id,
            "label": record.label,
            "connected": record.connected,
            "status": record.status,
            "protocol_version": record.protocol_version,
            "show_id": record.show_id,
            "position_ms": record.position_ms,
            "drift_ms": record.drift_ms,
            "drift_level": record.drift_level,
            "metrics": record.metrics,
            "last_seen_ms": record.last_seen_ms,
            "capabilities": record.capabilities,
            "command_seq": record.command_seq,
            "pending_commands": len(record.pending_commands),
        }

    def _drift_level(self, drift_ms: float) -> DriftLevel:
        abs_drift = abs(drift_ms)
        if abs_drift >= DRIFT_CRITICAL_MS:
            return "CRITICAL"
        if abs_drift >= DRIFT_WARN_MS:
            return "WARN"
        return "OK"

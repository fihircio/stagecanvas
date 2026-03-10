from __future__ import annotations

import asyncio
import json
import time
import shutil
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import WebSocket

from .config import (
    DRIFT_CRITICAL_MS,
    DRIFT_HISTORY_MAXLEN,
    DRIFT_SUSTAINED_CRITICAL_SAMPLES,
    DRIFT_SUSTAINED_WARN_SAMPLES,
    DRIFT_WARN_MS,
)
from .models import (
    ControlCommand,
    HeartbeatRequest,
    MediaAssetCreateRequest,
    MediaAssetResponse,
    MediaAssetUpdateRequest,
    TranscodeJobResponse,
    NodeStatus,
    RegisterNodeRequest,
)

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
    transfer_queue_depth: int = 0
    transfer_worker_state: str = "IDLE"
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

    async def update_transfer_queue_depth(self, node_id: str, depth: int) -> None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return
            record.transfer_queue_depth = max(0, depth)

    async def update_transfer_state(
        self,
        node_id: str,
        cached_assets: int,
        cached_bytes: int,
        state: str,
        message: str | None,
    ) -> None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return
            record.cache = {
                **record.cache,
                "cached_assets": max(0, cached_assets),
                "bytes_cached": max(0, cached_bytes),
                "preload_state": state,
                "progress_assets_pct": record.cache.get("progress_assets_pct"),
                "progress_bytes_pct": record.cache.get("progress_bytes_pct"),
                "progress_message": message,
            }

    async def update_transfer_worker_state(self, node_id: str, state: str) -> None:
        async with self._lock:
            record = self._nodes.get(node_id)
            if record is None:
                return
            record.transfer_worker_state = state

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
            "transfer_queue_depth": record.transfer_queue_depth,
            "transfer_worker_state": record.transfer_worker_state,
            "cache": record.cache,
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


@dataclass
class MediaAssetRecord:
    asset_id: str
    label: str | None
    codec_profile: str
    duration_ms: int
    size_bytes: int
    checksum: str | None = None
    uri: str | None = None
    status: str = "REGISTERED"
    error_message: str | None = None
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_response(self) -> MediaAssetResponse:
        return MediaAssetResponse(
            asset_id=self.asset_id,
            label=self.label,
            codec_profile=self.codec_profile,
            duration_ms=self.duration_ms,
            size_bytes=self.size_bytes,
            checksum=self.checksum,
            uri=self.uri,
            status=self.status,
            error_message=self.error_message,
            created_at_ms=self.created_at_ms,
            updated_at_ms=self.updated_at_ms,
        )


class MediaRegistry:
    def __init__(self, storage_path: Path | None = None) -> None:
        self._assets: dict[str, MediaAssetRecord] = {}
        self._lock = asyncio.Lock()
        self._storage_path = storage_path
        if self._storage_path is not None:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    async def register(self, body: MediaAssetCreateRequest) -> tuple[MediaAssetRecord, bool, bool]:
        async with self._lock:
            existing = self._assets.get(body.asset_id)
            if existing is not None:
                idempotent = (
                    existing.label == body.label
                    and existing.codec_profile == body.codec_profile
                    and existing.duration_ms == body.duration_ms
                    and existing.size_bytes == body.size_bytes
                    and existing.checksum == body.checksum
                    and existing.uri == body.uri
                )
                return existing, False, idempotent

            record = MediaAssetRecord(
                asset_id=body.asset_id,
                label=body.label,
                codec_profile=body.codec_profile,
                duration_ms=body.duration_ms,
                size_bytes=body.size_bytes,
                checksum=body.checksum,
                uri=body.uri,
                status=body.status,
            )
            self._assets[body.asset_id] = record
            self._persist()
            return record, True, True

    async def list_assets(self) -> list[MediaAssetResponse]:
        async with self._lock:
            return [asset.to_response() for asset in self._assets.values()]

    async def get(self, asset_id: str) -> MediaAssetRecord | None:
        async with self._lock:
            return self._assets.get(asset_id)

    async def update(self, asset_id: str, body: MediaAssetUpdateRequest) -> MediaAssetRecord | None:
        async with self._lock:
            record = self._assets.get(asset_id)
            if record is None:
                return None
            if body.status is not None:
                record.status = body.status
            if body.error_message is not None:
                record.error_message = body.error_message
            if body.checksum is not None:
                record.checksum = body.checksum
            if body.uri is not None:
                record.uri = body.uri
            record.updated_at_ms = int(time.time() * 1000)
            self._persist()
            return record

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        payload = [asset.to_response().model_dump(mode="json") for asset in self._assets.values()]
        tmp_path = self._storage_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(self._storage_path)

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            record = MediaAssetRecord(
                asset_id=str(item.get("asset_id", "")),
                label=item.get("label"),
                codec_profile=str(item.get("codec_profile", "")),
                duration_ms=int(item.get("duration_ms", 0)),
                size_bytes=int(item.get("size_bytes", 0)),
                checksum=item.get("checksum"),
                uri=item.get("uri"),
                status=str(item.get("status", "REGISTERED")),
                error_message=item.get("error_message"),
                created_at_ms=int(item.get("created_at_ms", int(time.time() * 1000))),
                updated_at_ms=int(item.get("updated_at_ms", int(time.time() * 1000))),
            )
            if record.asset_id:
                self._assets[record.asset_id] = record


@dataclass
class TranscodeJobRecord:
    job_id: str
    asset_id: str
    target_profile: str
    status: str = "QUEUED"
    error_message: str | None = None
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_response(self) -> TranscodeJobResponse:
        return TranscodeJobResponse(
            job_id=self.job_id,
            asset_id=self.asset_id,
            target_profile=self.target_profile,
            status=self.status,
            error_message=self.error_message,
            created_at_ms=self.created_at_ms,
            updated_at_ms=self.updated_at_ms,
        )


class TranscodeQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, TranscodeJobRecord] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, asset_id: str, target_profile: str) -> TranscodeJobRecord:
        async with self._lock:
            job_id = str(uuid.uuid4())
            record = TranscodeJobRecord(job_id=job_id, asset_id=asset_id, target_profile=target_profile)
            self._jobs[job_id] = record
            return record

    async def get(self, job_id: str) -> TranscodeJobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def list_jobs(self) -> list[TranscodeJobResponse]:
        async with self._lock:
            return [job.to_response() for job in self._jobs.values()]

    async def update(self, job_id: str, status: str | None, error_message: str | None) -> TranscodeJobRecord | None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            if status is not None:
                record.status = status
            if error_message is not None:
                record.error_message = error_message
            record.updated_at_ms = int(time.time() * 1000)
            return record


@dataclass
class TransferTask:
    node_id: str
    show_id: str
    media_id: str
    size_bytes: int
    attempt: int = 0
    max_retries: int = 3
    backoff_ms: int = 200
    next_run_ms: int = field(default_factory=lambda: int(time.time() * 1000))


class AssetTransferWorker:
    def __init__(
        self,
        registry: NodeRegistry,
        media_registry: MediaRegistry | None = None,
        media_root: Path | None = None,
        cache_root: Path | None = None,
        handler: Callable[[TransferTask], bool] | None = None,
    ) -> None:
        self._registry = registry
        self._media_registry = media_registry
        self._media_root = media_root
        self._cache_root = cache_root
        self._handler = handler
        self._queue: list[TransferTask] = []

    def enqueue(self, task: TransferTask) -> None:
        self._queue.append(task)

    def pending_count(self) -> int:
        return len(self._queue)

    async def run_once(self, now_ms: int | None = None) -> bool:
        if not self._queue:
            return False
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        task = next((t for t in self._queue if t.next_run_ms <= now), None)
        if task is None:
            return False

        await self._registry.update_transfer_worker_state(task.node_id, "RUNNING")
        if self._handler is not None:
            success = self._handler(task)
        else:
            success = await self._copy_media_asset(task)
        if success:
            self._queue.remove(task)
            await self._registry.update_transfer_queue_depth(task.node_id, self.pending_count())
            record = await self._registry.get(task.node_id)
            if record is not None:
                cached_assets = int(record.cache.get("cached_assets", 0)) + 1
                cached_bytes = int(record.cache.get("bytes_cached", 0)) + task.size_bytes
                total_assets = int(record.cache.get("asset_total", 0))
                total_bytes = int(record.cache.get("bytes_total", 0))
                state = "READY" if cached_assets >= total_assets else "LOADING"
                await self._registry.update_transfer_state(
                    task.node_id,
                    cached_assets=cached_assets,
                    cached_bytes=cached_bytes,
                    state=state,
                    message="transfer",
                )
        else:
            task.attempt += 1
            if task.attempt > task.max_retries:
                self._queue.remove(task)
                await self._registry.update_transfer_queue_depth(task.node_id, self.pending_count())
                await self._registry.update_transfer_state(
                    task.node_id,
                    cached_assets=0,
                    cached_bytes=0,
                    state="FAILED",
                    message="transfer_failed",
                )
            else:
                backoff = task.backoff_ms * (2 ** (task.attempt - 1))
                task.next_run_ms = now + backoff
        await self._registry.update_transfer_worker_state(task.node_id, "IDLE")
        return True

    async def _copy_media_asset(self, task: TransferTask) -> bool:
        if self._media_registry is None or self._media_root is None or self._cache_root is None:
            return True
        record = await self._media_registry.get(task.media_id)
        if record is None:
            return False
        source = self._resolve_media_path(record)
        if source is None or not source.exists():
            return False
        dest_dir = self._cache_root / task.node_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        shutil.copy2(source, dest)
        if task.size_bytes <= 0:
            task.size_bytes = dest.stat().st_size
        return True

    def _resolve_media_path(self, record: MediaAssetRecord) -> Path | None:
        if record.uri:
            if record.uri.startswith("file://"):
                return Path(record.uri[7:])
            return Path(record.uri)
        if self._media_root is None:
            return None
        return self._media_root / record.asset_id

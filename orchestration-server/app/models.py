from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .config import PROTOCOL_VERSION

NodeStatus = Literal["IDLE", "LOADING", "READY", "PLAYING", "PAUSED", "ERROR"]
CommandType = Literal["LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING"]
ProtocolVersion = Literal["v1"]


class RegisterNodeRequest(BaseModel):
    node_id: str = Field(min_length=1)
    label: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)


class NodeMetrics(BaseModel):
    cpu_pct: float
    gpu_pct: float
    fps: float
    dropped_frames: int = Field(ge=0)


class HeartbeatRequest(BaseModel):
    version: ProtocolVersion = PROTOCOL_VERSION
    status: NodeStatus
    metrics: NodeMetrics
    position_ms: int = Field(default=0, ge=0)
    drift_ms: float = 0.0
    show_id: str | None = None
    cache: "NodeCacheStatus | None" = None


class ControlCommand(BaseModel):
    version: ProtocolVersion = PROTOCOL_VERSION
    command: CommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    target_time_ms: int | None = Field(default=None, ge=0)
    seq: int = Field(ge=0)
    origin: Literal["operator", "scheduler", "system"] = "operator"


class SchedulePlayAtRequest(BaseModel):
    show_id: str = Field(min_length=1)
    target_time_ms: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    node_ids: list[str] = Field(default_factory=list)
    request_id: str | None = None


class OperatorCommandRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    node_ids: list[str] = Field(default_factory=list)
    request_id: str | None = None


class PreloadAsset(BaseModel):
    media_id: str = Field(min_length=1)
    uri: str | None = None
    checksum: str | None = None
    size_bytes: int = Field(default=0, ge=0)


class PreloadShowRequest(BaseModel):
    show_id: str = Field(min_length=1)
    assets: list[PreloadAsset] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    request_id: str | None = None


class NodeCacheStatus(BaseModel):
    show_id: str | None = None
    preload_state: Literal["IDLE", "PRELOADING", "READY", "ERROR"] = "IDLE"
    asset_total: int = Field(default=0, ge=0)
    cached_assets: int = Field(default=0, ge=0)
    bytes_total: int = Field(default=0, ge=0)
    bytes_cached: int = Field(default=0, ge=0)
    last_preload_request_id: str | None = None


class TimelineClip(BaseModel):
    clip_id: str
    label: str
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"


class TimelineTrack(BaseModel):
    track_id: str
    label: str
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    clips: list[TimelineClip] = Field(default_factory=list)


class TimelineSnapshotResponse(BaseModel):
    show_id: str
    duration_ms: int = Field(gt=0)
    playhead_ms: int = Field(ge=0)
    tracks: list[TimelineTrack] = Field(default_factory=list)


class TimelineShowSummary(BaseModel):
    show_id: str
    duration_ms: int = Field(gt=0)
    track_count: int = Field(ge=0)


class TimelineUpsertShowRequest(BaseModel):
    duration_ms: int = Field(gt=0)


class TimelineUpsertTrackRequest(BaseModel):
    label: str = Field(min_length=1)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    position: int | None = Field(default=None, ge=0)


class TimelineUpsertClipRequest(BaseModel):
    label: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    position: int | None = Field(default=None, ge=0)

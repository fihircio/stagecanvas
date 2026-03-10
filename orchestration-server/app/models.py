from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .config import PROTOCOL_VERSION

NodeStatus = Literal["IDLE", "LOADING", "READY", "PLAYING", "PAUSED", "ERROR"]
CommandType = Literal["LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING"]
ProtocolVersion = Literal["v1"]
MediaAssetStatus = Literal["REGISTERED", "INGESTING", "READY", "FAILED"]


class MappingBlend(BaseModel):
    gamma: float = Field(default=1.0, ge=0.0)
    brightness: float = Field(default=1.0, ge=0.0)
    black_level: float = Field(default=0.0, ge=0.0)


class MappingMesh(BaseModel):
    vertices: list[float] = Field(min_length=6)
    uvs: list[float] = Field(min_length=6)
    indices: list[int] = Field(min_length=3)

    @classmethod
    def _validate_pairs(cls, values: list[float], name: str) -> list[float]:
        if len(values) % 2 != 0:
            raise ValueError(f"{name} must contain an even number of floats")
        return values

    @classmethod
    def _validate_tris(cls, values: list[int]) -> list[int]:
        if len(values) % 3 != 0:
            raise ValueError("indices must contain a multiple of 3 entries")
        return values

    @model_validator(mode="after")
    def _validate_model(self) -> "MappingMesh":
        self.vertices = self._validate_pairs(self.vertices, "vertices")
        self.uvs = self._validate_pairs(self.uvs, "uvs")
        if len(self.uvs) != len(self.vertices):
            raise ValueError("uvs length must match vertices length")
        self.indices = self._validate_tris(self.indices)
        return self


class MappingOutput(BaseModel):
    output_id: str = Field(min_length=1)
    mesh: MappingMesh
    blend: MappingBlend = Field(default_factory=MappingBlend)


class MappingConfig(BaseModel):
    version: Literal["v1"] = "v1"
    outputs: list[MappingOutput] = Field(min_length=1)


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


class AssetTransferRequest(BaseModel):
    show_id: str = Field(min_length=1)
    assets: list[PreloadAsset] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    request_id: str | None = None


class NodeCacheStatus(BaseModel):
    show_id: str | None = None
    preload_state: Literal["EMPTY", "LOADING", "READY", "FAILED", "IDLE", "PRELOADING", "ERROR"] = "EMPTY"
    asset_total: int = Field(default=0, ge=0)
    cached_assets: int = Field(default=0, ge=0)
    bytes_total: int = Field(default=0, ge=0)
    bytes_cached: int = Field(default=0, ge=0)
    progress_assets_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    progress_bytes_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    progress_message: str | None = None
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
    mapping_config: MappingConfig | None = None


class MediaAssetMetadata(BaseModel):
    codec_profile: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    size_bytes: int = Field(ge=0)


class MediaAssetCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    label: str | None = None
    codec_profile: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    checksum: str | None = None
    uri: str | None = None
    status: MediaAssetStatus = "REGISTERED"


class MediaAssetUpdateRequest(BaseModel):
    status: MediaAssetStatus | None = None
    error_message: str | None = None
    checksum: str | None = None
    uri: str | None = None


class MediaAssetResponse(BaseModel):
    asset_id: str
    label: str | None
    codec_profile: str
    duration_ms: int
    size_bytes: int
    checksum: str | None
    uri: str | None
    status: MediaAssetStatus
    error_message: str | None
    created_at_ms: int
    updated_at_ms: int


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

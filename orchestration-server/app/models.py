from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .config import PROTOCOL_VERSION

NodeStatus = Literal["IDLE", "LOADING", "READY", "PLAYING", "PAUSED", "ERROR"]
CommandType = Literal["LOAD_SHOW", "PLAY_AT", "PAUSE", "SEEK", "STOP", "PING", "UPDATE_LAYERS", "HOT_SWAP", "PLAY_CLIP"]
ProtocolVersion = Literal["v1"]
TimeSyncSource = Literal["system", "ntp", "ptp"]
MediaAssetStatus = Literal["REGISTERED", "INGESTING", "READY", "FAILED", "MISSING"]
TranscodeJobStatus = Literal["QUEUED", "RUNNING", "DONE", "FAILED"]
SUPPORTED_CODEC_PROFILES: dict[str, str] = {
    "HAP": "HAP",
    "HAP-Q": "HAP-Q",
    "PRORES4444": "ProRes4444",
    "H264": "H264",
    "H265": "H265",
}


class MappingBlend(BaseModel):
    gamma: float = Field(default=1.0, ge=0.0)
    brightness: float = Field(default=1.0, ge=0.0)
    black_level: float = Field(default=0.0, ge=0.0)


class CanvasRegion(BaseModel):
    global_x: int = 0
    global_y: int = 0
    width: int = 1920
    height: int = 1080


class TimelineLayerTransform(BaseModel):
    x: float = 0.0
    y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


class TimelineLayer(BaseModel):
    layer_id: str
    label: str
    asset_id: str | None = None
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    blend_mode: Literal["normal", "add", "multiply", "screen"] = "normal"
    transform: TimelineLayerTransform = Field(default_factory=TimelineLayerTransform)


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
    target_node_id: str | None = None
    mesh: MappingMesh
    blend: MappingBlend = Field(default_factory=MappingBlend)
    canvas_region: CanvasRegion = Field(default_factory=CanvasRegion)


class MappingConfig(BaseModel):
    version: Literal["v1"] = "v1"
    outputs: list[MappingOutput] = Field(min_length=1)
    fixture_profiles: list[dict[str, Any]] = Field(default_factory=list)


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
    time_sync_source: TimeSyncSource = "system"
    time_sync_offset_ms: float = 0.0
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
    offset_ms: int = Field(default=0, ge=0)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    layers: list[TimelineLayer] = Field(default_factory=list)


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
    mapping_config: MappingConfig | None = None


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

    @field_validator("codec_profile")
    @classmethod
    def _validate_codec_profile(cls, value: str) -> str:
        return _normalize_codec_profile(value)


class MediaAssetCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    label: str | None = None
    codec_profile: str = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    checksum: str | None = None
    uri: str | None = None
    status: MediaAssetStatus = "REGISTERED"

    @field_validator("codec_profile")
    @classmethod
    def _validate_codec_profile(cls, value: str) -> str:
        return _normalize_codec_profile(value)


class MediaAssetUpdateRequest(BaseModel):
    status: MediaAssetStatus | None = None
    error_message: str | None = None
    checksum: str | None = None
    uri: str | None = None


def _normalize_codec_profile(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("UNSUPPORTED_CODEC_PROFILE")
    key = raw.upper().replace("_", "-").replace(" ", "-")
    if key == "H264-MAIN":
        return raw
    if key in SUPPORTED_CODEC_PROFILES:
        return raw
    raise ValueError("UNSUPPORTED_CODEC_PROFILE")


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


class TranscodeJobCreateRequest(BaseModel):
    target_profile: str = Field(min_length=1)


class TranscodeJobUpdateRequest(BaseModel):
    status: TranscodeJobStatus | None = None
    error_message: str | None = None


class TranscodeJobResponse(BaseModel):
    job_id: str
    asset_id: str
    target_profile: str
    status: TranscodeJobStatus
    progress: float = 0.0
    error_message: str | None
    created_at_ms: int
    updated_at_ms: int


# ---------------------------------------------------------------------------
# SC-112 — Visual Scripting Logic
# ---------------------------------------------------------------------------

class LogicConfig(BaseModel):
    """Configuration for stateful logic nodes in a trigger chain."""
    delay_ms: int | None = Field(default=None, description="Delay before execution")
    counter_target: int | None = Field(default=None, description="Number of hits before firing")
    condition: str | None = Field(default=None, description="Restricted eval condition (e.g. payload.x > 0.5)")

class TriggerRule(BaseModel):
    rule_id: str = Field(min_length=1)
    name: str | None = None
    source: Literal["osc", "http"] = "osc"
    cue_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    logic: LogicConfig | None = None


class TriggerRegisterRequest(BaseModel):
    rule_id: str = Field(min_length=1)
    name: str | None = None
    source: Literal["osc", "http"] = "osc"
    cue_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    logic: LogicConfig | None = None


class TriggerFireRequest(BaseModel):
    rule_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class TriggerEvent(BaseModel):
    event_id: str
    rule_id: str
    source: Literal["osc", "http"] = "osc"
    cue_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp_ms: int = Field(ge=0)


class TimelineUpsertTrackRequest(BaseModel):
    label: str = Field(min_length=1)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    position: int | None = Field(default=None, ge=0)
    order: int | None = Field(default=None, ge=0)


class TimelineUpsertClipRequest(BaseModel):
    label: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    offset_ms: int | None = Field(default=None, ge=0)
    kind: Literal["video", "audio", "image", "alpha", "trigger"] = "video"
    layers: list[TimelineLayer] | None = None
    position: int | None = Field(default=None, ge=0)
    order: int | None = Field(default=None, ge=0)


class PreviewSnapshotRequest(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    show_id: str | None = None


class PreviewImageRequest(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    show_id: str | None = None
    width: int = Field(default=320, ge=1)
    height: int = Field(default=180, ge=1)
class LockRequest(BaseModel):
    resource_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# SC-100 — SMPTE LTC Timecode
# ---------------------------------------------------------------------------

class LTCStatusResponse(BaseModel):
    """Current LTC reader state."""
    mode: str = Field(description="Sync mode: chase | jam_sync | free_wheel")
    fps: float = Field(description="Active frame rate (24, 25, 29.97, 30)")
    timecode_ms: int = Field(description="Current resolved playhead position in ms")
    locked: bool = Field(description="Whether the reader has locked to a signal")
    last_frame_str: str = Field(description="Last decoded SMPTE frame string HH:MM:SS:FF")
    simulate: bool = Field(description="True when running in simulation mode (no real audio)")


class LTCSetModeRequest(BaseModel):
    """Request to change the LTC sync mode at runtime."""
    mode: Literal["chase", "jam_sync", "free_wheel"] = Field(
        description="New sync mode to apply"
    )
    fps: float | None = Field(
        default=None,
        description="Optional new frame rate. Must be one of 24 / 25 / 29.97 / 30",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"mode": "jam_sync", "fps": 25},
                {"mode": "chase"},
            ]
        }
    }


# ---------------------------------------------------------------------------
# SC-109 — System Archiving
# ---------------------------------------------------------------------------

ArchiveJobStatus = Literal["QUEUED", "RUNNING", "DONE", "FAILED"]

class ArchiveJobResponse(BaseModel):
    job_id: str
    type: Literal["export", "import"]
    status: ArchiveJobStatus
    archive_url: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# SC-113 — Enterprise RBAC & User Management
# ---------------------------------------------------------------------------

UserRole = Literal["viewer", "operator", "designer", "admin"]


class User(BaseModel):
    user_id: str
    username: str
    full_name: str | None = None
    role: UserRole = "viewer"
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None
    role: UserRole | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# SC-121 — MIDI / OSC Learning
# ---------------------------------------------------------------------------

class MappingEntry(BaseModel):
    mapping_id: str
    source_type: Literal["midi_cc", "osc"]
    source_address: str
    target_layer_id: str
    target_property: str
    min_val: float = 0.0
    max_val: float = 1.0


class LearnRequest(BaseModel):
    target_layer_id: str
    target_property: str

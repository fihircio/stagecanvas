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


class OperatorCommandRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    node_ids: list[str] = Field(default_factory=list)

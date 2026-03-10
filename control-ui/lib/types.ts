export type NodeStatus = "IDLE" | "LOADING" | "READY" | "PLAYING" | "PAUSED" | "ERROR";
export type DriftLevel = "OK" | "WARN" | "CRITICAL";

export type NodeSnapshot = {
  node_id: string;
  label: string | null;
  connected: boolean;
  status: NodeStatus;
  protocol_version: string;
  show_id: string | null;
  position_ms: number;
  drift_ms: number;
  drift_level: DriftLevel;
  drift_alert_level?: DriftLevel;
  drift_alert_active?: boolean;
  metrics: {
    cpu_pct: number;
    gpu_pct: number;
    fps: number;
    dropped_frames: number;
  };
  last_seen_ms: number;
  command_seq: number;
  pending_commands: number;
  queue_depth?: number;
  replay_count?: number;
  queued_count?: number;
  reconnect_count?: number;
  drift_history_summary?: {
    sample_count: number;
    window_ms: number;
    avg_abs_drift_ms: number;
    max_abs_drift_ms: number;
    warn_samples: number;
    critical_samples: number;
    last_drift_ms: number;
    last_level: DriftLevel;
    last_timestamp_ms: number;
  };
  cache?: {
    show_id: string | null;
    preload_state: "EMPTY" | "LOADING" | "READY" | "FAILED";
    asset_total: number;
    cached_assets: number;
    bytes_total: number;
    bytes_cached: number;
    progress_assets_pct: number;
    progress_bytes_pct: number;
    progress_message: string | null;
    last_preload_request_id: string | null;
  };
};

export type DriftSloSnapshot = {
  ok: number;
  warn: number;
  critical: number;
  max_abs_drift_ms: number;
  warn_ms: number;
  critical_ms: number;
};

export type TimelineClip = {
  clip_id: string;
  label: string;
  start_ms: number;
  duration_ms: number;
  kind: "video" | "audio" | "image" | "alpha" | "trigger";
};

export type TimelineTrack = {
  track_id: string;
  label: string;
  kind: "video" | "audio" | "image" | "alpha" | "trigger";
  clips: TimelineClip[];
};

export type TimelineSnapshot = {
  show_id: string;
  duration_ms: number;
  playhead_ms: number;
  tracks: TimelineTrack[];
};

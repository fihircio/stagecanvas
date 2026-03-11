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
    gpu_temp?: number;
    vram_mb?: number;
    fps: number;
    dropped_frames: number;
    genlock?: {
      genlock_total_hold_ms: number;
      genlock_active: boolean;
    };
  };
  last_seen_ms: number;
  command_seq: number;
  pending_commands: number;
  queue_depth?: number;
  replay_count?: number;
  queued_count?: number;
  reconnect_count?: number;
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

export type PreviewSnapshotEntry = {
  node_id: string;
  ok: boolean;
  timestamp_ms: number;
  reason_code?: string;
  status?: string;
  show_id?: string | null;
  position_ms?: number;
};

export type PreviewSnapshotResponse = {
  ok: boolean;
  requested_count: number;
  snapshots: PreviewSnapshotEntry[];
};

export type PreviewImageEntry = {
  node_id: string;
  timestamp_ms: number;
  width: number;
  height: number;
  image_data: string;
};

export type PreviewImageResponse = {
  ok: boolean;
  requested_count: number;
  images: PreviewImageEntry[];
};

export type TranscodeJobSnapshot = {
  job_id: string;
  asset_id: string;
  target_profile: string;
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED";
  progress: number;
  error_message: string | null;
  created_at_ms: number;
  updated_at_ms: number;
};

export type MediaAsset = {
  asset_id: string;
  label: string;
  codec_profile: string;
  duration_ms: number;
  size_bytes: number;
  checksum: string;
  uri: string;
  status: "REGISTERED" | "INGESTING" | "READY" | "FAILED" | "MISSING";
  metadata?: {
    codec?: string;
    width?: number;
    height?: number;
    fps?: number;
    bitrate_bps?: number;
  };
};

export type BrowserEntry = {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  mtime: number;
};

export type BrowserListResponse = {
  path: string;
  parent: string | null;
  entries: BrowserEntry[];
  error?: string;
};

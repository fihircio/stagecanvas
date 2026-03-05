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
  metrics: {
    cpu_pct: number;
    gpu_pct: number;
    fps: number;
    dropped_frames: number;
  };
  last_seen_ms: number;
  command_seq: number;
  pending_commands: number;
};

export type DriftSloSnapshot = {
  ok: number;
  warn: number;
  critical: number;
  max_abs_drift_ms: number;
  warn_ms: number;
  critical_ms: number;
};

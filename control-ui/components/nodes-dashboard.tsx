"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { DriftSloSnapshot, NodeSnapshot, TimelineSnapshot } from "../lib/types";

type OperatorSnapshotMessage = {
  type: "NODES_SNAPSHOT";
  protocol_version?: string;
  drift_slo?: DriftSloSnapshot;
  play_at_min_lead_ms?: number;
  nodes: NodeSnapshot[];
};

type SocketStatus = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";
type ActionState = "idle" | "sending" | "ok" | "error";

type CommandResult = {
  command: string;
  status: "ok" | "error";
  detail: string;
  atIso: string;
};

function statusClass(status: string): string {
  return `status-pill status-${status.toLowerCase()}`;
}

function number(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : "0.0";
}

function timecodeFromMs(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hh = String(Math.floor(total / 3600)).padStart(2, "0");
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  const ff = "00";
  return `${hh}:${mm}:${ss}:${ff}`;
}

export function NodesDashboard() {
  const [nodes, setNodes] = useState<NodeSnapshot[]>([]);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("connecting");
  const [actionState, setActionState] = useState<ActionState>("idle");
  const [lastCommand, setLastCommand] = useState<CommandResult | null>(null);
  const [showId, setShowId] = useState("demo-show");
  const [seekMs, setSeekMs] = useState("0");
  const [targetNodeId, setTargetNodeId] = useState("ALL");
  const [driftThresholdMs, setDriftThresholdMs] = useState("");
  const [protocolVersion, setProtocolVersion] = useState("v1");
  const [playAtLeadMs, setPlayAtLeadMs] = useState(1500);
  const [serverDriftSlo, setServerDriftSlo] = useState<DriftSloSnapshot | null>(null);
  const [previewTab, setPreviewTab] = useState("combined");
  const [timelineSnapshot, setTimelineSnapshot] = useState<TimelineSnapshot | null>(null);

  const wsUrl = useMemo(() => {
    const base = process.env.NEXT_PUBLIC_ORCHESTRATION_WS ?? "ws://localhost:8010/ws/operators";
    return base;
  }, []);
  const apiUrl = useMemo(() => {
    return process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP ?? "http://localhost:8010";
  }, []);

  async function postJson(path: string, body: object, command: string) {
    setActionState("sending");
    try {
      const res = await fetch(`${apiUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}${text ? `: ${text.slice(0, 160)}` : ""}`);
      }
      setActionState("ok");
      setLastCommand({
        command,
        status: "ok",
        detail: `Accepted (${res.status})`,
        atIso: new Date().toISOString(),
      });
      setTimeout(() => setActionState("idle"), 1200);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown failure";
      setActionState("error");
      setLastCommand({
        command,
        status: "error",
        detail,
        atIso: new Date().toISOString(),
      });
      setTimeout(() => setActionState("idle"), 1200);
    }
  }

  function targetNodeIds(): string[] {
    return targetNodeId === "ALL" ? [] : [targetNodeId];
  }

  function parsedDriftThreshold(): number {
    if (driftThresholdMs === "" && serverDriftSlo) {
      return serverDriftSlo.warn_ms;
    }
    const parsed = Number.parseFloat(driftThresholdMs);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 2.0;
  }

  const driftThreshold = parsedDriftThreshold();
  const driftAlertCount = nodes.filter((n) => Math.abs(n.drift_ms) > driftThreshold).length;
  const activePreviewNode =
    previewTab === "combined" ? null : nodes.find((n) => n.node_id === previewTab) ?? null;
  const globalPositionMs = activePreviewNode
    ? activePreviewNode.position_ms
    : Math.max(0, ...nodes.map((n) => n.position_ms));
  const timelineDurationMs = timelineSnapshot?.duration_ms ?? 60000;
  const timelinePlayheadMs = timelineSnapshot?.playhead_ms ?? globalPositionMs;
  const timelineTracks = timelineSnapshot?.tracks ?? [];
  const timelineMarks = [0, 0.25, 0.5, 0.75, 1];

  const onPlayAt = async () => {
    const now = Date.now();
    await postJson(
      "/api/v1/shows/play_at",
      {
        show_id: showId,
        target_time_ms: now + Math.max(3000, playAtLeadMs),
        payload: {},
        node_ids: targetNodeIds(),
      },
      "PLAY_AT",
    );
  };

  const onPause = async () => {
    await postJson("/api/v1/operators/pause", { payload: {}, node_ids: targetNodeIds() }, "PAUSE");
  };

  const onStop = async () => {
    await postJson("/api/v1/operators/stop", { payload: {}, node_ids: targetNodeIds() }, "STOP");
  };

  const onLoadShow = async () => {
    await postJson(
      "/api/v1/operators/load_show",
      {
        payload: { show_id: showId },
        node_ids: targetNodeIds(),
      },
      "LOAD_SHOW",
    );
  };

  const onSeek = async () => {
    const parsed = Number.parseInt(seekMs, 10);
    await postJson(
      "/api/v1/operators/seek",
      {
        payload: { position_ms: Number.isFinite(parsed) ? Math.max(0, parsed) : 0 },
        node_ids: targetNodeIds(),
      },
      "SEEK",
    );
  };

  useEffect(() => {
    let isActive = true;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = (isReconnect: boolean) => {
      if (!isActive) return;
      setSocketStatus(isReconnect ? "reconnecting" : "connecting");
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!isActive) return;
        setSocketStatus("connected");
      };

      ws.onmessage = (event) => {
        const raw = JSON.parse(event.data) as OperatorSnapshotMessage;
        if (raw.type === "NODES_SNAPSHOT") {
          setNodes(raw.nodes);
          if (raw.protocol_version) setProtocolVersion(raw.protocol_version);
          if (raw.play_at_min_lead_ms) setPlayAtLeadMs(raw.play_at_min_lead_ms);
          if (raw.drift_slo) setServerDriftSlo(raw.drift_slo);
        }
      };

      ws.onerror = () => {
        if (!isActive) return;
        setSocketStatus("error");
      };

      ws.onclose = () => {
        if (!isActive) return;
        setSocketStatus("disconnected");
        reconnectTimer = setTimeout(() => connect(true), 1200);
      };
    };

    connect(false);

    return () => {
      isActive = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [wsUrl]);

  const loadTimeline = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/timeline/snapshot?show_id=${encodeURIComponent(showId)}`);
      if (!res.ok) {
        return;
      }
      const data = (await res.json()) as TimelineSnapshot;
      setTimelineSnapshot(data);
    } catch {
      // ignore; timeline panel will keep prior or default rendering
    }
  }, [apiUrl, showId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (cancelled) return;
      await loadTimeline();
    }
    void load();
    const id = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [loadTimeline]);

  const onSetCue = async () => {
    const cueTrack = "triggers";
    const cueId = `cue-${Date.now()}`;
    const cueStartMs = timelinePlayheadMs;

    await postJson(`/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${cueTrack}`, {
      label: "Cue Triggers",
      kind: "trigger",
    }, "UPSERT_TRACK");
    await postJson(
      `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${cueTrack}/clips/${cueId}`,
      {
        label: `Cue @ ${timecodeFromMs(cueStartMs)}`,
        start_ms: cueStartMs,
        duration_ms: 1000,
        kind: "trigger",
      },
      "UPSERT_CLIP",
    );
    await loadTimeline();
  };

  const onSnapRefresh = async () => {
    await loadTimeline();
    setActionState("ok");
    setTimeout(() => setActionState("idle"), 800);
  };

  return (
    <div className="stage-shell">
      <header className="topbar">
        <div className="window-dots">
          <span />
          <span />
          <span />
        </div>
        <div className="topbar-title">
          StageCanvas Control
          <span className="muted">
            WS <span className={`conn-state conn-${socketStatus}`}>{socketStatus}</span> • protocol {protocolVersion}
          </span>
        </div>
      </header>

      <section className="timeline-panel">
        <div className="section-title">Timeline</div>
        <div className="timeline-ruler">
          {timelineMarks.map((mark) => (
            <span key={mark}>{timecodeFromMs(Math.floor(timelineDurationMs * mark))}</span>
          ))}
        </div>
        <div className="timeline-tracks">
          <div className="timeline-search">
            <input className="input compact" placeholder="Search cue..." />
          </div>
          <div className="timeline-lanes">
            <div className="timeline-playhead" style={{ left: `${(timelinePlayheadMs / timelineDurationMs) * 100}%` }} />
            {timelineTracks.map((track) => (
              <div className="timeline-lane" key={track.track_id}>
                <div className="track-label">{track.label}</div>
                <div className="track-canvas">
                  {track.clips.map((clip) => (
                    <div
                      className={`clip ${clip.kind === "alpha" ? "alpha" : ""}`}
                      key={clip.clip_id}
                      style={{
                        left: `${(clip.start_ms / timelineDurationMs) * 100}%`,
                        width: `${(clip.duration_ms / timelineDurationMs) * 100}%`,
                      }}
                      title={`${clip.label} (${timecodeFromMs(clip.start_ms)})`}
                    >
                      <span>{clip.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {timelineTracks.length === 0 ? <div className="empty-card muted">No timeline tracks.</div> : null}
          </div>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="media-panel">
          <div className="section-title">Media Library</div>
          <div className="media-filters">
            <button className="chip active">All</button>
            <button className="chip">Video</button>
            <button className="chip">Audio</button>
            <button className="chip">Images</button>
          </div>
          <div className="media-list">
            <div className="media-item">Video Clip 1</div>
            <div className="media-item">Video Clip 2</div>
            <div className="media-item">Audio 1</div>
            <div className="media-item">Alpha Track</div>
            <div className="media-item">Alpha Matte</div>
          </div>
        </aside>

        <main className="preview-panel">
          <div className="section-title">Preview Window</div>
          <div className="preview-tabs">
            <button
              className={`chip ${previewTab === "combined" ? "active" : ""}`}
              onClick={() => setPreviewTab("combined")}
            >
              Combined View
            </button>
            {nodes.slice(0, 2).map((node) => (
              <button
                key={node.node_id}
                className={`chip ${previewTab === node.node_id ? "active" : ""}`}
                onClick={() => setPreviewTab(node.node_id)}
              >
                {node.label || node.node_id}
              </button>
            ))}
          </div>
          <div className="preview-output">
            <div className="preview-grid-overlay">
              <strong>Program Output</strong>
              <span className="muted">
                {previewTab === "combined" ? "Combined" : activePreviewNode?.label || "Node"}
              </span>
            </div>
          </div>

          <div className="operator-row">
            <select className="input compact" value={targetNodeId} onChange={(e) => setTargetNodeId(e.target.value)}>
              <option value="ALL">All Nodes</option>
              {nodes.map((node) => (
                <option key={node.node_id} value={node.node_id}>
                  {node.label || node.node_id}
                </option>
              ))}
            </select>
            <input className="input compact" value={showId} onChange={(e) => setShowId(e.target.value)} placeholder="show_id" />
            <button className="btn" onClick={onLoadShow}>
              LOAD_SHOW
            </button>
            <input className="input compact" value={seekMs} onChange={(e) => setSeekMs(e.target.value)} placeholder="position_ms" />
            <button className="btn" onClick={onSeek}>
              SEEK
            </button>
            <input
              className="input compact"
              value={driftThresholdMs}
              onChange={(e) => setDriftThresholdMs(e.target.value)}
              placeholder={`drift warn (${serverDriftSlo?.warn_ms ?? 2.0}ms)`}
            />
          </div>
        </main>

        <aside className="node-panel">
          <div className="section-title">Node Status</div>
          <div className="status-stack">
            {nodes.map((node) => {
              const driftAlert = Math.abs(node.drift_ms) > driftThreshold;
              return (
                <article className={`node-card ${driftAlert ? "card-alert" : ""}`} key={node.node_id}>
                  <div className="node-title">
                    <strong>{node.label || node.node_id}</strong>
                    <span className={statusClass(node.status)}>{node.status}</span>
                  </div>
                  <div className="node-metrics">
                    <span>GPU {number(node.metrics.gpu_pct)}%</span>
                    <span>CPU {number(node.metrics.cpu_pct)}%</span>
                    <span>Sync {node.drift_level}</span>
                    <span>Latency {number(node.drift_ms)}ms</span>
                  </div>
                  <div className="node-actions">
                    {driftAlert ? <span className="alert-pill">DRIFT ALERT</span> : <span className="muted">Sync OK</span>}
                  </div>
                </article>
              );
            })}
            {nodes.length === 0 ? <div className="empty-card muted">No nodes registered.</div> : null}
          </div>
        </aside>
      </section>

      <footer className="transport-bar">
        <div className="transport-group">
          <strong>Transport Controls</strong>
          <div className="transport-buttons">
            <button className="btn subtle">◀◀</button>
            <button className="btn subtle">▶▶</button>
            <button className="btn" onClick={onPlayAt}>
              PLAY_AT
            </button>
            <button className="btn" onClick={onPause}>
              PAUSE
            </button>
            <button className="btn" onClick={onStop}>
              STOP
            </button>
          </div>
        </div>

        <div className="transport-time">
          {timecodeFromMs(globalPositionMs)}
          <span className="muted">
            alerts {driftAlertCount} • action {actionState}
          </span>
          <span className={`command-result ${lastCommand?.status === "error" ? "command-error" : "command-ok"}`}>
            {lastCommand
              ? `${lastCommand.command} ${lastCommand.status.toUpperCase()} • ${new Date(lastCommand.atIso).toLocaleTimeString()} • ${lastCommand.detail}`
              : "No command sent yet"}
          </span>
        </div>

        <div className="quick-actions">
          <strong>Quick Actions</strong>
          <div className="transport-buttons">
            <button className="btn subtle" onClick={onSnapRefresh}>
              Snap
            </button>
            <button className="btn subtle" onClick={onSetCue}>
              Set Cue
            </button>
            <button className="btn subtle" onClick={onSnapRefresh}>
              Sync Refresh
            </button>
            <button className="btn subtle">Settings</button>
          </div>
        </div>
      </footer>

      <div className="status-ribbon">
        <span>Drift SLO: warn {serverDriftSlo?.warn_ms ?? 2.0}ms / critical {serverDriftSlo?.critical_ms ?? 8.0}ms</span>
        <span>
          summary ok {serverDriftSlo?.ok ?? 0} / warn {serverDriftSlo?.warn ?? 0} / critical {serverDriftSlo?.critical ?? 0}
        </span>
        <span>PLAY_AT min lead {playAtLeadMs}ms</span>
      </div>
    </div>
  );
}

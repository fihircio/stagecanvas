"use client";

import { useEffect, useMemo, useState } from "react";

import type { DriftSloSnapshot, NodeSnapshot } from "../lib/types";

type OperatorSnapshotMessage = {
  type: "NODES_SNAPSHOT";
  protocol_version?: string;
  drift_slo?: DriftSloSnapshot;
  play_at_min_lead_ms?: number;
  nodes: NodeSnapshot[];
};

function statusClass(status: string): string {
  return `status-pill status-${status.toLowerCase()}`;
}

function number(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : "0.0";
}

export function NodesDashboard() {
  const [nodes, setNodes] = useState<NodeSnapshot[]>([]);
  const [socketStatus, setSocketStatus] = useState("connecting");
  const [actionState, setActionState] = useState("idle");
  const [showId, setShowId] = useState("demo-show");
  const [seekMs, setSeekMs] = useState("0");
  const [targetNodeId, setTargetNodeId] = useState("ALL");
  const [driftThresholdMs, setDriftThresholdMs] = useState("");
  const [protocolVersion, setProtocolVersion] = useState("v1");
  const [playAtLeadMs, setPlayAtLeadMs] = useState(1500);
  const [serverDriftSlo, setServerDriftSlo] = useState<DriftSloSnapshot | null>(null);

  const wsUrl = useMemo(() => {
    const base = process.env.NEXT_PUBLIC_ORCHESTRATION_WS ?? "ws://localhost:8010/ws/operators";
    return base;
  }, []);
  const apiUrl = useMemo(() => {
    return process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP ?? "http://localhost:8010";
  }, []);

  async function postJson(path: string, body: object) {
    setActionState("sending");
    try {
      const res = await fetch(`${apiUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setActionState("ok");
      setTimeout(() => setActionState("idle"), 1200);
    } catch {
      setActionState("error");
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

  const onPlayAt = async () => {
    const now = Date.now();
    await postJson("/api/v1/shows/play_at", {
      show_id: showId,
      target_time_ms: now + Math.max(3000, playAtLeadMs),
      payload: {},
      node_ids: targetNodeIds(),
    });
  };

  const onPause = async () => {
    await postJson("/api/v1/operators/pause", { payload: {}, node_ids: targetNodeIds() });
  };

  const onStop = async () => {
    await postJson("/api/v1/operators/stop", { payload: {}, node_ids: targetNodeIds() });
  };

  const onLoadShow = async () => {
    await postJson("/api/v1/operators/load_show", {
      payload: { show_id: showId },
      node_ids: targetNodeIds(),
    });
  };

  const onSeek = async () => {
    const parsed = Number.parseInt(seekMs, 10);
    await postJson("/api/v1/operators/seek", {
      payload: { position_ms: Number.isFinite(parsed) ? Math.max(0, parsed) : 0 },
      node_ids: targetNodeIds(),
    });
  };

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => setSocketStatus("connected");
    ws.onclose = () => setSocketStatus("disconnected");
    ws.onerror = () => setSocketStatus("error");
    ws.onmessage = (event) => {
      const raw = JSON.parse(event.data) as OperatorSnapshotMessage;
      if (raw.type === "NODES_SNAPSHOT") {
        setNodes(raw.nodes);
        if (raw.protocol_version) setProtocolVersion(raw.protocol_version);
        if (raw.play_at_min_lead_ms) setPlayAtLeadMs(raw.play_at_min_lead_ms);
        if (raw.drift_slo) setServerDriftSlo(raw.drift_slo);
      }
    };
    return () => ws.close();
  }, [wsUrl]);

  return (
    <div className="page">
      <div className="header">
        <div>
          <h1 style={{ margin: "0 0 6px 0" }}>StageCanvas Control</h1>
          <div className="muted">Orchestration node dashboard</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={onPlayAt}>
            PLAY_AT (+3s)
          </button>
          <button className="btn" onClick={onPause}>
            PAUSE
          </button>
          <button className="btn" onClick={onStop}>
            STOP
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <select className="input" value={targetNodeId} onChange={(e) => setTargetNodeId(e.target.value)}>
          <option value="ALL">All Nodes</option>
          {nodes.map((node) => (
            <option key={node.node_id} value={node.node_id}>
              {node.label || node.node_id}
            </option>
          ))}
        </select>
        <input
          className="input"
          value={showId}
          onChange={(e) => setShowId(e.target.value)}
          placeholder="show_id"
        />
        <button className="btn" onClick={onLoadShow}>
          LOAD_SHOW
        </button>
        <input
          className="input"
          value={seekMs}
          onChange={(e) => setSeekMs(e.target.value)}
          placeholder="position_ms"
        />
        <button className="btn" onClick={onSeek}>
          SEEK
        </button>
        <input
          className="input"
          value={driftThresholdMs}
          onChange={(e) => setDriftThresholdMs(e.target.value)}
          placeholder="drift threshold ms"
        />
      </div>

      <div className="header" style={{ marginBottom: 12 }}>
        <div className="card" style={{ padding: "8px 12px" }}>
          WS: <strong>{socketStatus}</strong>
        </div>
        <div className="card" style={{ padding: "8px 12px" }}>
          Protocol: <strong>{protocolVersion}</strong>
        </div>
        <div className="card" style={{ padding: "8px 12px" }}>
          Action: <strong>{actionState}</strong>
        </div>
        <div className={`card ${driftAlertCount > 0 ? "card-alert" : ""}`} style={{ padding: "8px 12px" }}>
          Drift Alerts: <strong>{driftAlertCount}</strong>
        </div>
        <div className="card" style={{ padding: "8px 12px" }}>
          PLAY_AT Min Lead: <strong>{playAtLeadMs}ms</strong>
        </div>
      </div>

      <div className="grid">
        {nodes.map((node) => {
          const driftAlert = Math.abs(node.drift_ms) > driftThreshold;
          return (
          <article className={`card ${driftAlert ? "card-alert" : ""}`} key={node.node_id}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div>
                <strong>{node.label || node.node_id}</strong>
                <div className="muted" style={{ fontSize: 12 }}>
                  {node.node_id}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {driftAlert ? <span className="alert-pill">DRIFT ALERT</span> : null}
                <span className={statusClass(node.status)}>{node.status}</span>
              </div>
            </div>

            <div className="kpi">
              <span className="muted">Connected</span>
              <span>{node.connected ? "yes" : "no"}</span>
              <span className="muted">Show</span>
              <span>{node.show_id ?? "-"}</span>
              <span className="muted">Drift</span>
              <span>{number(node.drift_ms)} ms</span>
              <span className="muted">FPS</span>
              <span>{number(node.metrics.fps)}</span>
              <span className="muted">Dropped</span>
              <span>{node.metrics.dropped_frames}</span>
            </div>

            <div style={{ marginTop: 8 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                CPU {number(node.metrics.cpu_pct)}%
              </div>
              <div className="bar">
                <span style={{ width: `${Math.max(0, Math.min(node.metrics.cpu_pct, 100))}%` }} />
              </div>
            </div>

            <div style={{ marginTop: 8 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                GPU {number(node.metrics.gpu_pct)}%
              </div>
              <div className="bar">
                <span style={{ width: `${Math.max(0, Math.min(node.metrics.gpu_pct, 100))}%` }} />
              </div>
            </div>
          </article>
        )})}

        {nodes.length === 0 ? <div className="card muted">No nodes registered yet.</div> : null}
      </div>
    </div>
  );
}

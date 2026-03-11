"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  DriftSloSnapshot,
  NodeSnapshot,
  PreviewImageEntry,
  PreviewImageResponse,
  TimelineSnapshot,
  TranscodeJobSnapshot,
} from "../lib/types";

type OperatorSnapshotMessage = {
  type: "NODES_SNAPSHOT";
  protocol_version?: string;
  drift_slo?: DriftSloSnapshot;
  play_at_min_lead_ms?: number;
  nodes: NodeSnapshot[];
  transcode_jobs?: TranscodeJobSnapshot[];
};

type SocketStatus = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";
type ActionState = "idle" | "sending" | "ok" | "error";

type CommandResult = {
  command: string;
  status: "ok" | "error";
  detail: string;
  atIso: string;
  requestId: string;
};

type MappingOutputForm = {
  outputId: string;
  vertices: string;
  uvs: string;
  indices: string;
  gamma: string;
  brightness: string;
  blackLevel: string;
};

type PreviewSnapshotEntry = {
  node_id: string;
  ok: boolean;
  timestamp_ms: number;
  reason_code?: string;
  status?: string;
  show_id?: string | null;
  position_ms?: number;
};

type PreviewSnapshotResponse = {
  ok: boolean;
  requested_count: number;
  snapshots: PreviewSnapshotEntry[];
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
  const [minPlayAtLeadMs, setMinPlayAtLeadMs] = useState<number>(100);
  const [transcodeJobs, setTranscodeJobs] = useState<TranscodeJobSnapshot[]>([]);
  const [previewTab, setPreviewTab] = useState("combined");
  const [timelineSnapshot, setTimelineSnapshot] = useState<TimelineSnapshot | null>(null);
  const [previewSnapshots, setPreviewSnapshots] = useState<Record<string, PreviewSnapshotEntry>>({});
  const [previewImages, setPreviewImages] = useState<Record<string, PreviewImageEntry>>({});
  const [previewStatus, setPreviewStatus] = useState<"idle" | "loading" | "error">("idle");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [dragTrackId, setDragTrackId] = useState<string | null>(null);
  const [dragClipId, setDragClipId] = useState<string | null>(null);
  const [dragClipTrackId, setDragClipTrackId] = useState<string | null>(null);
  const [mappingOutputs, setMappingOutputs] = useState<MappingOutputForm[]>([]);
  const [mappingStatus, setMappingStatus] = useState<"idle" | "saving" | "ok" | "error">("idle");
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [trackId, setTrackId] = useState("track-1");
  const [trackLabel, setTrackLabel] = useState("Track 1");
  const [trackKind, setTrackKind] = useState("video");
  const [clipTrackId, setClipTrackId] = useState("track-1");
  const [clipId, setClipId] = useState("clip-1");
  const [clipLabel, setClipLabel] = useState("Clip 1");
  const [clipStart, setClipStart] = useState("0");
  const [clipDuration, setClipDuration] = useState("5000");
  const [clipKind, setClipKind] = useState("video");

  const wsUrl = useMemo(() => {
    const base = process.env.NEXT_PUBLIC_ORCHESTRATION_WS ?? "ws://localhost:8010/ws/operators";
    return base;
  }, []);
  const apiUrl = useMemo(() => {
    return process.env.NEXT_PUBLIC_ORCHESTRATION_HTTP ?? "http://localhost:8010";
  }, []);

  function makeRequestId(command: string): string {
    const suffix =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return `${command.toLowerCase()}-${suffix}`;
  }

  async function postJson(
    path: string,
    body: Record<string, unknown> | null,
    command: string,
    method: "POST" | "PUT" | "DELETE" = "POST",
  ) {
    setActionState("sending");
    const requestId = makeRequestId(command);
    try {
      const headers: Record<string, string> = {};
      let requestBody: Record<string, unknown> | null = null;
      if (body) {
        headers["Content-Type"] = "application/json";
        requestBody = { ...body, request_id: requestId };
      }
      const res = await fetch(`${apiUrl}${path}`, {
        method,
        headers,
        body: requestBody ? JSON.stringify(requestBody) : undefined,
      });
      const responsePayload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        const detail = (responsePayload.detail ?? responsePayload) as Record<string, unknown>;
        const reason = typeof detail.reason_code === "string" ? detail.reason_code : "UNKNOWN_ERROR";
        const message = typeof detail.message === "string" ? detail.message : JSON.stringify(detail).slice(0, 160);
        throw new Error(`HTTP ${res.status}: ${reason} - ${message}`);
      }

      const reason = typeof responsePayload.reason_code === "string" ? responsePayload.reason_code : "OK";
      const replay = responsePayload.idempotent_replay === true ? " replay=true" : "";
      setActionState("ok");
      setLastCommand({
        command,
        status: "ok",
        detail: `Accepted (${res.status}) ${reason}${replay}`,
        atIso: new Date().toISOString(),
        requestId,
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
        requestId,
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
  const driftAlertCount = nodes.filter((n) => {
    if (n.drift_alert_active !== undefined) return n.drift_alert_active;
    if (n.drift_alert_level !== undefined) return (n.drift_alert_level ?? "OK") !== "OK";
    return Math.abs(n.drift_ms) > driftThreshold;
  }).length;
  const driftLevelCounts = nodes.reduce(
    (acc, node) => {
      if (node.drift_level === "CRITICAL") acc.critical += 1;
      else if (node.drift_level === "WARN") acc.warn += 1;
      else acc.ok += 1;
      return acc;
    },
    { ok: 0, warn: 0, critical: 0 },
  );
  const activePreviewNode =
    previewTab === "combined" ? null : nodes.find((n) => n.node_id === previewTab) ?? null;
  const activePreviewSnapshot = activePreviewNode ? previewSnapshots[activePreviewNode.node_id] : null;
  const latestPreviewSnapshot = Object.values(previewSnapshots).sort((a, b) => b.timestamp_ms - a.timestamp_ms)[0];
  const activePreviewImage = activePreviewNode ? previewImages[activePreviewNode.node_id] : null;
  const latestPreviewImage = Object.values(previewImages).sort((a, b) => b.timestamp_ms - a.timestamp_ms)[0];
  const reliabilityTotals = nodes.reduce(
    (acc, node) => {
      acc.replays += node.replay_count ?? 0;
      acc.reconnects += node.reconnect_count ?? 0;
      acc.queueDepth += node.queue_depth ?? node.pending_commands ?? 0;
      acc.queued += node.queued_count ?? 0;
      return acc;
    },
    { replays: 0, reconnects: 0, queueDepth: 0, queued: 0 },
  );
  const globalPositionMs = activePreviewNode
    ? activePreviewNode.position_ms
    : Math.max(0, ...nodes.map((n) => n.position_ms));
  const timelineDurationMs = timelineSnapshot?.duration_ms ?? 60000;
  const timelinePlayheadMs = timelineSnapshot?.playhead_ms ?? globalPositionMs;
  const timelineTracks = timelineSnapshot?.tracks ?? [];
  const timelineMarks = [0, 0.25, 0.5, 0.75, 1];
  const snapIntervalMs = 1000;

  const sampleMappingConfig = useMemo(
    () => ({
      version: "v1",
      outputs: [
        {
          output_id: "output-1",
          mesh: {
            vertices: [0, 0, 1, 0, 1, 1],
            uvs: [0, 0, 1, 0, 1, 1],
            indices: [0, 1, 2],
          },
          blend: { gamma: 1.0, brightness: 1.0, black_level: 0.0 },
        },
      ],
    }),
    [],
  );

  const applySnap = (value: number) => {
    if (!snapEnabled) return value;
    return Math.round(value / snapIntervalMs) * snapIntervalMs;
  };

  const parseNumberList = useCallback((value: string, label: string, integer = false) => {
    const tokens = value.split(/[\s,]+/).filter(Boolean);
    if (tokens.length === 0) {
      throw new Error(`${label} cannot be empty`);
    }
    const numbers = tokens.map((token) => (integer ? Number.parseInt(token, 10) : Number.parseFloat(token)));
    if (numbers.some((num) => !Number.isFinite(num))) {
      throw new Error(`${label} must be numeric values`);
    }
    return numbers;
  }, []);

  const buildMappingConfig = useCallback(() => {
    const outputs = mappingOutputs.map((output, index) => {
      const outputId = output.outputId.trim();
      if (!outputId) {
        throw new Error(`Output ${index + 1} missing output_id`);
      }
      return {
        output_id: outputId,
        mesh: {
          vertices: parseNumberList(output.vertices, `Output ${index + 1} vertices`),
          uvs: parseNumberList(output.uvs, `Output ${index + 1} uvs`),
          indices: parseNumberList(output.indices, `Output ${index + 1} indices`, true),
        },
        blend: {
          gamma: Number.parseFloat(output.gamma || "1"),
          brightness: Number.parseFloat(output.brightness || "1"),
          black_level: Number.parseFloat(output.blackLevel || "0"),
        },
      };
    });
    return { version: "v1", outputs };
  }, [mappingOutputs, parseNumberList]);

  const mappingJson = useMemo(() => {
    try {
      return JSON.stringify(buildMappingConfig(), null, 2);
    } catch {
      return "";
    }
  }, [buildMappingConfig]);

  useEffect(() => {
    if (mappingOutputs.length === 0) {
      const initial = sampleMappingConfig.outputs.map((output) => ({
        outputId: output.output_id,
        vertices: output.mesh.vertices.join(", "),
        uvs: output.mesh.uvs.join(", "),
        indices: output.mesh.indices.join(", "),
        gamma: String(output.blend.gamma),
        brightness: String(output.blend.brightness),
        blackLevel: String(output.blend.black_level),
      }));
      setMappingOutputs(initial);
    }
  }, [mappingOutputs.length, sampleMappingConfig]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem("sc-theme");
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light";
    setTheme(initial);
    document.documentElement.dataset.theme = initial;
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("sc-theme", next);
    }
    document.documentElement.dataset.theme = next;
  };

  const onPlayAt = async () => {
    const now = Date.now();
    await postJson(
      "/api/v1/shows/play_at",
      {
        show_id: showId,
        target_time_ms: now + Math.max(minPlayAtLeadMs, playAtLeadMs),
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

  const onPreload = async () => {
    await postJson(
      "/api/v1/shows/preload",
      {
        show_id: showId,
        assets: [],
        node_ids: targetNodeIds(),
      },
      "PRELOAD",
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

  const onUpsertTrack = async () => {
    await postJson(
      `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(trackId)}`,
      {
        label: trackLabel,
        kind: trackKind,
      },
      "UPSERT_TRACK",
      "PUT",
    );
    await loadTimeline();
  };

  const onDeleteTrack = async () => {
    await postJson(
      `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(trackId)}`,
      null,
      "DELETE_TRACK",
      "DELETE",
    );
    await loadTimeline();
  };

  const onUpsertClip = async () => {
    const start = Number.parseInt(clipStart, 10);
    const duration = Number.parseInt(clipDuration, 10);
    await postJson(
      `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(clipTrackId)}/clips/${encodeURIComponent(clipId)}`,
      {
        label: clipLabel,
        start_ms: Number.isFinite(start) ? Math.max(0, start) : 0,
        duration_ms: Number.isFinite(duration) ? Math.max(1, duration) : 1000,
        kind: clipKind,
      },
      "UPSERT_CLIP",
      "PUT",
    );
    await loadTimeline();
  };

  const onDeleteClip = async () => {
    await postJson(
      `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(clipTrackId)}/clips/${encodeURIComponent(clipId)}`,
      null,
      "DELETE_CLIP",
      "DELETE",
    );
    await loadTimeline();
  };

  const onPreviewSnapshot = async () => {
    setPreviewStatus("loading");
    setPreviewError(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/preview/snapshot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_ids: targetNodeIds(), show_id: showId }),
      });
      const payload = (await res.json().catch(() => ({}))) as PreviewSnapshotResponse;
      if (!res.ok) {
        const detail = (payload as unknown as Record<string, unknown>).detail as Record<string, unknown> | undefined;
        const reason = detail?.reason_code ?? "UNKNOWN_ERROR";
        throw new Error(`HTTP ${res.status}: ${reason}`);
      }
      const next: Record<string, PreviewSnapshotEntry> = {};
      payload.snapshots.forEach((snap) => {
        next[snap.node_id] = snap;
      });
      setPreviewSnapshots(next);
      setPreviewStatus("idle");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Preview request failed";
      setPreviewError(message);
      setPreviewStatus("error");
    }
  };

  const onPreviewImage = async () => {
    setPreviewStatus("loading");
    setPreviewError(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/preview/image`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_ids: targetNodeIds(), show_id: showId, width: 320, height: 180 }),
      });
      const payload = (await res.json().catch(() => ({}))) as PreviewImageResponse;
      if (!res.ok) {
        const detail = (payload as unknown as Record<string, unknown>).detail as Record<string, unknown> | undefined;
        const reason = detail?.reason_code ?? "UNKNOWN_ERROR";
        throw new Error(`HTTP ${res.status}: ${reason}`);
      }
      const next: Record<string, PreviewImageEntry> = {};
      payload.images.forEach((img) => {
        next[img.node_id] = img;
      });
      setPreviewImages(next);
      setPreviewStatus("idle");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Preview image failed";
      setPreviewError(message);
      setPreviewStatus("error");
    }
  };

  const onLoadMappingSample = () => {
    const initial = sampleMappingConfig.outputs.map((output) => ({
      outputId: output.output_id,
      vertices: output.mesh.vertices.join(", "),
      uvs: output.mesh.uvs.join(", "),
      indices: output.mesh.indices.join(", "),
      gamma: String(output.blend.gamma),
      brightness: String(output.blend.brightness),
      blackLevel: String(output.blend.black_level),
    }));
    setMappingOutputs(initial);
    setMappingError(null);
    setMappingStatus("idle");
  };

  const onSaveMapping = async () => {
    setMappingStatus("saving");
    setMappingError(null);
    let parsed: Record<string, unknown>;
    try {
      parsed = buildMappingConfig() as Record<string, unknown>;
    } catch (error) {
      setMappingStatus("error");
      setMappingError(error instanceof Error ? error.message : "Invalid mapping config");
      return;
    }

    try {
      const res = await fetch(`${apiUrl}/api/v1/timeline/shows/${encodeURIComponent(showId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_ms: timelineDurationMs, mapping_config: parsed }),
      });
      const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        const detail = (payload.detail ?? payload) as Record<string, unknown>;
        const reason = typeof detail.reason_code === "string" ? detail.reason_code : "UNKNOWN_ERROR";
        const message = typeof detail.message === "string" ? detail.message : JSON.stringify(detail).slice(0, 160);
        throw new Error(`HTTP ${res.status}: ${reason} - ${message}`);
      }
      setMappingStatus("ok");
      setTimeout(() => setMappingStatus("idle"), 1200);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Mapping save failed";
      setMappingStatus("error");
      setMappingError(message);
    }
  };

  const updateMappingOutput = (index: number, field: keyof MappingOutputForm, value: string) => {
    setMappingOutputs((prev) =>
      prev.map((output, idx) => (idx === index ? { ...output, [field]: value } : output)),
    );
  };

  const addMappingOutput = () => {
    setMappingOutputs((prev) => [
      ...prev,
      {
        outputId: `output-${prev.length + 1}`,
        vertices: "0, 0, 1, 0, 1, 1",
        uvs: "0, 0, 1, 0, 1, 1",
        indices: "0, 1, 2",
        gamma: "1.0",
        brightness: "1.0",
        blackLevel: "0.0",
      },
    ]);
  };

  const removeMappingOutput = (index: number) => {
    setMappingOutputs((prev) => prev.filter((_, idx) => idx !== index));
  };

  const reorderTracks = async (fromId: string, toId: string) => {
    if (fromId === toId) return;
    const tracks = [...timelineTracks];
    const fromIndex = tracks.findIndex((track) => track.track_id === fromId);
    const toIndex = tracks.findIndex((track) => track.track_id === toId);
    if (fromIndex < 0 || toIndex < 0) return;
    const [moved] = tracks.splice(fromIndex, 1);
    tracks.splice(toIndex, 0, moved);
    for (let index = 0; index < tracks.length; index += 1) {
      const track = tracks[index];
      await postJson(
        `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(track.track_id)}`,
        {
          label: track.label,
          kind: track.kind,
          order: index,
        },
        "REORDER_TRACK",
        "PUT",
      );
    }
    await loadTimeline();
  };

  const reorderClips = async (trackId: string, fromId: string, toId: string) => {
    if (fromId === toId) return;
    const track = timelineTracks.find((t) => t.track_id === trackId);
    if (!track) return;
    const clips = [...track.clips];
    const fromIndex = clips.findIndex((clip) => clip.clip_id === fromId);
    const toIndex = clips.findIndex((clip) => clip.clip_id === toId);
    if (fromIndex < 0 || toIndex < 0) return;
    const [moved] = clips.splice(fromIndex, 1);
    clips.splice(toIndex, 0, moved);
    for (let index = 0; index < clips.length; index += 1) {
      const clip = clips[index];
      const startMs = clip.clip_id === moved.clip_id ? applySnap(clip.start_ms) : clip.start_ms;
      await postJson(
        `/api/v1/timeline/shows/${encodeURIComponent(showId)}/tracks/${encodeURIComponent(trackId)}/clips/${encodeURIComponent(clip.clip_id)}`,
        {
          label: clip.label,
          start_ms: startMs,
          duration_ms: clip.duration_ms,
          kind: clip.kind,
          order: index,
        },
        "REORDER_CLIP",
        "PUT",
      );
    }
    await loadTimeline();
  };

  const onTrackDragStart = (trackId: string) => {
    setDragTrackId(trackId);
  };

  const onTrackDrop = async (trackId: string) => {
    if (!dragTrackId) return;
    await reorderTracks(dragTrackId, trackId);
    setDragTrackId(null);
  };

  const onClipDragStart = (trackId: string, clipId: string) => {
    setDragClipTrackId(trackId);
    setDragClipId(clipId);
  };

  const onClipDrop = async (trackId: string, clipId: string) => {
    if (!dragClipId || !dragClipTrackId) return;
    if (dragClipTrackId !== trackId) {
      setDragClipId(null);
      setDragClipTrackId(null);
      return;
    }
    await reorderClips(trackId, dragClipId, clipId);
    setDragClipId(null);
    setDragClipTrackId(null);
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
          if (raw.nodes) setNodes(raw.nodes);
          if (raw.protocol_version) setProtocolVersion(raw.protocol_version);
          if (raw.drift_slo) setServerDriftSlo(raw.drift_slo);
          if (raw.play_at_min_lead_ms !== undefined) setMinPlayAtLeadMs(raw.play_at_min_lead_ms);
          if (raw.transcode_jobs) setTranscodeJobs(raw.transcode_jobs);
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
        <div className="topbar-actions">
          <button className="btn subtle theme-toggle" onClick={toggleTheme}>
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
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
            <button
              className={`chip snap-toggle ${snapEnabled ? "active" : ""}`}
              onClick={() => setSnapEnabled((prev) => !prev)}
            >
              Snap {snapEnabled ? "On" : "Off"}
            </button>
          </div>
          <div className="timeline-lanes">
            <div className="timeline-playhead" style={{ left: `${(timelinePlayheadMs / timelineDurationMs) * 100}%` }} />
            {timelineTracks.map((track) => (
              <div
                className="timeline-lane"
                key={track.track_id}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => onTrackDrop(track.track_id)}
              >
                <div className="track-label" draggable onDragStart={() => onTrackDragStart(track.track_id)}>
                  <span className="drag-handle">↕</span>
                  {track.label}
                </div>
                <div className="track-canvas">
                  {track.clips.map((clip) => (
                    <div
                      className={`clip ${clip.kind === "alpha" ? "alpha" : ""}`}
                      key={clip.clip_id}
                      draggable
                      onDragStart={() => onClipDragStart(track.track_id, clip.clip_id)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={() => onClipDrop(track.track_id, clip.clip_id)}
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
        <div className="timeline-editor">
          <div className="editor-column">
            <div className="editor-title">Tracks</div>
            <div className="editor-grid">
              <input className="input compact" value={trackId} onChange={(e) => setTrackId(e.target.value)} placeholder="track_id" />
              <input className="input compact" value={trackLabel} onChange={(e) => setTrackLabel(e.target.value)} placeholder="label" />
              <select className="input compact" value={trackKind} onChange={(e) => setTrackKind(e.target.value)}>
                <option value="video">video</option>
                <option value="audio">audio</option>
                <option value="image">image</option>
                <option value="alpha">alpha</option>
                <option value="trigger">trigger</option>
              </select>
              <button className="btn subtle" onClick={onUpsertTrack}>
                Save Track
              </button>
              <button className="btn subtle" onClick={onDeleteTrack}>
                Delete Track
              </button>
            </div>
          </div>
          <div className="editor-column">
            <div className="editor-title">Clips</div>
            <div className="editor-grid">
              <input
                className="input compact"
                value={clipTrackId}
                onChange={(e) => setClipTrackId(e.target.value)}
                placeholder="track_id"
              />
              <input className="input compact" value={clipId} onChange={(e) => setClipId(e.target.value)} placeholder="clip_id" />
              <input className="input compact" value={clipLabel} onChange={(e) => setClipLabel(e.target.value)} placeholder="label" />
              <input className="input compact" value={clipStart} onChange={(e) => setClipStart(e.target.value)} placeholder="start_ms" />
              <input className="input compact" value={clipDuration} onChange={(e) => setClipDuration(e.target.value)} placeholder="duration_ms" />
              <select className="input compact" value={clipKind} onChange={(e) => setClipKind(e.target.value)}>
                <option value="video">video</option>
                <option value="audio">audio</option>
                <option value="image">image</option>
                <option value="alpha">alpha</option>
                <option value="trigger">trigger</option>
              </select>
              <button className="btn subtle" onClick={onUpsertClip}>
                Save Clip
              </button>
              <button className="btn subtle" onClick={onDeleteClip}>
                Delete Clip
              </button>
            </div>
          </div>
        </div>
        <div className="mapping-panel">
          <div className="editor-title">Mapping Config</div>
          <div className="mapping-output-list">
            {mappingOutputs.map((output, index) => (
              <div className="mapping-output-card" key={`${output.outputId}-${index}`}>
                <div className="mapping-output-header">
                  <input
                    className="input compact"
                    value={output.outputId}
                    onChange={(event) => updateMappingOutput(index, "outputId", event.target.value)}
                    placeholder="output_id"
                  />
                  <button className="btn subtle" onClick={() => removeMappingOutput(index)}>
                    Remove
                  </button>
                </div>
                <div className="mapping-grid">
                  <label>
                    <span>Vertices</span>
                    <textarea
                      className="mapping-textarea"
                      value={output.vertices}
                      onChange={(event) => updateMappingOutput(index, "vertices", event.target.value)}
                      rows={2}
                    />
                  </label>
                  <label>
                    <span>UVs</span>
                    <textarea
                      className="mapping-textarea"
                      value={output.uvs}
                      onChange={(event) => updateMappingOutput(index, "uvs", event.target.value)}
                      rows={2}
                    />
                  </label>
                  <label>
                    <span>Indices</span>
                    <textarea
                      className="mapping-textarea"
                      value={output.indices}
                      onChange={(event) => updateMappingOutput(index, "indices", event.target.value)}
                      rows={2}
                    />
                  </label>
                </div>
                <div className="mapping-blend">
                  <label>
                    <span>Gamma</span>
                    <input
                      className="input compact"
                      value={output.gamma}
                      onChange={(event) => updateMappingOutput(index, "gamma", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Brightness</span>
                    <input
                      className="input compact"
                      value={output.brightness}
                      onChange={(event) => updateMappingOutput(index, "brightness", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Black</span>
                    <input
                      className="input compact"
                      value={output.blackLevel}
                      onChange={(event) => updateMappingOutput(index, "blackLevel", event.target.value)}
                    />
                  </label>
                </div>
              </div>
            ))}
          </div>
          <div className="mapping-json">
            <div className="muted">Generated JSON</div>
            <textarea className="mapping-textarea" value={mappingJson} readOnly rows={6} />
          </div>
          <div className="mapping-actions">
            <button className="btn subtle" onClick={onLoadMappingSample}>
              Load Sample
            </button>
            <button className="btn subtle" onClick={addMappingOutput}>
              Add Output
            </button>
            <button className="btn" onClick={onSaveMapping}>
              Save Mapping
            </button>
            <span className="muted">
              {mappingStatus === "saving" ? "Saving..." : mappingStatus === "ok" ? "Saved" : mappingStatus === "error" ? "Error" : "Idle"}
            </span>
          </div>
          {mappingError ? <div className="mapping-error">{mappingError}</div> : null}
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
              <span className="muted">
                {activePreviewSnapshot
                  ? `Preview @ ${new Date(activePreviewSnapshot.timestamp_ms).toLocaleTimeString()}`
                  : latestPreviewSnapshot
                    ? `Last preview @ ${new Date(latestPreviewSnapshot.timestamp_ms).toLocaleTimeString()}`
                    : "No preview snapshot yet"}
              </span>
              <span className="muted">
                {activePreviewImage
                  ? `Image @ ${new Date(activePreviewImage.timestamp_ms).toLocaleTimeString()}`
                  : latestPreviewImage
                    ? `Last image @ ${new Date(latestPreviewImage.timestamp_ms).toLocaleTimeString()}`
                    : "No preview image yet"}
              </span>
            </div>
          </div>
          <div className="preview-controls">
            <button className="btn subtle" onClick={onPreviewSnapshot} disabled={previewStatus === "loading"}>
              {previewStatus === "loading" ? "Previewing..." : "Preview Snapshot"}
            </button>
            <button className="btn subtle" onClick={onPreviewImage} disabled={previewStatus === "loading"}>
              Preview Image
            </button>
            {previewError ? <span className="mapping-error">{previewError}</span> : null}
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
            <button className="btn" onClick={onPreload}>
              PRELOAD
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
          <div className="reliability-overview">
            <span className="reliability-pill">Replays {reliabilityTotals.replays}</span>
            <span className="reliability-pill">Reconnects {reliabilityTotals.reconnects}</span>
            <span className="reliability-pill">Queue Depth {reliabilityTotals.queueDepth}</span>
            <span className="reliability-pill">Queued Total {reliabilityTotals.queued}</span>
          </div>
          <div className="drift-overview">
            <span className="drift-count drift-count-ok">OK {serverDriftSlo?.ok ?? driftLevelCounts.ok}</span>
            <span className="drift-count drift-count-warn">WARN {serverDriftSlo?.warn ?? driftLevelCounts.warn}</span>
            <span className="drift-count drift-count-critical">
              CRITICAL {serverDriftSlo?.critical ?? driftLevelCounts.critical}
            </span>
          </div>
          {transcodeJobs.length > 0 && (
            <div className="transcode-overview">
              <div className="section-title">Background Optimization</div>
              {transcodeJobs.map(job => (
                <div key={job.job_id} className="transcode-job">
                  <span className="job-id">{job.asset_id.split('-')[0]}</span>
                  <span className={`job-status ${job.status.toLowerCase()}`}>{job.status}</span>
                  <div className="progress-bar-container">
                    <div className="progress-bar" style={{ width: `${job.progress * 100}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="status-stack">
            {nodes.map((node) => {
              const alertLevel = node.drift_alert_level ?? node.drift_level;
              const driftAlert = node.drift_alert_active ?? alertLevel !== "OK";
              const preloadState = node.cache?.preload_state ?? "EMPTY";
              const preloadReady = preloadState === "READY" && (node.cache?.show_id ?? showId) === showId;
              return (
                <article className={`node-card ${driftAlert ? "card-alert" : ""}`} key={node.node_id}>
                  <div className="node-title">
                    <strong>{node.label || node.node_id}</strong>
                    <span className={statusClass(node.status)}>{node.status}</span>
                  </div>
                  <div className="node-metrics">
                    <span>GPU {number(node.metrics.gpu_pct)}%</span>
                    <span>CPU {number(node.metrics.cpu_pct)}%</span>
                    <span>Temp {number(node.metrics.gpu_temp ?? 0)}°C</span>
                    <span>VRAM {number(node.metrics.vram_mb ?? 0)}MB</span>
                    <span>Sync {node.drift_level}</span>
                    <span>Alert {alertLevel}</span>
                    <span>Latency {number(node.drift_ms)}ms</span>
                    <span>Queue {node.queue_depth ?? node.pending_commands}</span>
                    <span>Replay {node.replay_count ?? 0}</span>
                    <span>Reconnect {node.reconnect_count ?? 0}</span>
                    <span>Preload {preloadState}</span>
                    <span>
                      Cache {node.cache?.cached_assets ?? 0}/{node.cache?.asset_total ?? 0} •{" "}
                      {node.cache?.progress_assets_pct?.toFixed(0) ?? 0}%
                    </span>
                    {node.metrics.genlock && (
                      <span className={node.metrics.genlock.genlock_active ? "text-emerald-400" : "text-amber-400"}>
                        Genlock: {node.metrics.genlock.genlock_active ? "LOCKED" : "OFF"} ({node.metrics.genlock.genlock_total_hold_ms.toFixed(1)}ms hold)
                      </span>
                    )}
                  </div>
                  <div className="node-actions">
                    <span className={`drift-pill drift-${alertLevel.toLowerCase()}`}>{alertLevel}</span>
                    <span className="queue-depth-badge">Q {node.queue_depth ?? node.pending_commands}</span>
                    <span className={`cache-pill cache-${preloadState.toLowerCase()}`}>
                      {preloadState}
                    </span>
                    {preloadReady ? (
                      <span className="queue-depth-badge">READY</span>
                    ) : (
                      <span className="alert-pill">NOT READY</span>
                    )}
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
              ? `${lastCommand.command} ${lastCommand.status.toUpperCase()} • ${new Date(lastCommand.atIso).toLocaleTimeString()} • ${lastCommand.requestId} • ${lastCommand.detail}`
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

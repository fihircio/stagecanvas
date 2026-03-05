# StageCanvas Architecture v0.1

## 1) Product Scope

StageCanvas is a **hybrid** media-server platform:

- Cloud/remote-capable control and monitoring
- Strictly local rendering and projector output
- Deterministic multi-node playback for live shows

This keeps the reliability of WATCHOUT-style local engines while modernizing collaboration and operations.

## 2) System Layers

### A. Control Layer (`control-ui`)

Responsibilities:

- Show authoring (timeline, cues, node assignment)
- Operator controls (play/pause/seek/stop)
- Topology and health dashboard

Tech direction:

- React + Next.js
- Optional Electron wrapper for offline operator app

### B. Orchestration Layer (`orchestration-server`)

Responsibilities:

- Show state authority
- Scheduled playback commands (`play_at`)
- Node discovery and heartbeats
- Content distribution coordination

Tech direction:

- FastAPI + WebSocket + REST
- Redis (ephemeral coordination), Postgres (metadata), S3-compatible object store (media registry)

### C. Render Layer (`render-node`)

Responsibilities:

- Receive control commands
- Maintain local show state machine
- Decode media, buffer frames, render outputs
- Apply warp/blend and output to displays

Tech direction (MVP):

- Unity render app + node agent
- FFmpeg-based transcoding pipeline on ingest
- GPU-friendly playback codec strategy (HAP/ProRes/NotchLC-compatible path)

## 3) Core Runtime Contracts

### Show state machine

- `IDLE`
- `LOADING`
- `READY`
- `PLAYING`
- `PAUSED`
- `ERROR`

### Sync model

1. Clock sync (NTP in MVP, PTP later)
2. Scheduled playback (`play_at` absolute node time)
3. Frame reconciliation (software sync in MVP, genlock-ready later)
4. Drift SLO classification (`OK`/`WARN`/`CRITICAL`) for operator actions

### Control command model

- `LOAD_SHOW`
- `PLAY_AT`
- `PAUSE`
- `SEEK`
- `STOP`
- `PING`

## 4) Network and Deployment Model

Separated logical networks:

- Control network: UI <-> orchestration
- Render network: orchestration <-> nodes
- Optional media network: artifact distribution

Node behavior:

- Nodes run even if cloud/control is unavailable
- Existing loaded show can continue locally
- Commands are idempotent and sequence-numbered

## 5) Media Strategy

Ingest path:

1. Upload source media
2. Transcode to playback profile(s)
3. Push/cache on nodes before show start

Playback design goals:

- Frame-accurate seek
- Low CPU decode load
- Stable multi-stream playback
- Predictable VRAM and disk cache behavior

## 6) Observability (WATCHNET equivalent)

Node metrics:

- CPU/GPU usage
- VRAM usage
- decode latency
- dropped frames
- output FPS
- temperature

Events:

- Node connected/disconnected
- show loaded
- playback drift warnings
- output failure

## 7) Security Model

- Role-based access for control UI users
- Signed node registration tokens
- mTLS support planned between orchestration and nodes
- Offline-mode operation for isolated venues

## 8) Non-Goals (MVP)

- Full cloud rendering
- Browser-based high-performance projector output
- Genlock/hardware frame lock from day one

## 9) MVP Acceptance Criteria

- Two nodes can load same show and execute `PLAY_AT` within acceptable drift
- One operator can control nodes from web UI
- Node health and playback status visible in real time
- Warp/blend available for at least one multi-projector setup

Determinism details:

- See `docs/DETERMINISM.md`

# Control UI

Current stack:

- Next.js (React, App Router)
- WebSocket client for live node telemetry (`/ws/operators`)

Implemented screen:

- Node dashboard (status, drift, CPU/GPU, FPS, dropped frames)
- Target selector (all nodes or a specific node)
- Drift alert threshold input
- Protocol/SLO badges from orchestration snapshots

## Run

```bash
cd control-ui
npm install
npm run dev
```

## Configuration

- `NEXT_PUBLIC_ORCHESTRATION_WS` (optional)
  - default: `ws://localhost:8010/ws/operators`
- `NEXT_PUBLIC_ORCHESTRATION_HTTP` (optional)
  - default: `http://localhost:8010`

Example:

```bash
NEXT_PUBLIC_ORCHESTRATION_WS=ws://localhost:8010/ws/operators npm run dev
```

## Operator Controls

- `PLAY_AT (+3s)` -> `POST /api/v1/shows/play_at`
- `PAUSE` -> `POST /api/v1/operators/pause`
- `STOP` -> `POST /api/v1/operators/stop`
- `LOAD_SHOW` -> `POST /api/v1/operators/load_show`
- `SEEK` -> `POST /api/v1/operators/seek`

All controls dispatch to either:

- all nodes (default), or
- selected node from the target selector.

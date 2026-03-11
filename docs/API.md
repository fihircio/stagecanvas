# StageCanvas REST API & SDK Quick-Start Guide

The StageCanvas Orchestration Server provides a comprehensive REST API and WebSocket interface for managing render nodes, media assets, and precision show control.

## Interactive Documentation
Once the server is running, you can access the interactive Swagger UI at:
`http://localhost:18010/docs`

## Core Concepts

### Render Nodes
Render nodes are discovered automatically via mDNS/Zeroconf. You can also manually register them or monitor their health via the `/api/v1/nodes` endpoints.

### Media Registry
All assets must be registered before being used in a show. The Orchestration Server handles background transcoding (to HAP/DXV) to ensure GPU-optimized playback.

### Timeline & Shows
Shows consist of tracks and clips. The `TimelineRepository` manages the persistent state of these shows in a SQLite database. Playback is triggered using `PLAY_AT` (precision time-synced) or `SEEK` commands.

---

## API Reference

### Health & System
- `GET /health`: Basic health check.

### Node Management
- `GET /api/v1/nodes`: List all active nodes.
- `POST /api/v1/nodes/heartbeat`: (Internal) Used by render nodes to report status.

### Media Management
- `GET /api/v1/media`: List all assets.
- `POST /api/v1/media`: Register a new asset.
- `GET /api/v1/media/{asset_id}`: Get asset details.

### Show Control
- `GET /api/v1/shows`: List all shows.
- `POST /api/v1/shows/play_at`: Precision playback start.
- `POST /api/v1/shows/seek`: Seek all nodes to a specific position.

### IO & Synchronization (SC-100)
- `GET /api/v1/ltc/status`: Get current SMPTE LTC reader state.
- `POST /api/v1/ltc/mode`: Change LTC sync mode (CHASE, JAM_SYNC, FREE_WHEEL).

---

## Examples

### 1. Precision Playback Start
To start playback at a specific wall-clock time:
```bash
curl -X POST http://localhost:18010/api/v1/shows/play_at \
  -H "Content-Type: application/json" \
  -d '{
    "show_id": "demo-show",
    "target_time_ms": 1710150000000,
    "node_ids": ["node-01"]
  }'
```

### 2. Switching LTC Sync Mode
To switch the LTC reader to "Chase" mode at 24fps:
```bash
curl -X POST http://localhost:18010/api/v1/ltc/mode \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "chase",
    "fps": 24
  }'
```

## WebSocket Snapshots
Connect to `ws://localhost:18010/ws/operators` to receive real-time updates of node status, transcode progress, and LTC timecode.

```json
{
  "type": "NODES_SNAPSHOT",
  "nodes": [...],
  "ltc_status": {
    "mode": "chase",
    "timecode_ms": 12500,
    "locked": true,
    "last_frame_str": "00:00:12:12"
  }
}
```

## Error Handling
The API uses standard HTTP status codes:
- `200 OK`: Success.
- `400 Bad Request`: Invalid parameters.
- `404 Not Found`: Resource (node, asset, show) missing.
- `503 Service Unavailable`: Component (like LTC reader) not initialized.

# Orchestration Server

Current stack:

- FastAPI
- REST + WebSocket (scaffolded)
- In-memory registry (Postgres/Redis later phase)

Responsibilities:

- Node registration + heartbeat intake
- Command fanout to render nodes
- Show state authority and scheduling (`PLAY_AT`)
- Drift tracking and operational events

## Run

```bash
cd orchestration-server
python -m pip install -e .
uvicorn app.main:app --reload --port 8010
```

## Implemented Endpoints

- `GET /health`
- `POST /api/v1/nodes/register`
- `POST /api/v1/nodes/{node_id}/heartbeat`
- `GET /api/v1/nodes`
- `GET /api/v1/slo`
- `POST /api/v1/commands/broadcast`
- `POST /api/v1/nodes/{node_id}/commands`
- `POST /api/v1/shows/play_at`
- `POST /api/v1/operators/pause`
- `POST /api/v1/operators/stop`
- `POST /api/v1/operators/load_show`
- `POST /api/v1/operators/seek`
- `WS /ws/nodes/{node_id}`
- `WS /ws/operators`

## Notes

- Nodes must register before opening `WS /ws/nodes/{node_id}`.
- Broadcast commands are queued per node if not currently connected.
- `PLAY_AT` is exposed as an orchestration-level endpoint and dispatched as a `COMMAND`.
- Operator endpoints accept optional `node_ids` for targeted dispatch.
- `PLAY_AT` enforces a minimum lead time (`1500ms` in MVP).
- Operator WS snapshots include drift SLO summary and protocol version.

## Mock Node (Local E2E)

```bash
cd orchestration-server
python -m pip install -e .
python scripts/mock_node.py --node-id mock-node-1 --label "Mock Node 1"
```

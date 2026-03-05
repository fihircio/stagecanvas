from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import MIN_PLAY_AT_LEAD_MS, PROTOCOL_VERSION
from .models import (
    ControlCommand,
    HeartbeatRequest,
    OperatorCommandRequest,
    RegisterNodeRequest,
    SchedulePlayAtRequest,
)
from .registry import NodeRegistry

app = FastAPI(title="StageCanvas Orchestration Server", version="0.1.0")
registry = NodeRegistry()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/nodes/register")
async def register_node(body: RegisterNodeRequest) -> dict[str, object]:
    record = await registry.register(body)
    return {
        "ok": True,
        "node_id": record.node_id,
        "connected": record.connected,
        "status": record.status,
    }


@app.post("/api/v1/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, body: HeartbeatRequest) -> dict[str, object]:
    record = await registry.heartbeat(node_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return {"ok": True, "node_id": node_id, "status": record.status, "drift_ms": record.drift_ms}


@app.get("/api/v1/nodes")
async def list_nodes() -> dict[str, object]:
    return {"nodes": await registry.list_nodes()}


@app.get("/api/v1/slo")
async def slo_snapshot() -> dict[str, object]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "drift_slo": await registry.drift_summary(),
        "play_at_min_lead_ms": MIN_PLAY_AT_LEAD_MS,
    }


async def _dispatch_to_nodes(command: ControlCommand, node_ids: list[str]) -> dict[str, object]:
    delivered = 0
    queued = 0
    missing = 0
    targets = list(dict.fromkeys(node_ids))
    for node_id in targets:
        record, envelope = await registry.enqueue_command(node_id, command)
        if record is None or envelope is None:
            missing += 1
            continue
        if record.ws is not None and record.connected:
            try:
                await record.ws.send_text(json.dumps(envelope))
                delivered += 1
                await registry.dequeue_pending(node_id)
            except RuntimeError:
                queued += 1
        else:
            queued += 1

    return {
        "ok": True,
        "command": command.command,
        "target_count": len(targets),
        "delivered_count": delivered,
        "queued_count": queued,
        "missing_count": missing,
    }


@app.post("/api/v1/commands/broadcast")
async def broadcast_command(body: ControlCommand) -> dict[str, object]:
    node_ids = await registry.active_node_ids()
    return await _dispatch_to_nodes(body, node_ids)


@app.post("/api/v1/nodes/{node_id}/commands")
async def node_command(node_id: str, body: ControlCommand) -> dict[str, object]:
    result = await _dispatch_to_nodes(body, [node_id])
    if result["missing_count"] == 1:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return result


@app.post("/api/v1/shows/play_at")
async def schedule_play_at(body: SchedulePlayAtRequest) -> dict[str, object]:
    now_ms = int(time.time() * 1000)
    if body.target_time_ms < (now_ms + MIN_PLAY_AT_LEAD_MS):
        raise HTTPException(
            status_code=422,
            detail=f"PLAY_AT requires at least {MIN_PLAY_AT_LEAD_MS}ms lead time.",
        )

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="PLAY_AT",
        payload={"show_id": body.show_id, **body.payload},
        target_time_ms=body.target_time_ms,
        seq=int(time.time() * 1000),
        origin="scheduler",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    return {"ok": True, "scheduled": True, "play_at": body.target_time_ms, "dispatch": result}


@app.post("/api/v1/operators/pause")
async def operator_pause(body: OperatorCommandRequest) -> dict[str, object]:
    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="PAUSE",
        payload=body.payload,
        seq=int(time.time() * 1000),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    return await _dispatch_to_nodes(command, target_ids)


@app.post("/api/v1/operators/stop")
async def operator_stop(body: OperatorCommandRequest) -> dict[str, object]:
    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="STOP",
        payload=body.payload,
        seq=int(time.time() * 1000),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    return await _dispatch_to_nodes(command, target_ids)


@app.post("/api/v1/operators/load_show")
async def operator_load_show(body: OperatorCommandRequest) -> dict[str, object]:
    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="LOAD_SHOW",
        payload=body.payload,
        seq=int(time.time() * 1000),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    return await _dispatch_to_nodes(command, target_ids)


@app.post("/api/v1/operators/seek")
async def operator_seek(body: OperatorCommandRequest) -> dict[str, object]:
    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="SEEK",
        payload=body.payload,
        seq=int(time.time() * 1000),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    return await _dispatch_to_nodes(command, target_ids)


@app.websocket("/ws/nodes/{node_id}")
async def node_socket(ws: WebSocket, node_id: str) -> None:
    await ws.accept()
    record = await registry.get(node_id)
    if record is None:
        await ws.send_json({"type": "ERROR", "message": f"Node {node_id} is not registered"})
        await ws.close(code=1008)
        return

    await registry.set_connection(node_id, ws)
    pending = await registry.dequeue_pending(node_id)
    for msg in pending:
        await ws.send_text(json.dumps(msg))

    try:
        while True:
            # MVP: listen for node-side status updates on WS channel as optional path.
            raw = await ws.receive_text()
            with suppress(json.JSONDecodeError):
                payload = json.loads(raw)
                if payload.get("type") == "HEARTBEAT":
                    hb = HeartbeatRequest.model_validate(
                        {
                            "status": payload.get("status", "IDLE"),
                            "metrics": payload.get("metrics", {}),
                            "position_ms": payload.get("position_ms", 0),
                            "drift_ms": payload.get("drift_ms", 0.0),
                            "show_id": payload.get("show_id"),
                        }
                    )
                    await registry.heartbeat(node_id, hb)
    except WebSocketDisconnect:
        pass
    finally:
        await registry.clear_connection(node_id)


@app.websocket("/ws/operators")
async def operator_socket(ws: WebSocket) -> None:
    await ws.accept()
    # Simple polling stream for dashboards; replace with event push later.
    try:
        while True:
            await ws.send_json(
                {
                    "type": "NODES_SNAPSHOT",
                    "protocol_version": PROTOCOL_VERSION,
                    "nodes": await registry.list_nodes(),
                    "drift_slo": await registry.drift_summary(),
                    "play_at_min_lead_ms": MIN_PLAY_AT_LEAD_MS,
                }
            )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return

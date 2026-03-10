from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import MIN_PLAY_AT_LEAD_MS, PROTOCOL_VERSION
from .models import (
    ControlCommand,
    HeartbeatRequest,
    PreviewSnapshotRequest,
    MappingConfig,
    MediaAssetCreateRequest,
    MediaAssetUpdateRequest,
    AssetTransferRequest,
    OperatorCommandRequest,
    PreloadShowRequest,
    RegisterNodeRequest,
    SchedulePlayAtRequest,
    TimelineShowSummary,
    TimelineSnapshotResponse,
    TimelineUpsertClipRequest,
    TimelineUpsertShowRequest,
    TimelineUpsertTrackRequest,
)
from .command_ledger import CommandLedger
from .registry import AssetTransferWorker, MediaRegistry, NodeRegistry, TransferTask
from .timeline_repository import TimelineRepository

app = FastAPI(title="StageCanvas Orchestration Server", version="0.1.0")
registry = NodeRegistry()
media_registry = MediaRegistry(Path(__file__).resolve().parent.parent / "data" / "media_registry.json")
transfer_worker = AssetTransferWorker(registry)
timeline_repo = TimelineRepository(Path(__file__).resolve().parent.parent / "data" / "timeline.db")
command_ledger = CommandLedger(Path(__file__).resolve().parent.parent / "data" / "orchestration.db")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _transfer_loop() -> None:
    while True:
        ran = await transfer_worker.run_once()
        await asyncio.sleep(0.05 if ran else 0.2)


@app.on_event("startup")
async def _startup() -> None:
    app.state.transfer_task = asyncio.create_task(_transfer_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    task = getattr(app.state, "transfer_task", None)
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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


@app.get("/api/v1/nodes/{node_id}/drift_history")
async def node_drift_history(node_id: str) -> dict[str, object]:
    record = await registry.get(node_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return {"node_id": node_id, "history": await registry.get_drift_history(node_id)}


@app.post("/api/v1/preview/snapshot")
async def preview_snapshot(body: PreviewSnapshotRequest) -> dict[str, object]:
    target_ids = body.node_ids or await registry.active_node_ids()
    nodes = await registry.list_nodes()
    node_by_id = {node["node_id"]: node for node in nodes}
    now_ms = int(time.time() * 1000)
    snapshots: list[dict[str, object]] = []
    for node_id in target_ids:
        node = node_by_id.get(node_id)
        if node is None:
            snapshots.append(
                {
                    "node_id": node_id,
                    "ok": False,
                    "reason_code": "NOT_REGISTERED",
                    "timestamp_ms": now_ms,
                }
            )
            continue
        snapshots.append(
            {
                "node_id": node_id,
                "ok": True,
                "status": node.get("status"),
                "show_id": node.get("show_id"),
                "position_ms": node.get("position_ms"),
                "timestamp_ms": now_ms,
            }
        )
    return {"ok": True, "requested_count": len(target_ids), "snapshots": snapshots}


@app.post("/api/v1/media")
async def register_media_asset(body: MediaAssetCreateRequest) -> dict[str, object]:
    record, is_new, idempotent = await media_registry.register(body)
    if not idempotent:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "ASSET_ID_MISMATCH",
                "message": "Asset ID already exists with different metadata.",
            },
        )
    return {"ok": True, "asset": record.to_response().model_dump(mode="json"), "idempotent": not is_new}


@app.get("/api/v1/media")
async def list_media_assets() -> dict[str, object]:
    assets = await media_registry.list_assets()
    return {"assets": [asset.model_dump(mode="json") for asset in assets]}


@app.get("/api/v1/media/{asset_id}")
async def get_media_asset(asset_id: str) -> dict[str, object]:
    record = await media_registry.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {"asset": record.to_response().model_dump(mode="json")}


@app.patch("/api/v1/media/{asset_id}")
async def update_media_asset(asset_id: str, body: MediaAssetUpdateRequest) -> dict[str, object]:
    record = await media_registry.update(asset_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {"ok": True, "asset": record.to_response().model_dump(mode="json")}


@app.get("/api/v1/slo")
async def slo_snapshot() -> dict[str, object]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "drift_slo": await registry.drift_summary(),
        "play_at_min_lead_ms": MIN_PLAY_AT_LEAD_MS,
    }


@app.get("/api/v1/timeline/snapshot", response_model=TimelineSnapshotResponse)
async def timeline_snapshot(show_id: str = "demo-show") -> TimelineSnapshotResponse:
    nodes = await registry.list_nodes()
    playhead_ms = 0
    if nodes:
        playhead_ms = max(int(node.get("position_ms", 0)) for node in nodes)
    try:
        return timeline_repo.snapshot(show_id=show_id, playhead_ms=playhead_ms)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/timeline/shows", response_model=list[TimelineShowSummary])
async def timeline_list_shows() -> list[TimelineShowSummary]:
    return timeline_repo.list_shows()


@app.put("/api/v1/timeline/shows/{show_id}")
async def timeline_upsert_show(show_id: str, body: TimelineUpsertShowRequest) -> dict[str, object]:
    mapping_payload = None
    if body.mapping_config is not None:
        mapping_payload = body.mapping_config.model_dump(mode="json")
        _validate_mapping_config_from_payload({"mapping_config": mapping_payload})
    timeline_repo.upsert_show(show_id=show_id, duration_ms=body.duration_ms, mapping_config=mapping_payload)
    return {"ok": True, "show_id": show_id}


@app.delete("/api/v1/timeline/shows/{show_id}")
async def timeline_delete_show(show_id: str) -> dict[str, object]:
    try:
        timeline_repo.delete_show(show_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id}


@app.put("/api/v1/timeline/shows/{show_id}/tracks/{track_id}")
async def timeline_upsert_track(show_id: str, track_id: str, body: TimelineUpsertTrackRequest) -> dict[str, object]:
    try:
        position = body.order if body.order is not None else body.position
        timeline_repo.upsert_track(
            show_id=show_id,
            track_id=track_id,
            label=body.label,
            kind=body.kind,
            position=position,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id}


@app.delete("/api/v1/timeline/shows/{show_id}/tracks/{track_id}")
async def timeline_delete_track(show_id: str, track_id: str) -> dict[str, object]:
    try:
        timeline_repo.delete_track(show_id=show_id, track_id=track_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id}


@app.put("/api/v1/timeline/shows/{show_id}/tracks/{track_id}/clips/{clip_id}")
async def timeline_upsert_clip(
    show_id: str,
    track_id: str,
    clip_id: str,
    body: TimelineUpsertClipRequest,
) -> dict[str, object]:
    try:
        position = body.order if body.order is not None else body.position
        timeline_repo.upsert_clip(
            show_id=show_id,
            track_id=track_id,
            clip_id=clip_id,
            label=body.label,
            start_ms=body.start_ms,
            duration_ms=body.duration_ms,
            kind=body.kind,
            position=position,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id, "clip_id": clip_id}


@app.delete("/api/v1/timeline/shows/{show_id}/tracks/{track_id}/clips/{clip_id}")
async def timeline_delete_clip(show_id: str, track_id: str, clip_id: str) -> dict[str, object]:
    try:
        timeline_repo.delete_clip(show_id=show_id, track_id=track_id, clip_id=clip_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id, "clip_id": clip_id}


async def _dispatch_to_nodes(command: ControlCommand, node_ids: list[str]) -> dict[str, object]:
    delivered = 0
    queued = 0
    missing = 0
    skipped = 0
    per_node: list[dict[str, str]] = []
    targets = list(dict.fromkeys(node_ids))
    if len(targets) == 0:
        return {
            "ok": False,
            "command": command.command,
            "seq": command.seq,
            "target_count": 0,
            "delivered_count": 0,
            "queued_count": 0,
            "missing_count": 0,
            "skipped_count": 0,
            "per_node": [],
            "reason_code": "NO_TARGETS",
            "message": "No target nodes resolved for command dispatch.",
        }
    for node_id in targets:
        record, envelope, reason = await registry.enqueue_command(node_id, command)
        if record is None:
            missing += 1
            per_node.append({"node_id": node_id, "status": "missing", "reason_code": reason})
            continue
        if envelope is None:
            skipped += 1
            per_node.append({"node_id": node_id, "status": "skipped", "reason_code": reason})
            continue
        if record.ws is not None and record.connected:
            try:
                await record.ws.send_text(json.dumps(envelope))
                delivered += 1
                await registry.dequeue_pending(node_id)
                per_node.append({"node_id": node_id, "status": "delivered", "reason_code": "SENT_TO_SOCKET"})
            except RuntimeError:
                queued += 1
                per_node.append({"node_id": node_id, "status": "queued", "reason_code": "SOCKET_SEND_ERROR"})
        else:
            queued += 1
            per_node.append({"node_id": node_id, "status": "queued", "reason_code": "OFFLINE_QUEUED"})

    return {
        "ok": True,
        "command": command.command,
        "seq": command.seq,
        "target_count": len(targets),
        "delivered_count": delivered,
        "queued_count": queued,
        "missing_count": missing,
        "skipped_count": skipped,
        "per_node": per_node,
    }


@app.post("/api/v1/commands/broadcast")
async def broadcast_command(body: ControlCommand) -> dict[str, object]:
    node_ids = await registry.active_node_ids()
    return await _dispatch_to_nodes(body, node_ids)


@app.post("/api/v1/nodes/{node_id}/commands")
async def node_command(node_id: str, body: ControlCommand) -> dict[str, object]:
    result = await _dispatch_to_nodes(body, [node_id])
    if result["missing_count"] == 1:
        raise HTTPException(
            status_code=404,
            detail={"reason_code": "NOT_REGISTERED", "message": f"Node not found: {node_id}"},
        )
    return result


@app.post("/api/v1/shows/play_at")
async def schedule_play_at(body: SchedulePlayAtRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="play_at",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    now_ms = int(time.time() * 1000)
    if body.target_time_ms < (now_ms + MIN_PLAY_AT_LEAD_MS):
        raise HTTPException(
            status_code=422,
            detail={
                "reason_code": "PLAY_AT_LEAD_TIME_TOO_SHORT",
                "message": f"PLAY_AT requires at least {MIN_PLAY_AT_LEAD_MS}ms lead time.",
                "min_lead_ms": MIN_PLAY_AT_LEAD_MS,
            },
        )

    target_ids = body.node_ids or await registry.active_node_ids()
    not_ready: list[dict[str, str]] = []
    for node_id in target_ids:
        record = await registry.get(node_id)
        if record is None:
            not_ready.append({"node_id": node_id, "reason": "NOT_REGISTERED"})
            continue
        cache = record.cache or {}
        preload_state = str(cache.get("preload_state", "EMPTY"))
        cache_show_id = cache.get("show_id")
        if preload_state != "READY" or (cache_show_id and cache_show_id != body.show_id):
            not_ready.append(
                {
                    "node_id": node_id,
                    "preload_state": preload_state,
                    "cache_show_id": str(cache_show_id),
                }
            )
    if not_ready:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "PLAY_AT_PRELOAD_NOT_READY",
                "message": "One or more target nodes are not READY for preload.",
                "not_ready": not_ready,
                "required_state": "READY",
            },
        )

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="PLAY_AT",
        payload={"show_id": body.show_id, **body.payload},
        target_time_ms=body.target_time_ms,
        seq=command_ledger.next_seq(),
        origin="scheduler",
    )
    result = await _dispatch_to_nodes(command, target_ids)
    response = {"ok": True, "scheduled": True, "play_at": body.target_time_ms, "dispatch": result}
    command_ledger.finalize_request("play_at", body.request_id, response)
    return response


@app.post("/api/v1/shows/preload")
async def preload_show(body: PreloadShowRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="preload_show",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="LOAD_SHOW",
        payload={
            "show_id": body.show_id,
            "preload_only": True,
            "request_id": body.request_id,
            "assets": [asset.model_dump(mode="json", exclude_none=True) for asset in body.assets],
        },
        seq=command_ledger.next_seq(),
        origin="scheduler",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    dispatch = await _dispatch_to_nodes(command, target_ids)
    response = {
        "ok": True,
        "preload_requested": True,
        "show_id": body.show_id,
        "asset_count": len(body.assets),
        "dispatch": dispatch,
    }
    command_ledger.finalize_request("preload_show", body.request_id, response)
    return response


@app.post("/api/v1/assets/transfer")
async def transfer_assets(body: AssetTransferRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="asset_transfer",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    target_ids = body.node_ids or await registry.active_node_ids()
    total_bytes = 0
    for asset in body.assets:
        total_bytes += max(0, int(asset.size_bytes))

    per_node: list[dict[str, object]] = []
    for node_id in target_ids:
        record = await registry.get(node_id)
        if record is None:
            per_node.append({"node_id": node_id, "status": "missing"})
            continue
        record.cache = {
            **record.cache,
            "show_id": body.show_id,
            "preload_state": "LOADING",
            "asset_total": len(body.assets),
            "cached_assets": 0,
            "bytes_total": total_bytes,
            "bytes_cached": 0,
            "progress_assets_pct": 0.0,
            "progress_bytes_pct": 0.0,
            "progress_message": "transfer",
            "last_preload_request_id": body.request_id,
        }
        per_node.append({"node_id": node_id, "status": "queued"})

        for asset in body.assets:
            transfer_worker.enqueue(
                TransferTask(
                    node_id=node_id,
                    show_id=body.show_id,
                    media_id=asset.media_id,
                    size_bytes=int(asset.size_bytes),
                )
            )
        await registry.update_transfer_queue_depth(node_id, transfer_worker.pending_count())

    transfer_commands = [
        {
            "media_id": asset.media_id,
            "uri": asset.uri,
            "checksum": asset.checksum,
            "size_bytes": asset.size_bytes,
        }
        for asset in body.assets
    ]
    response = {
        "ok": True,
        "transfer_requested": True,
        "show_id": body.show_id,
        "asset_count": len(body.assets),
        "transfer_commands": transfer_commands,
        "per_node": per_node,
    }
    command_ledger.finalize_request("asset_transfer", body.request_id, response)
    return response


@app.post("/api/v1/operators/pause")
async def operator_pause(body: OperatorCommandRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="operator_pause",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="PAUSE",
        payload=body.payload,
        seq=command_ledger.next_seq(),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    command_ledger.finalize_request("operator_pause", body.request_id, result)
    return result


@app.post("/api/v1/operators/stop")
async def operator_stop(body: OperatorCommandRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="operator_stop",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="STOP",
        payload=body.payload,
        seq=command_ledger.next_seq(),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    command_ledger.finalize_request("operator_stop", body.request_id, result)
    return result


@app.post("/api/v1/operators/load_show")
async def operator_load_show(body: OperatorCommandRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="operator_load_show",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    payload = dict(body.payload)
    mapping_config = payload.get("mapping_config")
    show_id = payload.get("show_id")
    if mapping_config is None and show_id is not None:
        try:
            mapping_config = timeline_repo.get_mapping_config(str(show_id))
        except KeyError:
            mapping_config = None
        if mapping_config is not None:
            payload["mapping_config"] = mapping_config
    _validate_mapping_config_from_payload(payload)
    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="LOAD_SHOW",
        payload=payload,
        seq=command_ledger.next_seq(),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    command_ledger.finalize_request("operator_load_show", body.request_id, result)
    return result


@app.post("/api/v1/operators/seek")
async def operator_seek(body: OperatorCommandRequest) -> dict[str, object]:
    replay = _idempotent_begin_or_raise(
        scope="operator_seek",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="SEEK",
        payload=body.payload,
        seq=command_ledger.next_seq(),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    command_ledger.finalize_request("operator_seek", body.request_id, result)
    return result


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
                            "cache": payload.get("cache"),
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


def _idempotent_begin_or_raise(
    scope: str,
    request_id: str | None,
    payload: dict[str, object],
) -> dict[str, object] | None:
    status, replay = command_ledger.begin_request(scope=scope, request_id=request_id, payload=payload)
    if status == "REPLAY":
        return replay
    if status == "MISMATCH":
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "REQUEST_ID_PAYLOAD_MISMATCH",
                "message": "The same request_id was reused with a different payload.",
            },
        )
    if status == "IN_PROGRESS":
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "REQUEST_IN_PROGRESS",
                "message": "A request with this request_id is currently in progress.",
            },
        )
    return None


def _validate_mapping_config_from_payload(payload: dict[str, object]) -> None:
    mapping_config = payload.get("mapping_config")
    if mapping_config is None:
        return
    try:
        MappingConfig.model_validate(mapping_config)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "reason_code": "INVALID_MAPPING_CONFIG",
                "message": f"mapping_config validation failed: {exc}",
            },
        ) from exc

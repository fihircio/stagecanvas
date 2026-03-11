from __future__ import annotations

import asyncio
import logging
import hashlib
import json
import os
import time
from datetime import timedelta
from typing import Any, Optional, Literal, Union
from contextlib import suppress
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Depends, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import MIN_PLAY_AT_LEAD_MS, PROTOCOL_VERSION
from .models import (
    ControlCommand,
    HeartbeatRequest,
    PreviewImageRequest,
    PreviewSnapshotRequest,
    MappingConfig,
    MediaAssetCreateRequest,
    MediaAssetUpdateRequest,
    TranscodeJobCreateRequest,
    TranscodeJobUpdateRequest,
    AssetTransferRequest,
    OperatorCommandRequest,
    PreloadShowRequest,
    RegisterNodeRequest,
    SchedulePlayAtRequest,
    TriggerEvent,
    TriggerFireRequest,
    TriggerRegisterRequest,
    TriggerRule,
    TimelineShowSummary,
    TimelineSnapshotResponse,
    TimelineUpsertClipRequest,
    TimelineUpsertShowRequest,
    TimelineUpsertTrackRequest,
    LockRequest,
    LTCStatusResponse,
    LTCSetModeRequest,
    User,
    User,
    Token,
    LearnRequest,
    MappingEntry,
)
from .auth import (
    authenticate_user,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    require_role,
    FAKE_USERS_DB,
)
from fastapi.security import OAuth2PasswordRequestForm
from .command_ledger import CommandLedger
from .registry import AssetTransferWorker, MediaRegistry, NodeRegistry, TransferTask, TranscodeQueue
from .timeline_repository import TimelineRepository
from .collaboration import CollaborationManager
from .io.osc_server import OSCServer
from .io.midi_handler import MIDIHandler
from .io.midi_osc_mapper import MidiOscMapper
from .io.artnet_server import ArtNetServer, ArtNetToLayerMapper
from .io.artnet_sender import ArtNetSender
from .io.psn_listener import PSNListener
from .cluster_manager import ClusterManager
from .services.transcoder import TranscodeWorker
from .services.archiver import ArchiverService
from .services.cloud_sync import CloudSyncService
from .io.ltc_reader import LTCReader, LTCSyncMode
from .metadata_extractor import MetadataExtractor
from .media_browser import MediaBrowser
from .services.file_watcher import FileWatcherService
from .services.logger import ShowLogger
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo, ServiceListener

app = FastAPI(
    title="StageCanvas Orchestration Server",
)
logger = logging.getLogger("orchestration")
registry = NodeRegistry()
MEDIA_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "media"
THUMBNAIL_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "thumbnails"
RENDER_CACHE_DIR = Path(__file__).resolve().parents[2] / "render-node" / "data" / "cache"

MEDIA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
RENDER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
media_registry = MediaRegistry(Path(__file__).resolve().parent.parent / "data" / "media_registry.json")
transcode_queue = TranscodeQueue()
transfer_worker = AssetTransferWorker(
    registry,
    media_registry=media_registry,
    media_root=MEDIA_STORAGE_DIR,
    cache_root=RENDER_CACHE_DIR,
)
timeline_repo = TimelineRepository(Path(__file__).resolve().parent.parent / "data" / "timeline.db")
command_ledger = CommandLedger(Path(__file__).resolve().parent.parent / "data" / "orchestration.db")
trigger_rules: dict[str, TriggerRule] = {}
trigger_events: list[TriggerEvent] = []
TRIGGER_EVENT_LIMIT = 200
preview_image_last_request: dict[str, int] = {}
osc_server: OSCServer | None = None
midi_handler: MIDIHandler | None = None
artnet_server: ArtNetServer | None = None
artnet_sender: ArtNetSender | None = None
cluster_manager: ClusterManager | None = None
transcode_worker: TranscodeWorker | None = None
archiver_service: ArchiverService | None = None
zeroconf: Zeroconf | None = None
ltc_reader: LTCReader | None = None
show_logger = ShowLogger(log_dir=str(Path(__file__).resolve().parent.parent / "data" / "logs"))
midi_osc_mapper: MidiOscMapper | None = None

# SC-112: Stateful logic tracking
logic_state: dict[str, int] = {}

async def _fire_trigger_internal(rule: TriggerRule, fire_payload: dict[str, Any], source: str):
    """Processes a trigger rule with LogicConfig (SC-112)."""
    logic = rule.logic
    full_payload = {**rule.payload, **fire_payload}
    
    # 1. Condition Check
    if logic and logic.condition:
        # Very simple safe eval for "payload.x > 0.5" type strings
        # In production, use a real expression parser.
        try:
            # Mock evaluation: if condition contains 'value >' compare it
            if ">" in logic.condition:
                parts = logic.condition.split(">")
                if len(parts) == 2:
                    key, val = parts
                    key = key.replace("payload.", "").strip()
                    if float(full_payload.get(key, 0)) <= float(val):
                        return
        except Exception:
            logger.warning(f"[logic] Condition evaluation failed for {rule.rule_id}")
            return

    # 2. Counter Logic
    if logic and logic.counter_target:
        current = logic_state.get(rule.rule_id, 0) + 1
        logic_state[rule.rule_id] = current
        if current < logic.counter_target:
            logger.info(f"[logic] Counter {rule.rule_id}: {current}/{logic.counter_target}")
            return
        logic_state[rule.rule_id] = 0 # Reset

    # 3. Delay Logic
    async def execute():
        if logic and logic.delay_ms:
            await asyncio.sleep(logic.delay_ms / 1000.0)
        
        event = TriggerEvent(
            event_id=f"evt-{rule.rule_id}-{int(time.time() * 1000)}",
            rule_id=rule.rule_id,
            source=source,
            cue_id=rule.cue_id,
            payload=full_payload,
            timestamp_ms=int(time.time() * 1000),
        )
        trigger_events.append(event)
        if len(trigger_events) > TRIGGER_EVENT_LIMIT:
            del trigger_events[0 : len(trigger_events) - TRIGGER_EVENT_LIMIT]
        logger.info(f"[logic] Fired trigger: {rule.rule_id} from {source}")
        show_logger.log_cue(rule.show_id or "unknown", rule.cue_id or "unknown", full_payload)

    if logic and logic.delay_ms:
        asyncio.create_task(execute())
    else:
        await execute()
cloud_sync: CloudSyncService | None = None
file_watcher: FileWatcherService | None = None

class NodeDiscoveryListener(ServiceListener):
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"[discovery] Service {name} removed")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            node_id = info.properties.get(b"node_id", b"unknown").decode("utf-8")
            label = info.properties.get(b"label", b"").decode("utf-8")
            print(f"[discovery] Found node {node_id} ({label}) at {info.parsed_addresses()}")
            # Auto-register node
            asyncio.create_task(registry.register(RegisterNodeRequest(
                node_id=node_id,
                label=label,
                capabilities={"discovered": True, "address": info.parsed_addresses()[0] if info.parsed_addresses() else None}
            )))
psn_listener: PSNListener | None = None
collaboration_manager = CollaborationManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(FAKE_USERS_DB, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


async def _transfer_loop() -> None:
    while True:
        ran = await transfer_worker.run_once()
        await asyncio.sleep(0.05 if ran else 0.2)


@app.on_event("startup")
async def _startup() -> None:
    global osc_server, midi_handler, artnet_server, psn_listener, cluster_manager
    global artnet_sender, transcode_worker, zeroconf, ltc_reader, archiver_service, cloud_sync, file_watcher, midi_osc_mapper
    app.state.transfer_task = asyncio.create_task(_transfer_loop())

    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
    archiver_service = ArchiverService(DATA_DIR)
    
    AUTO_IMPORT_DIR = DATA_DIR / "auto_import"
    file_watcher = FileWatcherService(AUTO_IMPORT_DIR, media_registry)
    file_watcher.start(asyncio.get_running_loop())
    
    # [MOVED TO MODULE LEVEL] logic_state, _fire_trigger_internal

    # MidiOscMapper initialization
    async def mapper_dispatch(cmd: ControlCommand):
        target_ids = await registry.active_node_ids()
        await _dispatch_to_nodes(cmd, target_ids)

    midi_osc_mapper = MidiOscMapper(
        db_path=DATA_DIR / "orchestration.db",
        dispatch_callback=mapper_dispatch
    )

    # Internal trigger callback for OSC
    async def osc_trigger_callback(payload: dict):
        body = TriggerFireRequest(**payload)
        rule = trigger_rules.get(body.rule_id)
        if rule is not None:
            await _fire_trigger_internal(rule, body.payload, "osc")
        if midi_osc_mapper:
            val = body.payload.get("value", 1.0) if "value" in body.payload else 1.0
            # For mapping, the raw address is usually the rule_id, so we just use that.
            await midi_osc_mapper.handle_signal("osc", f"/{body.rule_id}", float(val))

    artnet_sender = ArtNetSender()

    osc_port = int(os.environ.get("OSC_PORT", 8000))
    osc_server = OSCServer(host="0.0.0.0", port=osc_port, trigger_callback=osc_trigger_callback)
    await osc_server.start()

    # CC callback for MIDI
    async def midi_cc_callback(control: int, value: int):
        print(f"[main] Received MIDI CC {control} = {value}")
        if midi_osc_mapper:
            await midi_osc_mapper.handle_signal("midi_cc", f"cc:{control}", value / 127.0)

    midi_handler = MIDIHandler(trigger_callback=None, cc_callback=midi_cc_callback)
    midi_handler.start(asyncio.get_running_loop())

    # Layer update callback for ArtNet
    async def artnet_update_callback(layers: list[dict[str, Any]]):
        command = ControlCommand(
            version=PROTOCOL_VERSION,
            command="UPDATE_LAYERS",
            payload={"layers": layers},
            seq=command_ledger.next_seq(),
            origin="artnet",
        )
        await broadcast_command(command)

    artnet_mapper = ArtNetToLayerMapper(update_callback=artnet_update_callback)
    artnet_server = ArtNetServer(dmx_callback=artnet_mapper.handle_dmx)
    await artnet_server.start()

    # Spatial Tracking callback for PSN
    async def psn_tracking_callback(tracker_id: int, coords: dict[str, float]):
        # Map tracker coordinates to layer properties
        # For demo, mapping Tracker 1 to a specific layer's X/Y
        if tracker_id == 1:
            layers_data = [{
                "layer_id": "layer-tracking-mask",
                "kind": "video",
                "transform": {
                    "x": coords["x"] * 0.001,
                    "y": coords["y"] * 0.001
                }
            }]
            cmd = ControlCommand(
                version=PROTOCOL_VERSION,
                command="UPDATE_LAYERS",
                payload={"layers": layers_data},
                seq=command_ledger.next_seq(),
                origin="psn",
            )
            await broadcast_command(cmd)

    psn_listener = PSNListener(tracking_callback=psn_tracking_callback)
    await psn_listener.start()

    role = os.environ.get("CLUSTER_ROLE", "PRIMARY").upper()
    primary_url = os.environ.get("PRIMARY_URL")
    cluster_manager = ClusterManager(role=role, primary_url=primary_url)
    await cluster_manager.start()

    # Transcoder
    async def transcode_progress_callback(job_id: str, progress: float):
        await transcode_queue.update(job_id, progress=progress)

    transcode_worker = TranscodeWorker(
        transcode_queue=transcode_queue,
        media_registry=media_registry,
        media_root=MEDIA_STORAGE_DIR,
        progress_callback=transcode_progress_callback
    )
    app.state.transcode_task = asyncio.create_task(transcode_worker.run_loop())

    # Zeroconf Discovery
    global zeroconf
    zeroconf = Zeroconf()
    listener = NodeDiscoveryListener()
    browser = ServiceBrowser(zeroconf, "_stagecanvas._tcp.local.", listener)

    # SMPTE LTC Reader (SC-100)
    async def ltc_timecode_callback(position_ms: int, mode: str) -> None:
        # CHASE mode: continuously push PLAY_AT to all nodes when LTC ticks
        # JAM/FREE_WHEEL: only do so on initial lock
        if mode == "chase":
            # Throttle: only dispatch every ~100 ms to avoid flooding
            now = int(time.time() * 1000)
            last = getattr(app.state, "ltc_last_dispatch_ms", 0)
            if now - last < 100:
                return
            app.state.ltc_last_dispatch_ms = now
        command = ControlCommand(
            version=PROTOCOL_VERSION,
            command="SEEK",
            payload={"position_ms": position_ms, "source": "ltc", "mode": mode},
            seq=command_ledger.next_seq(),
            origin="system",
        )
        await broadcast_command(command)
        logger.info(f"[ltc] dispatched SEEK position_ms={position_ms} mode={mode}")

    ltc_fps = float(os.environ.get("LTC_FPS", "25"))
    ltc_mode_str = os.environ.get("LTC_MODE", "chase")
    ltc_mode = LTCSyncMode(ltc_mode_str) if ltc_mode_str in ("chase", "jam_sync", "free_wheel") else LTCSyncMode.CHASE
    global ltc_reader
    ltc_reader = LTCReader(fps=ltc_fps, sync_mode=ltc_mode, callback=ltc_timecode_callback, simulate=True)
    await ltc_reader.start()

    # Cloud Sync Service (SC-111)
    global cloud_sync
    cloud_sync = CloudSyncService(data_dir=Path(__file__).resolve().parent.parent / "data")
    app.state.cloud_sync_task = asyncio.create_task(cloud_sync.start_background_sync())
    
    print("[main] Startup sequence complete.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    global osc_server, midi_handler, artnet_server, psn_listener, cluster_manager
    global cloud_sync, file_watcher
    if file_watcher:
        file_watcher.stop()
    task = getattr(app.state, "transfer_task", None)
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    if osc_server:
        osc_server.stop()
    if midi_handler:
        midi_handler.stop()
    if artnet_server:
        artnet_server.stop()
    if psn_listener:
        psn_listener.stop()
    if cluster_manager:
        await cluster_manager.stop()
    if transcode_worker:
        transcode_worker.stop()
    if zeroconf:
        zeroconf.close()
    if ltc_reader:
        await ltc_reader.stop()
    cloud_sync_task = getattr(app.state, "cloud_sync_task", None)
    if cloud_sync_task is not None:
        cloud_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await cloud_sync_task
    if cloud_sync:
        await cloud_sync.stop()


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "role": cluster_manager.role if cluster_manager else "unknown"}


@app.get("/api/v1/cluster/heartbeat")
async def cluster_heartbeat() -> dict[str, str]:
    return {"status": "ok", "role": cluster_manager.role if cluster_manager else "unknown"}


@app.post("/api/v1/nodes/register", dependencies=[Depends(require_role(["admin"]))])
async def register_node(body: RegisterNodeRequest) -> dict[str, object]:
    record = await registry.register(body)
    return {
        "ok": True,
        "node_id": record.node_id,
        "connected": record.connected,
        "status": record.status,
    }


@app.post("/api/v1/nodes/{node_id}/heartbeat", tags=["nodes"])
async def node_heartbeat(node_id: str, body: HeartbeatRequest) -> dict[str, Any]:
    """Receive heartbeat and performance metrics from a render node."""
    record = await registry.heartbeat(node_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    
    # SC-124: Log drift if exceeding threshold
    if abs(body.drift_ms) > 2.0:
        level = "CRITICAL" if abs(body.drift_ms) > 10.0 else "WARN"
        show_logger.log_drift(node_id, body.drift_ms, level)

    return {"ok": True, "node_id": node_id, "status": record.status, "drift_ms": record.drift_ms}


@app.get("/api/v1/nodes", tags=["nodes"])
async def list_nodes() -> dict[str, Any]:
    """List all registered render nodes and their status."""
    return {"nodes": await registry.list_nodes()}


# ---------------------------------------------------------------------------
# SC-115 MEDIA BROWSER ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/api/v1/browser/list", tags=["media"], dependencies=[Depends(require_role(["admin", "designer"]))])
async def browser_list_directory(path: str = str(Path.home())) -> dict[str, Any]:
    """Securely list files and folders on the local system."""
    return MediaBrowser.list_directory(path)

@app.get("/api/v1/media/thumbnails/{asset_id}", tags=["media"])
async def get_media_thumbnail(asset_id: str):
    """Serve the generated thumbnail for a media asset."""
    thumb_path = THUMBNAIL_STORAGE_DIR / f"{asset_id}.jpg"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(thumb_path, media_type="image/jpeg")

@app.post("/api/v1/media/ingest_local", tags=["media"], dependencies=[Depends(require_role(["admin"]))])
async def ingest_local_file(path: str, asset_id: Optional[str] = None, label: Optional[str] = None) -> dict[str, Any]:
    """Ingest a file already present on the local disk."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=400, detail="Invalid file path")
        
    actual_asset_id = asset_id or hashlib.md5(str(p).encode()).hexdigest()[:12]
    
    # Extract metadata
    meta = MetadataExtractor.get_metadata(str(p))
    
    # Generate thumbnail
    thumb_path = THUMBNAIL_STORAGE_DIR / f"{actual_asset_id}.jpg"
    MetadataExtractor.generate_thumbnail(str(p), str(thumb_path))
    
    # Register in registry
    request = MediaAssetCreateRequest(
        asset_id=actual_asset_id,
        label=label or p.name,
        codec_profile="generic", # Could be refined
        duration_ms=meta.get("duration_ms", 0),
        size_bytes=meta.get("size_bytes", p.stat().st_size),
        checksum="local-ingest", 
        uri=f"file://{p.resolve()}",
        status="READY",
    )
    
    record, is_new, idempotent = await media_registry.register(request)
    return {"ok": True, "asset": record.to_response().model_dump(mode="json"), "metadata": meta}


@app.get("/api/v1/nodes/{node_id}/drift_history", tags=["nodes"])
async def node_drift_history(node_id: str) -> dict[str, object]:
    """Retrieve the drift history for a specific render node."""
    record = await registry.get(node_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return {"node_id": node_id, "history": await registry.get_drift_history(node_id)}


@app.post("/api/v1/preview/snapshot", tags=["preview"], dependencies=[Depends(require_role(["operator"]))])
async def preview_snapshot(body: PreviewSnapshotRequest) -> dict[str, object]:
    """Request a snapshot of the current state from render nodes."""
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


@app.post("/api/v1/preview/image", tags=["preview"], dependencies=[Depends(require_role(["operator"]))])
async def preview_image(body: PreviewImageRequest) -> dict[str, object]:
    """Request a preview image from render nodes."""
    target_ids = body.node_ids or await registry.active_node_ids()
    now_ms = int(time.time() * 1000)
    images: list[dict[str, object]] = []
    for node_id in target_ids:
        preview_image_last_request[node_id] = now_ms
        images.append(
            {
                "node_id": node_id,
                "timestamp_ms": now_ms,
                "width": body.width,
                "height": body.height,
                "image_data": "data:image/png;base64,stub",
            }
        )
    return {"ok": True, "requested_count": len(target_ids), "images": images}


@app.post("/api/v1/media", tags=["media"], dependencies=[Depends(require_role(["admin"]))])
async def register_media_asset(body: MediaAssetCreateRequest) -> dict[str, object]:
    """Register a new media asset."""
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


@app.get("/api/v1/media", tags=["media"])
async def list_media_assets() -> dict[str, Any]:
    """List all media assets in the registry."""
    assets = await media_registry.list_assets()
    return {"assets": [asset.model_dump(mode="json") for asset in assets]}


@app.get("/api/v1/media/{asset_id}", tags=["media"])
async def get_media_asset(asset_id: str) -> dict[str, Any]:
    record = await media_registry.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {"asset": record.to_response().model_dump(mode="json")}


@app.patch("/api/v1/media/{asset_id}", tags=["media"], dependencies=[Depends(require_role(["admin"]))])
async def update_media_asset(asset_id: str, body: MediaAssetUpdateRequest) -> dict[str, Any]:
    """Update metadata for an existing media asset."""
    record = await media_registry.update(asset_id, body)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {"ok": True, "asset": record.to_response().model_dump(mode="json")}


@app.post("/api/v1/media/{asset_id}/transcode", tags=["media"], dependencies=[Depends(require_role(["admin"]))])
async def enqueue_transcode_job(asset_id: str, body: TranscodeJobCreateRequest) -> dict[str, Any]:
    """Enqueue a background transcoding job for a specific asset."""
    record = await media_registry.get(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    job = await transcode_queue.enqueue(asset_id=asset_id, target_profile=body.target_profile)
    return {"ok": True, "job": job.to_response().model_dump(mode="json")}


@app.get("/api/v1/transcode/jobs", tags=["media"])
async def list_transcode_jobs() -> dict[str, Any]:
    """List all current background transcoding jobs."""
    jobs = await transcode_queue.list_jobs()
    return {"jobs": [job.model_dump(mode="json") for job in jobs]}


@app.get("/api/v1/transcode/jobs/{job_id}", tags=["media"])
async def get_transcode_job(job_id: str) -> dict[str, Any]:
    """Retrieve details and progress of a specific transcoding job."""
    job = await transcode_queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Transcode job not found: {job_id}")
    return {"job": job.to_response().model_dump(mode="json")}


# ---------------------------------------------------------------------------
# SC-109 ARCHIVE ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/api/v1/archive/export", tags=["archive"], dependencies=[Depends(require_role(["admin"]))])
async def start_archive_export() -> dict[str, Any]:
    """Start bundling the current show into a portable .stage archive."""
    if archiver_service is None:
        raise HTTPException(status_code=503, detail="Archiver service not available")
    job_id = await archiver_service.create_export_job()
    return {"ok": True, "job_id": job_id}


@app.post("/api/v1/archive/import", tags=["archive"], dependencies=[Depends(require_role(["admin"]))])
async def start_archive_import(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a .stage archive to replace the current session state."""
    if archiver_service is None:
        raise HTTPException(status_code=503, detail="Archiver service not available")
        
    import uuid
    tmp_path = archiver_service.archives_dir / f"upload_{uuid.uuid4().hex}.stage"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
        
    job_id = await archiver_service.create_import_job(tmp_path)
    return {"ok": True, "job_id": job_id}


@app.get("/api/v1/archive/jobs/{job_id}", tags=["archive"])
async def get_archive_job(job_id: str) -> dict[str, Any]:
    """Check the status of an ongoing export or import job."""
    if archiver_service is None:
        raise HTTPException(status_code=503, detail="Archiver service not available")
    job = archiver_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job.model_dump(mode="json")}


@app.get("/api/v1/archive/download/{filename}", tags=["archive"])
async def download_archive(filename: str):
    """Download a completed .stage archive."""
    if archiver_service is None:
        raise HTTPException(status_code=503, detail="Archiver service not available")
    file_path = archiver_service.archives_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archive not found")
    return FileResponse(path=file_path, filename=filename, media_type="application/zip")


# ---------------------------------------------------------------------------
# MEDIA TRANSFER (Operator -> Nodes)
@app.patch("/api/v1/transcode/jobs/{job_id}")
async def update_transcode_job(job_id: str, body: TranscodeJobUpdateRequest) -> dict[str, object]:
    job = await transcode_queue.update(job_id, status=body.status, error_message=body.error_message)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Transcode job not found: {job_id}")
    return {"ok": True, "job": job.to_response().model_dump(mode="json")}


@app.post("/api/v1/media/upload", dependencies=[Depends(require_role(["admin"]))])
async def upload_media_asset(request: Request) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=415,
            detail={"reason_code": "UNSUPPORTED_MEDIA_TYPE", "message": "Expected multipart/form-data upload."},
        )
    fields, upload = _parse_multipart_formdata(content_type, await request.body())
    asset_id = fields.get("asset_id")
    codec_profile = fields.get("codec_profile")
    duration_ms_raw = fields.get("duration_ms", "0")
    label = fields.get("label")
    if not asset_id or not codec_profile or upload is None:
        raise HTTPException(
            status_code=400,
            detail={"reason_code": "MISSING_FIELDS", "message": "asset_id, codec_profile, and file are required."},
        )
    filename, file_bytes = upload
    if not filename:
        raise HTTPException(
            status_code=400,
            detail={"reason_code": "MISSING_FILENAME", "message": "Uploaded file must include a filename."},
        )

    MEDIA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    target_path = MEDIA_STORAGE_DIR / f"{asset_id}_{safe_name}"

    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    size_bytes = len(file_bytes)
    with target_path.open("wb") as handle:
        handle.write(file_bytes)

    checksum = hasher.hexdigest()
    
    # SC-116: Extract metadata and generate thumbnail
    meta = MetadataExtractor.get_metadata(str(target_path))
    thumb_path = THUMBNAIL_STORAGE_DIR / f"{asset_id}.jpg"
    MetadataExtractor.generate_thumbnail(str(target_path), str(thumb_path))
    
    try:
        request = MediaAssetCreateRequest(
            asset_id=asset_id,
            label=label or safe_name,
            codec_profile=codec_profile,
            duration_ms=meta.get("duration_ms", int(duration_ms_raw) or 0),
            size_bytes=size_bytes,
            checksum=checksum,
            uri=f"file://{target_path}",
            status="READY",
        )
    except Exception as exc:
        if "UNSUPPORTED_CODEC_PROFILE" in str(exc):
            raise HTTPException(
                status_code=422,
                detail={"reason_code": "UNSUPPORTED_CODEC_PROFILE", "message": str(exc)},
            ) from exc
        raise
    record, is_new, idempotent = await media_registry.register(request)
    if not idempotent:
        raise HTTPException(
            status_code=409,
            detail={
                "reason_code": "ASSET_ID_MISMATCH",
                "message": "Asset ID already exists with different metadata.",
            },
        )
    return {"ok": True, "asset": record.to_response().model_dump(mode="json"), "idempotent": not is_new}


@app.post("/api/v1/triggers/register", tags=["io"], dependencies=[Depends(require_role(["designer"]))])
async def register_trigger_rule(body: TriggerRegisterRequest) -> dict[str, Any]:
    """Register a new external trigger rule (OSC, MIDI, or ArtNet)."""
    rule = TriggerRule(
        rule_id=body.rule_id,
        name=body.name,
        source=body.source,
        cue_id=body.cue_id,
        payload=body.payload,
        logic=body.logic, # SC-112
    )
    trigger_rules[rule.rule_id] = rule
    return {"ok": True, "rule": rule.model_dump(mode="json")}


@app.get("/api/v1/triggers/rules", tags=["io"])
async def list_trigger_rules() -> dict[str, Any]:
    """List all active trigger rules."""
    return {"rules": [rule.model_dump(mode="json") for rule in trigger_rules.values()]}


@app.post("/api/v1/triggers/fire", tags=["io"], dependencies=[Depends(require_role(["operator"]))])
async def fire_trigger(body: TriggerFireRequest) -> dict[str, Any]:
    """Manually fire a trigger rule."""
    rule = trigger_rules.get(body.rule_id)
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail={"reason_code": "TRIGGER_RULE_NOT_FOUND", "message": f"Rule not found: {body.rule_id}"},
        )
    
    # Use the logic-aware internal function (SC-112)
    # We call it without awaiting if there's a delay, to return HTTP 202-like success immediately.
    await _fire_trigger_internal(rule, body.payload, "http")
    return {"ok": True, "event_status": "QUEUED" if rule.logic and rule.logic.delay_ms else "FIRED"}


@app.get("/api/v1/triggers/events", tags=["io"])
async def list_trigger_events() -> dict[str, Any]:
    """Retrieve the recent history of fired trigger events."""
    return {"events": [event.model_dump(mode="json") for event in trigger_events]}


from pydantic import BaseModel

class DMXBroadcastRequest(BaseModel):
    dmx_payloads: dict[str, str]

@app.post("/api/v1/io/dmx/broadcast", tags=["io"], dependencies=[Depends(require_role(["operator"]))])
async def broadcast_dmx(body: DMXBroadcastRequest) -> dict[str, Any]:
    """Broadcast raw DMX data (universes with hex-encoded byte payloads) over ArtNet."""
    if not artnet_sender:
        raise HTTPException(status_code=503, detail="ArtNetSender not initialized")
    
    for universe_str, hex_payload in body.dmx_payloads.items():
        try:
            universe = int(universe_str)
            data = bytes.fromhex(hex_payload)
            artnet_sender.send_universe(universe, data)
        except Exception:
            # Silently skip malformed data for performance
            continue
            
    return {"ok": True}


@app.get("/api/v1/slo")
async def slo_snapshot() -> dict[str, object]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "drift_slo": await registry.drift_summary(),
        "play_at_min_lead_ms": MIN_PLAY_AT_LEAD_MS,
    }


@app.get("/api/v1/timeline/snapshot", tags=["shows"], response_model=TimelineSnapshotResponse)
async def timeline_snapshot(show_id: str = "demo-show") -> TimelineSnapshotResponse:
    """Get the full state snapshot of a show's timeline."""
    nodes = await registry.list_nodes()
    playhead_ms = 0
    if nodes:
        playhead_ms = max(int(node.get("position_ms", 0)) for node in nodes)
    try:
        return timeline_repo.snapshot(show_id=show_id, playhead_ms=playhead_ms)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/timeline/shows", tags=["shows"], response_model=list[TimelineShowSummary])
async def timeline_list_shows() -> list[TimelineShowSummary]:
    """List all shows in the timeline repository."""
    return timeline_repo.list_shows()


@app.put("/api/v1/timeline/shows/{show_id}", dependencies=[Depends(require_role(["designer"]))])
async def timeline_upsert_show(show_id: str, body: TimelineUpsertShowRequest) -> dict[str, object]:
    mapping_payload = None
    if body.mapping_config is not None:
        mapping_payload = body.mapping_config.model_dump(mode="json")
        _validate_mapping_config_from_payload({"mapping_config": mapping_payload})
    timeline_repo.upsert_show(show_id=show_id, duration_ms=body.duration_ms, mapping_config=mapping_payload)
    return {"ok": True, "show_id": show_id}


@app.delete("/api/v1/timeline/shows/{show_id}", dependencies=[Depends(require_role(["designer"]))])
async def timeline_delete_show(show_id: str) -> dict[str, object]:
    try:
        timeline_repo.delete_show(show_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id}


@app.put("/api/v1/timeline/shows/{show_id}/tracks/{track_id}", dependencies=[Depends(require_role(["designer"]))])
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


@app.delete("/api/v1/timeline/shows/{show_id}/tracks/{track_id}", dependencies=[Depends(require_role(["designer"]))])
async def timeline_delete_track(show_id: str, track_id: str) -> dict[str, object]:
    try:
        timeline_repo.delete_track(show_id=show_id, track_id=track_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id}


@app.put("/api/v1/timeline/shows/{show_id}/tracks/{track_id}/clips/{clip_id}", dependencies=[Depends(require_role(["designer"]))])
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
            offset_ms=body.offset_ms,
            layers=body.layers,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "show_id": show_id, "track_id": track_id, "clip_id": clip_id}


@app.delete("/api/v1/timeline/shows/{show_id}/tracks/{track_id}/clips/{clip_id}", dependencies=[Depends(require_role(["designer"]))])
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

    show_id = body.show_id
    payload = {
        "show_id": show_id,
        "preload_only": True,
        "request_id": body.request_id,
        "assets": [asset.model_dump(mode="json", exclude_none=True) for asset in body.assets],
    }

    # SC-092: Ensure mapping_config is included for canvas splitting
    try:
        mapping_config = timeline_repo.get_mapping_config(str(show_id))
    except KeyError:
        mapping_config = None
    if mapping_config:
        payload["mapping_config"] = mapping_config

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="LOAD_SHOW",
        payload=payload,
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


@app.post("/api/v1/operators/pause", dependencies=[Depends(require_role(["operator"]))])
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


@app.post("/api/v1/operators/stop", dependencies=[Depends(require_role(["operator"]))])
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


@app.post("/api/v1/operators/load_show", dependencies=[Depends(require_role(["operator"]))])
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


@app.post("/api/v1/operators/seek", dependencies=[Depends(require_role(["operator"]))])
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


@app.post("/api/v1/operators/hot_swap", dependencies=[Depends(require_role(["operator"]))])
async def operator_hot_swap(body: OperatorCommandRequest) -> dict[str, object]:
    """Replace an active layer's source asset on the fly (SC-119)."""
    replay = _idempotent_begin_or_raise(
        scope="operator_hot_swap",
        request_id=body.request_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    if replay is not None:
        return replay

    command = ControlCommand(
        version=PROTOCOL_VERSION,
        command="HOT_SWAP",
        payload=body.payload,
        seq=command_ledger.next_seq(),
        origin="operator",
    )
    target_ids = body.node_ids or await registry.active_node_ids()
    result = await _dispatch_to_nodes(command, target_ids)
    command_ledger.finalize_request("operator_hot_swap", body.request_id, result)
    
    # SC-124: Log hot-swap
    show_logger.log_swap(
        target_ids[0] if target_ids else "ALL", 
        body.payload.get("layer_id", "unknown"), 
        body.payload.get("media_id", "unknown")
    )

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
                    "transcode_jobs": [job.model_dump(mode="json") for job in await transcode_queue.list_jobs()],
                    "ltc_status": {
                        "mode": ltc_reader.sync_mode.value if ltc_reader else "off",
                        "fps": ltc_reader.fps if ltc_reader else 0,
                        "timecode_ms": ltc_reader.timecode_ms if ltc_reader else 0,
                        "locked": ltc_reader.locked if ltc_reader else False,
                        "last_frame_str": ltc_reader.last_frame_str if ltc_reader else "00:00:00:00",
                    } if ltc_reader else None,
                    "drift_slo": await registry.drift_summary(),
                    "play_at_min_lead_ms": MIN_PLAY_AT_LEAD_MS,
                    "locks": collaboration_manager.get_locks(),
                }
            )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return


def _parse_multipart_formdata(content_type: str, body: bytes) -> tuple[dict[str, str], tuple[str, bytes] | None]:
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)
    fields: dict[str, str] = {}
    upload: tuple[str, bytes] | None = None
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_param("filename", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            upload = (filename, payload)
        elif name is not None:
            fields[name] = payload.decode("utf-8")
    return fields, upload


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
@app.get("/api/v1/ltc/status", tags=["io"], response_model=LTCStatusResponse)
async def get_ltc_status() -> LTCStatusResponse:
    """Get the current state of the SMPTE LTC reader."""
    if not ltc_reader:
        raise HTTPException(status_code=503, detail="LTC Reader not initialized")
    return LTCStatusResponse(
        mode=ltc_reader.sync_mode.value,
        fps=ltc_reader.fps,
        timecode_ms=ltc_reader.timecode_ms,
        locked=ltc_reader.locked,
        last_frame_str=ltc_reader.last_frame_str,
        simulate=ltc_reader.simulate
    )


@app.post("/api/v1/ltc/mode", tags=["io"], response_model=dict[str, Any], dependencies=[Depends(require_role(["operator"]))])
async def set_ltc_mode(body: LTCSetModeRequest) -> dict[str, Any]:
    """Change the LTC sync mode and frame rate at runtime."""
    if not ltc_reader:
        raise HTTPException(status_code=503, detail="LTC Reader not initialized")
    
    ltc_reader.set_mode(LTCSyncMode(body.mode), fps=body.fps)
    return {
        "ok": True,
        "mode": ltc_reader.sync_mode.value,
        "fps": ltc_reader.fps
    }


@app.post("/api/v1/io/learn/start", tags=["io"], dependencies=[Depends(require_role(["designer", "admin"]))])
async def start_learning(body: LearnRequest):
    if midi_osc_mapper:
        midi_osc_mapper.start_learning(body.target_layer_id, body.target_property)
    return {"ok": True}

@app.post("/api/v1/io/learn/stop", tags=["io"], dependencies=[Depends(require_role(["designer", "admin"]))])
async def stop_learning():
    if midi_osc_mapper:
        midi_osc_mapper.stop_learning()
    return {"ok": True}

@app.get("/api/v1/io/mappings", tags=["io"], response_model=list[MappingEntry])
async def get_mappings() -> list[MappingEntry]:
    if midi_osc_mapper:
        return midi_osc_mapper.get_mappings()
    return []


@app.post("/api/v1/collaboration/lock", tags=["collaboration"], dependencies=[Depends(require_role(["operator"]))])
async def take_lock(body: LockRequest) -> dict[str, object]:
    success = collaboration_manager.take_lock(body.resource_id, body.user_id)
    return {"ok": success, "locks": collaboration_manager.get_locks()}


@app.delete("/api/v1/collaboration/lock", dependencies=[Depends(require_role(["operator"]))])
async def release_lock(body: LockRequest) -> dict[str, object]:
    success = collaboration_manager.release_lock(body.resource_id, body.user_id)
    return {"ok": success, "locks": collaboration_manager.get_locks()}


@app.get("/api/v1/collaboration/locks")
async def list_locks() -> dict[str, object]:
    return {"ok": True, "locks": collaboration_manager.get_locks()}
@app.get("/api/v1/logs/export", tags=["diagnostics"], dependencies=[Depends(require_role(["admin"]))])
async def export_logs():
    """Download the main show operations log file."""
    log_path = Path(show_logger.log_path)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    return FileResponse(log_path, filename="show_operations.log", media_type="text/plain")

@app.get("/api/v1/logs/live", tags=["diagnostics"])
async def get_live_logs():
    """Get the last 100 log entries for the live dashboard."""
    return {"logs": show_logger.get_live_logs()}

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """Real-time show log stream for the operator dashboard."""
    await websocket.accept()
    
    # Send backlog
    for entry in show_logger.get_live_logs():
        await websocket.send_json(entry)
        
    queue = asyncio.Queue()
    show_logger.add_callback(queue.put_nowait)
    
    try:
        while True:
            entry = await queue.get()
            await websocket.send_json(entry)
    except WebSocketDisconnect:
        show_logger.remove_callback(queue.put_nowait)
    except Exception:
        show_logger.remove_callback(queue.put_nowait)

import os
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..models import MediaAssetCreateRequest, MediaAssetUpdateRequest
from ..registry import MediaRegistry
from ..metadata_extractor import MetadataExtractor
from ..media_browser import MediaBrowser

logger = logging.getLogger(__name__)

class AutoImportHandler(FileSystemEventHandler):
    def __init__(self, registry: MediaRegistry, loop: asyncio.AbstractEventLoop):
        self.registry = registry
        self.loop = loop
        self._pending_tasks: Dict[str, asyncio.Task] = {}

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and MediaBrowser.is_media_file(event.src_path):
            self._debounce_event("register", event.src_path)

    def on_moved(self, event: FileSystemEvent):
        # If moved into our watch dir
        if not event.is_directory and MediaBrowser.is_media_file(event.dest_path):
            self._debounce_event("register", event.dest_path)
        # If moved out of our watch dir
        if not event.is_directory and MediaBrowser.is_media_file(event.src_path):
            self._debounce_event("delete", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and MediaBrowser.is_media_file(event.src_path):
            self._debounce_event("delete", event.src_path)

    def _debounce_event(self, action: str, file_path: str):
        key = f"{action}:{file_path}"
        if key in self._pending_tasks:
            self._pending_tasks[key].cancel()
        
        self._pending_tasks[key] = self.loop.create_task(self._process_event_async(action, file_path))

    async def _process_event_async(self, action: str, file_path: str):
        # Wait a bit to ensure file is fully copied
        await asyncio.sleep(2.0)
        
        try:
            path = Path(file_path)
            asset_id = path.name # Simplified ID for now, maybe use hash later
            
            if action == "register":
                if not path.exists():
                    return
                
                logger.info(f"[watcher] Registering new asset: {path.name}")
                meta = MetadataExtractor.get_metadata(str(path))
                
                request = MediaAssetCreateRequest(
                    asset_id=asset_id,
                    label=path.stem,
                    codec_profile=meta.get("codec", "unknown"),
                    duration_ms=meta.get("duration_ms", 0),
                    size_bytes=meta.get("size_bytes", 0),
                    uri=f"file://{path.absolute()}",
                    status="READY"
                )
                await self.registry.register(request)
                
            elif action == "delete":
                logger.info(f"[watcher] Marking asset as MISSING: {path.name}")
                # We don't delete from registry, just mark as MISSING per SC-117
                await self.registry.update(asset_id, MediaAssetUpdateRequest(status="MISSING"))
                
        except Exception as e:
            logger.error(f"[watcher] Error processing {action} for {file_path}: {e}")
        finally:
            key = f"{action}:{file_path}"
            self._pending_tasks.pop(key, None)

class FileWatcherService:
    def __init__(self, watch_dir: Path, registry: MediaRegistry):
        self.watch_dir = watch_dir
        self.registry = registry
        self.observer = Observer()
        self.handler = None

    def start(self, loop: asyncio.AbstractEventLoop):
        if not self.watch_dir.exists():
            self.watch_dir.mkdir(parents=True, exist_ok=True)
        
        self.handler = AutoImportHandler(self.registry, loop)
        self.observer.schedule(self.handler, str(self.watch_dir), recursive=False)
        self.observer.start()
        logger.info(f"[watcher] Started monitoring {self.watch_dir}")

    def stop(self):
        self.observer.stop()
        self.observer.join()
        logger.info("[watcher] Stopped monitoring")

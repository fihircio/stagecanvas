from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, Any

import ffmpeg
from ..registry import MediaRegistry, TranscodeQueue, TranscodeJobRecord

logger = logging.getLogger("transcoder")

class TranscodeWorker:
    def __init__(
        self,
        transcode_queue: TranscodeQueue,
        media_registry: MediaRegistry,
        media_root: Path,
        progress_callback: Callable[[str, float], Any] | None = None,
    ) -> None:
        self.queue = transcode_queue
        self.registry = media_registry
        self.media_root = media_root
        self.progress_callback = progress_callback
        self._stop_event = asyncio.Event()

    def stop(self):
        self._stop_event.set()

    async def run_loop(self):
        logger.info("TranscodeWorker started")
        while not self._stop_event.is_set():
            job = await self.queue.get_next_queued()
            if job:
                await self._process_job(job)
            else:
                await asyncio.sleep(1.0)

    async def _process_job(self, job: TranscodeJobRecord):
        logger.info(f"Processing transcode job {job.job_id} for asset {job.asset_id}")
        await self.queue.update(job.job_id, status="RUNNING", error_message=None)
        
        asset = await self.registry.get(job.asset_id)
        if not asset:
            await self.queue.update(job.job_id, status="FAILED", error_message="Asset not found")
            return

        # Resolve source path
        source_path = self.media_root / asset.asset_id
        if not source_path.exists() and asset.uri:
            # Try to resolve from URI if absolute
            if asset.uri.startswith("file://"):
                source_path = Path(asset.uri[7:])
            else:
                source_path = Path(asset.uri)

        if not source_path.exists():
            await self.queue.update(job.job_id, status="FAILED", error_message=f"Source file not found: {source_path}")
            return

        target_path = self.media_root / f"{asset.asset_id}_{job.target_profile.lower()}.mov"
        
        try:
            # FFmpeg transcoding to HAP
            # Note: We use a simplified ffmpeg-python call. 
            # In a real scenario, we'd use a subprocess to capture progress.
            
            logger.info(f"Transcoding {source_path} to {target_path} using profile {job.target_profile}")
            
            # Simplified progress: 0% -> 50% -> 100% since ffmpeg-python 
            # standard .run() is blocking and doesn't easily give progress without complex setup.
            if self.progress_callback:
                await self.progress_callback(job.job_id, 0.1)

            # HAP encoding parameters
            # -c:v hap -format hap_q (depending on profile)
            v_codec = "hap"
            if job.target_profile.upper() == "HAP-Q":
                v_codec = "hap"
                # hap_q is often a format option: -format hap_q
                # But sometimes it's just -c:v hap -format hap_q
                kwargs = {"c:v": v_codec, "format": "hap_q"}
            else:
                kwargs = {"c:v": v_codec}

            # Run FFmpeg (wrapped in run_in_executor to avoid blocking the loop)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: ffmpeg.input(str(source_path))
                .output(str(target_path), **kwargs)
                .overwrite_output()
                .run(quiet=True)
            )

            if self.progress_callback:
                await self.progress_callback(job.job_id, 1.0)

            # Update asset in registry to point to new transcoded file
            # and update status to READY
            await self.registry.update(
                asset.asset_id, 
                status="READY", 
                uri=f"file://{target_path.absolute()}"
            )
            
            await self.queue.update(job.job_id, status="DONE", error_message=None)
            logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            logger.error(f"Transcoding failed for job {job.job_id}: {e}")
            await self.queue.update(job.job_id, status="FAILED", error_message=str(e))
            if target_path.exists():
                target_path.unlink()

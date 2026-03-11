"""
System Archiving & Show Packaging (SC-109)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from ..models import ArchiveJobResponse

logger = logging.getLogger("orchestration.archiver")

class ArchiverService:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.archives_dir = data_dir / "archives"
        self.archives_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, ArchiveJobResponse] = {}

    def get_job(self, job_id: str) -> ArchiveJobResponse | None:
        return self._jobs.get(job_id)

    async def create_export_job(self) -> str:
        job_id = f"exp_{uuid.uuid4().hex[:8]}"
        self._jobs[job_id] = ArchiveJobResponse(
            job_id=job_id,
            type="export",
            status="QUEUED",
        )
        asyncio.create_task(self._run_export(job_id))
        return job_id

    async def _run_export(self, job_id: str) -> None:
        job = self._jobs[job_id]
        job.status = "RUNNING"
        try:
            archive_path = self.archives_dir / f"show_{job_id}.stage"
            await asyncio.to_thread(self._do_export, archive_path)
            job.status = "DONE"
            job.archive_url = f"/api/v1/archive/download/{archive_path.name}"
        except Exception as e:
            logger.error(f"Archive export failed: {e}")
            job.status = "FAILED"
            job.error_message = str(e)

    def _do_export(self, archive_path: Path) -> None:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in ["orchestration.db", "timeline.db", "media_registry.json"]:
                p = self.data_dir / item
                if p.exists():
                    zf.write(p, arcname=item)
            
            media_dir = self.data_dir / "media"
            if media_dir.exists():
                for root, _, files in os.walk(media_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(self.data_dir)
                        zf.write(file_path, arcname=str(arcname))

    async def create_import_job(self, uploaded_file_path: Path) -> str:
        job_id = f"imp_{uuid.uuid4().hex[:8]}"
        self._jobs[job_id] = ArchiveJobResponse(
            job_id=job_id,
            type="import",
            status="QUEUED",
        )
        asyncio.create_task(self._run_import(job_id, uploaded_file_path))
        return job_id

    async def _run_import(self, job_id: str, uploaded_file_path: Path) -> None:
        job = self._jobs[job_id]
        job.status = "RUNNING"
        try:
            await asyncio.to_thread(self._do_import, uploaded_file_path)
            job.status = "DONE"
        except Exception as e:
            logger.error(f"Archive import failed: {e}")
            job.status = "FAILED"
            job.error_message = str(e)

    def _do_import(self, archive_path: Path) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(tmp_path)
            
            for item in ["orchestration.db", "timeline.db", "media_registry.json"]:
                src = tmp_path / item
                dst = self.data_dir / item
                if src.exists():
                    shutil.copy2(src, dst)
            
            src_media = tmp_path / "media"
            dst_media = self.data_dir / "media"
            if src_media.exists():
                # We overwrite the contents instead of full recreate to prevent locks
                shutil.copytree(src_media, dst_media, dirs_exist_ok=True)

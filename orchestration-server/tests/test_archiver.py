from __future__ import annotations

import asyncio
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Add the server root to the pythonpath for tests
import sys
ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.services.archiver import ArchiverService


class ArchiverTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some dummy data
        (self.data_dir / "orchestration.db").write_text("dummy orchestration")
        (self.data_dir / "timeline.db").write_text("dummy timeline")
        (self.data_dir / "media_registry.json").write_text("{}")
        
        media_dir = self.data_dir / "media"
        media_dir.mkdir()
        (media_dir / "test.mp4").write_text("dummy video")
        
        self.archiver = ArchiverService(self.data_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_export_and_import(self) -> None:
        # 1. Export
        job_id = await self.archiver.create_export_job()
        
        # Wait for export to finish
        job = self.archiver.get_job(job_id)
        self.assertIsNotNone(job)
        if job is None:
            return

        while job.status in ("QUEUED", "RUNNING"):
            await asyncio.sleep(0.05)
            
        self.assertEqual(job.status, "DONE", f"Export failed: {job.error_message}")
        self.assertIsNotNone(job.archive_url)
        
        archive_name = job.archive_url.split("/")[-1]  # type: ignore
        archive_path = self.archiver.archives_dir / archive_name
        self.assertTrue(archive_path.exists())
        
        # 2. Modify original data to simulate a different state
        (self.data_dir / "timeline.db").write_text("changed timeline")
        
        # 3. Import
        import_job_id = await self.archiver.create_import_job(archive_path)
        import_job = self.archiver.get_job(import_job_id)
        self.assertIsNotNone(import_job)
        if import_job is None:
            return
            
        while import_job.status in ("QUEUED", "RUNNING"):
            await asyncio.sleep(0.05)
            
        self.assertEqual(import_job.status, "DONE", f"Import failed: {import_job.error_message}")
        
        # Verify state was restored
        self.assertEqual((self.data_dir / "timeline.db").read_text(), "dummy timeline")
        self.assertEqual((self.data_dir / "media" / "test.mp4").read_text(), "dummy video")


if __name__ == "__main__":
    unittest.main()

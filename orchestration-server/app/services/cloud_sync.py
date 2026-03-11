import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
import time

# Attempt to import boto3, fallback to stub if missing
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None

logger = logging.getLogger("orchestration.cloud_sync")

class CloudSyncService:
    def __init__(self, data_dir: Path, bucket_name: Optional[str] = None):
        self.data_dir = data_dir
        self.media_dir = data_dir / "media"
        self.bucket_name = bucket_name or os.getenv("STAGE_CANVAS_S3_BUCKET")
        self.s3_client = None
        self.is_syncing = False
        self.last_sync_time = 0
        
        if boto3 and self.bucket_name:
            try:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
                )
                logger.info(f"CloudSync initialized for bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Boto3 client: {e}")

    async def start_background_sync(self, interval_seconds: int = 300):
        """Periodically syncs assets in the background."""
        while True:
            if self.s3_client and not self.is_syncing:
                await self.sync_now()
            await asyncio.sleep(interval_seconds)

    async def sync_now(self) -> Dict[str, Any]:
        """Triggers an immediate synchronization pass."""
        if not self.s3_client:
            return {"status": "ERROR", "message": "Cloud sync not configured (missing credentials or bucket)"}
        
        if self.is_syncing:
            return {"status": "BUSY", "message": "Sync already in progress"}

        self.is_syncing = True
        logger.info("Starting Cloud S3 synchronization...")
        
        results = {"uploaded": 0, "errors": 0, "files_checked": 0}
        
        try:
            # Sync Media Files
            if self.media_dir.exists():
                for root, _, files in os.walk(self.media_dir):
                    for file in files:
                        file_path = Path(root) / file
                        relative_path = file_path.relative_to(self.data_dir)
                        s3_key = str(relative_path)
                        
                        results["files_checked"] += 1
                        try:
                            # Simple "upload-if-missing" or "overwrite" for now
                            # In production we'd check ETag/MD5
                            await asyncio.to_thread(
                                self.s3_client.upload_file,
                                str(file_path),
                                self.bucket_name,
                                s3_key
                            )
                            results["uploaded"] += 1
                        except Exception as e:
                            logger.error(f"Failed to upload {s3_key}: {e}")
                            results["errors"] += 1

            # Sync Database Snapshots (SC-111 requires backing up the registry)
            for db_file in ["orchestration.db", "timeline.db"]:
                db_path = self.data_dir / db_file
                if db_path.exists():
                    try:
                        await asyncio.to_thread(
                            self.s3_client.upload_file,
                            str(db_path),
                            self.bucket_name,
                            f"backups/{db_file}"
                        )
                        results["uploaded"] += 1
                    except Exception as e:
                        logger.error(f"Failed to backup {db_file}: {e}")
                        results["errors"] += 1

            self.last_sync_time = time.time()
            return {"status": "SUCCESS", "details": results}

        finally:
            self.is_syncing = False
            logger.info("Cloud S3 synchronization complete.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": self.s3_client is not None,
            "bucket": self.bucket_name,
            "is_syncing": self.is_syncing,
            "last_sync_time": self.last_sync_time
        }

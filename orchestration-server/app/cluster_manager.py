import asyncio
import time
import httpx
from typing import Literal

NodeRole = Literal["PRIMARY", "BACKUP"]

class ClusterManager:
    """
    Handles Primary/Backup redundancy for the Orchestration Server.
    The Backup monitors the Primary and promotes itself if the Primary fails.
    """
    def __init__(self, role: NodeRole, primary_url: str | None = None, heartbeat_interval: float = 1.0, failover_timeout: float = 3.0):
        self.role = role
        self.primary_url = primary_url
        self.heartbeat_interval = heartbeat_interval
        self.failover_timeout = failover_timeout
        self._is_running = False
        self._last_primary_heartbeat = time.time()
        self._monitor_task: asyncio.Task | None = None

    async def start(self):
        self._is_running = True
        if self.role == "BACKUP":
            print(f"[Cluster] Starting as BACKUP, monitoring Primary: {self.primary_url}")
            self._monitor_task = asyncio.create_task(self._monitor_loop())
        else:
            print("[Cluster] Starting as PRIMARY")

    async def stop(self):
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        print("[Cluster] Stopped")

    async def _monitor_loop(self):
        async with httpx.AsyncClient() as client:
            while self._is_running:
                try:
                    resp = await client.get(f"{self.primary_url}/api/v1/cluster/heartbeat", timeout=0.5)
                    if resp.status_code == 200:
                        self._last_primary_heartbeat = time.time()
                    else:
                        print(f"[Cluster] Primary heartbeat failed with status {resp.status_code}")
                except Exception as e:
                    print(f"[Cluster] Primary heartbeat error: {e}")

                # Check for failover
                if self.role == "BACKUP" and (time.time() - self._last_primary_heartbeat) > self.failover_timeout:
                    await self._promote_to_primary()
                
                await asyncio.sleep(self.heartbeat_interval)

    async def _promote_to_primary(self):
        print("[Cluster] PRIMARY FAILURE DETECTED! Promoting to PRIMARY...")
        self.role = "PRIMARY"
        # In a real system, this might trigger IP takeover or DNS updates.
        # For StageCanvas, we just change the internal role.
        # The render nodes should already be attempting to reconnect if they lost connection.
        if self._monitor_task:
            self._monitor_task.cancel()

    def get_status(self) -> dict:
        return {
            "role": self.role,
            "last_primary_heartbeat_age": time.time() - self._last_primary_heartbeat if self.role == "BACKUP" else 0
        }

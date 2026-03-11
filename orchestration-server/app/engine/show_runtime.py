import logging
from typing import Optional
from .timeline_scheduler import TimelineScheduler

logger = logging.getLogger("orchestration.runtime")

class ShowRuntime:
    def __init__(self, timeline_repo, scheduler: TimelineScheduler):
        self.timeline_repo = timeline_repo
        self.scheduler = scheduler
        self.current_show_id: Optional[str] = None

    def load_show(self, show_id: str) -> bool:
        """Loads a show from the repository into the scheduler."""
        try:
            snapshot = self.timeline_repo.snapshot(show_id)
            self.current_show_id = show_id
            self.scheduler.load_show_data(snapshot)
            logger.info(f"[runtime] Loaded show: {show_id}")
            return True
        except Exception as e:
            logger.error(f"[runtime] Failed to load show {show_id}: {e}")
            return False

    async def play(self):
        """Starts the timeline scheduler loop."""
        if not self.current_show_id:
            logger.warning("[runtime] Cannot play: No show loaded")
            return
        await self.scheduler.start()

    async def pause(self):
        """Pauses the timeline scheduler loop."""
        await self.scheduler.pause()

    async def stop(self):
        """Stops the timeline scheduler and resets playhead."""
        await self.scheduler.stop()

    async def seek(self, position_ms: int):
        """Seeks the timeline to a specific position."""
        await self.scheduler.seek(position_ms)

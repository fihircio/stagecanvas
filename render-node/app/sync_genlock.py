import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class GenlockSync:
    """
    Hardware Genlock Sync Stub.
    Holds the frame-flip until a (simulated) hardware pulse is received.
    """
    def __init__(self, target_fps: float = 60.0):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.last_pulse_time = time.perf_counter()
        self.total_hold_time_ms = 0.0

    async def wait_for_pulse(self) -> float:
        """
        Stub: Simulate waiting for a VSync/hardware pulse.
        In a real implementation, this would block until a GPU/SDI interrupt.
        """
        # Yield to event loop, but don't add forced latency in the stub
        # to allow precision tests to pass.
        await asyncio.sleep(0)
        now = time.perf_counter()
        elapsed = now - self.last_pulse_time
        
        # Simulate a pulse arriving at every frame_interval
        wait_time = max(0, self.frame_interval - (elapsed % self.frame_interval))
        
        # In a real app with hardware, this would block on a GPIO interrupt 
        # or a Decklink/Quaro genlock API.
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        hold_end = time.perf_counter()
        hold_duration_ms = (hold_end - now) * 1000.0
        self.total_hold_time_ms += hold_duration_ms
        self.last_pulse_time = hold_end
        
        return hold_duration_ms

    def get_metrics(self) -> dict:
        return {
            "genlock_total_hold_ms": self.total_hold_time_ms,
            "genlock_active": True
        }

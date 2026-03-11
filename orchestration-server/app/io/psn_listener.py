import asyncio
import struct
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

class PSNListener:
    """
    PosiStageNet (PSN) 2.0 UDP Listener.
    Listens for stage tracking data (typically on port 56565).
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 56565, tracking_callback: Callable[[int, dict[str, float]], Awaitable[None]] = None):
        self.host = host
        self.port = port
        self.tracking_callback = tracking_callback
        self.transport = None
        self.protocol = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: PSNProtocol(self.tracking_callback),
            local_addr=(self.host, self.port)
        )
        logger.info(f"[PSN] Listening on {self.host}:{self.port}")

    def stop(self):
        if self.transport:
            self.transport.close()
            logger.info("[PSN] Listener stopped")

class PSNProtocol(asyncio.DatagramProtocol):
    def __init__(self, tracking_callback: Callable[[int, dict[str, float]], Awaitable[None]] = None):
        self.tracking_callback = tracking_callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        """
        Simplistic PSN v2.0 parser.
        PSN Header (12 bytes):
        - Sync (4 bytes): 0x88, 0x67, 0x00, 0x00
        - Header (8 bytes): length, ver...
        """
        if len(data) < 12:
            return

        # Check Sync (some implementations use different sync words, but PSN 2 is standardized)
        sync = struct.unpack('<I', data[0:4])[0]
        if sync != 0x00006788: # 0x8867 Little Endian
            return

        # Note: A full PSN parser would iterate through all "Chunks" (Trackers, Metadata, etc.)
        # Here we implement a targeted extract for the first Tracker (Chunk ID 0x0001)
        
        # Simple extraction for demo purposes:
        # PosiStageNet packets are complex. We look for the tracker block.
        try:
            # Chunk ID for Tracker List is usually after header
            tracker_chunk_id = struct.unpack('<H', data[12:14])[0]
            if tracker_chunk_id == 0x0001:
                # Number of trackers
                num_trackers = data[16]
                offset = 17
                
                for _ in range(num_trackers):
                    tracker_id = struct.unpack('<H', data[offset:offset+2])[0]
                    # Simplified: extract X, Y, Z (Floats)
                    # This offset logic is illustrative; PSN fields vary by flags.
                    x = struct.unpack('<f', data[offset+2:offset+6])[0]
                    y = struct.unpack('<f', data[offset+6:offset+10])[0]
                    z = struct.unpack('<f', data[offset+10:offset+14])[0]
                    
                    if self.tracking_callback:
                        coords = {"x": x, "y": y, "z": z}
                        asyncio.create_task(self.tracking_callback(tracker_id, coords))
                    
                    offset += 14 # Move to next tracker (assuming fixed size for simplicity)
        except Exception as e:
            logger.error(f"[PSN] Parse error: {e}")

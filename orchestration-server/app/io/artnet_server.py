import asyncio
import struct
from typing import Callable, Awaitable

class ArtNetServer:
    """
    Minimal ArtNet 4 / DMX listener for StageCanvas.
    Listens on UDP 6454 for ArtDMX (OpCode 0x5000) packets.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 6454, dmx_callback: Callable[[int, int, bytes], Awaitable[None]] = None):
        self.host = host
        self.port = port
        self.dmx_callback = dmx_callback
        self.transport: asyncio.DatagramTransport | None = None
        self.protocol: ArtNetProtocol | None = None

    async def start(self):
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: ArtNetProtocol(self.dmx_callback),
            local_addr=(self.host, self.port)
        )
        print(f"[ArtNet] Listening on {self.host}:{self.port}")

    def stop(self):
        if self.transport:
            self.transport.close()
            print("[ArtNet] Server stopped")

class ArtNetProtocol(asyncio.DatagramProtocol):
    def __init__(self, dmx_callback: Callable[[int, int, bytes], Awaitable[None]] = None):
        self.dmx_callback = dmx_callback

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        if len(data) < 18:
            return

        # Art-Net Header: "Art-Net\0"
        if data[0:8] != b'Art-Net\x00':
            return

        # OpCode (Little Endian)
        opcode = struct.unpack('<H', data[8:10])[0]
        if opcode != 0x5000: # ArtDMX
            return

        # Protocol Version (Big Endian)
        _proto_ver = struct.unpack('>H', data[10:12])[0]

        # Sequence, Physical
        # sequence = data[12]
        # physical = data[13]

        # Net + SubNet + Universe (Universe is bits 0-14)
        # For simplicity, we just use the 16-bit field as Universe ID
        universe = struct.unpack('<H', data[14:16])[0]

        # Length (Big Endian)
        length = struct.unpack('>H', data[16:18])[0]
        dmx_data = data[18:18+length]

        if self.dmx_callback:
            # Shield against slow callbacks by tasking them
            asyncio.create_task(self.dmx_callback(universe, length, dmx_data))

# Mapping Logic for StageCanvas
# Universe 0: Layer control
# Ch 1: Layer 1 Opacity (0-255)
# Ch 2: Layer 1 Speed (0-255)
# Ch 3: Layer 1 Play/Pause (0-127 Stop, 128-255 Play)
# ... repeats for each layer

class ArtNetToLayerMapper:
    def __init__(self, update_callback: Callable[[list[dict[str, Any]]], Awaitable[None]]):
        self.update_callback = update_callback

    async def handle_dmx(self, universe: int, length: int, data: bytes):
        if universe != 0:
            return
        
        # We assume 10 channels per layer for future expansion
        CHANNELS_PER_LAYER = 10
        layers_to_update = []

        for i in range(min(10, length // CHANNELS_PER_LAYER)):
            base = i * CHANNELS_PER_LAYER
            
            opacity = data[base] / 255.0
            speed = (data[base + 1] / 127.5) # 0.0 to 2.0
            play_pause = data[base + 2]
            
            layers_to_update.append({
                "layer_index": i,
                "opacity": opacity,
                "speed": speed,
                "play_state": "playing" if play_pause >= 128 else "paused"
            })
        
        if layers_to_update:
            await self.update_callback(layers_to_update)

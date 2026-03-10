import asyncio
import struct
from typing import Any, Callable, Awaitable

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
    def __init__(self, update_callback: Callable[[list[dict[str, Any]]], Awaitable[None]], fixtures_path: str = "shared-protocol/fixtures.json"):
        self.update_callback = update_callback
        self.fixtures_path = fixtures_path
        self.profiles = {}
        self.assignments = []
        self._load_fixtures()

    def _load_fixtures(self):
        try:
            import json
            import os
            # Support absolute or relative to CWD
            path = self.fixtures_path
            if not os.path.isabs(path):
                # Try relative to the app root or project root
                pass # Already using relative to project root in default

            with open(path, 'r') as f:
                config = json.load(f)
                self.profiles = {p["profile_name"]: p for p in config.get("profiles", [])}
                self.assignments = config.get("assignments", [])
                print(f"[ArtNet] Loaded {len(self.profiles)} profiles and {len(self.assignments)} assignments.")
        except Exception as e:
            print(f"[ArtNet] Error loading fixtures: {e}")

    async def handle_dmx(self, universe: int, length: int, data: bytes):
        layers_to_update = []

        for assign in self.assignments:
            if assign["universe"] != universe:
                continue
            
            profile = self.profiles.get(assign["profile_name"])
            if not profile:
                continue

            channels_per_fixture = profile["channels_per_fixture"]
            mapping = profile["mapping"]
            start_address = assign["start_address"] - 1 # 0-indexed
            count = assign["count"]

            for i in range(count):
                base = start_address + (i * channels_per_fixture)
                if base + channels_per_fixture > length:
                    break
                
                layer_patch = {"layer_index": i}
                
                for offset_str, param in mapping.items():
                    offset = int(offset_str)
                    val = data[base + offset]
                    
                    if param == "opacity":
                        layer_patch["opacity"] = val / 255.0
                    elif param == "speed":
                        layer_patch["speed"] = val / 127.5
                    elif param == "play_state":
                        layer_patch["play_state"] = "playing" if val >= 128 else "paused"
                    elif param == "transform_x":
                        layer_patch["transform_x"] = (val / 255.0) * 2.0 - 1.0 # -1 to 1
                    elif param == "transform_y":
                        layer_patch["transform_y"] = (val / 255.0) * 2.0 - 1.0 # -1 to 1
                    elif param == "scale_x":
                        layer_patch["scale_x"] = (val / 255.0) * 2.0
                    elif param == "scale_y":
                        layer_patch["scale_y"] = (val / 255.0) * 2.0
                
                layers_to_update.append(layer_patch)
        
        if layers_to_update:
            await self.update_callback(layers_to_update)

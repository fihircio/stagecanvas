import asyncio
import unittest
import socket
import struct
from app.io.artnet_server import ArtNetServer, ArtNetToLayerMapper

class TestArtNetServer(unittest.IsolatedAsyncioTestCase):
    async def test_artnet_dmx_mapping(self):
        received_updates = []

        async def mock_callback(layers):
            received_updates.append(layers)

        mapper = ArtNetToLayerMapper(update_callback=mock_callback)
        server = ArtNetServer(host="127.0.0.1", port=6455, dmx_callback=mapper.handle_dmx)
        await server.start()

        # Construct a mock ArtDMX packet
        # Header: Art-Net\0
        header = b'Art-Net\x00'
        opcode = struct.pack('<H', 0x5000)
        proto_ver = struct.pack('>H', 14)
        seq_phys = b'\x00\x00'
        universe = struct.pack('<H', 0)
        length = struct.pack('>H', 512)
        
        # DMX Data: 
        # Layer 0 (Ch 1-10): Opacity=255 (1.0), Speed=127 ( ~1.0), Play=255 (Playing)
        dmx_data = bytearray(512)
        dmx_data[0] = 255 # Opacity
        dmx_data[1] = 127 # Speed
        dmx_data[2] = 255 # Play
        
        packet = header + opcode + proto_ver + seq_phys + universe + length + dmx_data

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(packet, ("127.0.0.1", 6455))
        sock.close()

        # Give the event loop a moment
        await asyncio.sleep(0.2)
        server.stop()

        self.assertGreater(len(received_updates), 0)
        first_update = received_updates[0]
        layer0 = next(l for l in first_update if l["layer_index"] == 0)
        self.assertAlmostEqual(layer0["opacity"], 1.0)
        self.assertAlmostEqual(layer0["speed"], 127 / 127.5, places=2)
        self.assertEqual(layer0["play_state"], "playing")

if __name__ == '__main__':
    unittest.main()

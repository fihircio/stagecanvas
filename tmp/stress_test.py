import asyncio
import socket
import time
from pythonosc import udp_client

# ArtNet DMX Packet (OpCode 0x5000)
def create_artnet_dmx(universe: int, data: bytes) -> bytes:
    header = b'Art-Net\x00'
    opcode = b'\x00\x50' # 0x5000 Little Endian
    version = b'\x00\x0e' # 14 Big Endian
    sequence = b'\x00'
    physical = b'\x00'
    universe_id = universe.to_bytes(2, 'little')
    length = len(data).to_bytes(2, 'big')
    return header + opcode + version + sequence + physical + universe_id + length + data

async def stress_test_artnet(host: str, port: int, iterations: int = 1000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Starting ArtNet stress test at {host}:{port}")
    start = time.perf_counter()
    for i in range(iterations):
        # 510 channels of random data
        dmx_data = bytes([i % 256] * 510)
        packet = create_artnet_dmx(0, dmx_data)
        sock.sendto(packet, (host, port))
        if i % 100 == 0:
            await asyncio.sleep(0.01) # 100Hz effective
    end = time.perf_counter()
    print(f"ArtNet: Sent {iterations} packets in {end - start:.2f}s")
    sock.close()

async def stress_test_osc(host: str, port: int, iterations: int = 1000):
    client = udp_client.SimpleUDPClient(host, port)
    print(f"Starting OSC stress test at {host}:{port}")
    start = time.perf_counter()
    for i in range(iterations):
        client.send_message("/api/v1/trigger", ["yolo_detect", f"person_{i}"])
        if i % 100 == 0:
            await asyncio.sleep(0.01) # 100Hz effective
    end = time.perf_counter()
    print(f"OSC: Sent {iterations} packets in {end - start:.2f}s")

if __name__ == "__main__":
    async def run_all():
        # Port 6454 for ArtNet, 8000 for OSC (as seen in main.py)
        # Note: This expects a server listening on localhost.
        try:
            await asyncio.gather(
                stress_test_artnet("127.0.0.1", 6454, 500),
                stress_test_osc("127.0.0.1", 8000, 500)
            )
        except ConnectionRefusedError:
            print("Server not running, skipping live stress test.")

    asyncio.run(run_all())

import asyncio
import socket
import struct
from typing import Dict, List

class ArtNetSender:
    """
    ArtNet 4 DMX Sender for StageCanvas.
    Sends OpCode 0x5000 (ArtDMX) over UDP port 6454 to broadcast or specific IPs.
    """
    def __init__(self, target_ip: str = "255.255.255.255", port: int = 6454):
        self.target_ip = target_ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if target_ip == "255.255.255.255":
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def send_universe(self, universe: int, data: bytes):
        """
        Sends up to 512 bytes of DMX data to the specified universe.
        """
        if len(data) > 512:
            data = data[:512]
            
        # ArtDMX Packet Header (18 bytes)
        # ID: "Art-Net\0" (8 bytes)
        # OpCode: 0x5000 (ArtDMX, Little Endian) (2 bytes) -> 0x00 0x50
        # ProtVer: 14 (Big Endian) (2 bytes) -> 0x00 0x0e
        # Sequence: 0x00 (Auto)
        # Physical: 0x00
        # SubUni (Universe): 16-bit Little Endian (2 bytes)
        # Length: Big Endian length of DMX data (2 bytes)
        
        header = bytearray(18)
        header[0:8] = b'Art-Net\0'
        
        # OpCode 0x5000 (Little Endian)
        struct.pack_into('<H', header, 8, 0x5000)
        
        # ProtVer 14 (Big Endian)
        struct.pack_into('>H', header, 10, 14)
        
        # Sequence and Physical
        header[12] = 0
        header[13] = 0
        
        # Universe (Little Endian)
        struct.pack_into('<H', header, 14, universe)
        
        # Length (Big Endian) - Must be even
        length = len(data)
        if length % 2 != 0:
             data += b'\x00'
             length += 1
             
        struct.pack_into('>H', header, 16, length)
        
        packet = header + data
        try:
            self.sock.sendto(packet, (self.target_ip, self.port))
        except Exception as e:
            # Drop silently for performance, in a real app might log throttling
            pass

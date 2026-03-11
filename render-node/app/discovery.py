from __future__ import annotations

import socket
import logging
from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger("discovery")

class HeartbeatDiscovery:
    def __init__(self, node_id: str, label: str | None = None, port: int = 8010):
        self.node_id = node_id
        self.label = label or node_id
        self.port = port
        self.zeroconf = Zeroconf()
        self.service_info = None

    def get_ip_address(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def register(self):
        desc = {b"node_id": self.node_id.encode("utf-8"), b"label": self.label.encode("utf-8")}
        ip = self.get_ip_address()
        
        self.service_info = ServiceInfo(
            "_stagecanvas._tcp.local.",
            f"{self.node_id}._stagecanvas._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties=desc,
            server=f"{self.node_id}.local.",
        )
        self.zeroconf.register_service(self.service_info)
        logger.info(f"Registered mDNS service for {self.node_id} on {ip}:{self.port}")

    def unregister(self):
        if self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.service_info = None
        self.zeroconf.close()

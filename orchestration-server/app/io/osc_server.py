import asyncio
from typing import Callable, Any
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import time

class OSCServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 10101, trigger_callback: Callable[[dict[str, Any]], None] = None):
        self.host = host
        self.port = port
        self.trigger_callback = trigger_callback
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/stagecanvas/trigger", self._handle_trigger)
        self.server = None
        self.transport = None

    def _handle_trigger(self, address: str, *args):
        if not self.trigger_callback:
            return
        
        rule_id = str(args[0]) if len(args) > 0 else "osc-trigger"
        value = args[1] if len(args) > 1 else 1.0

        payload = {
            "rule_id": rule_id,
            "payload": {
                "value": value,
                "source": "osc",
                "timestamp": time.time()
            }
        }
        
        # Fire the callback (we can assume the callback is a synchronous function that queues an async task,
        # or we can use the event loop to run the async callback if it's an async function)
        if asyncio.iscoroutinefunction(self.trigger_callback):
            asyncio.create_task(self.trigger_callback(payload))
        else:
            self.trigger_callback(payload)

    async def start(self):
        server = AsyncIOOSCUDPServer((self.host, self.port), self.dispatcher, asyncio.get_running_loop())
        self.transport, self.protocol = await server.create_serve_endpoint()
        print(f"[osc-server] Serving on {self.host}:{self.port}")

    def stop(self):
        if self.transport:
            self.transport.close()
            print("[osc-server] Stopped.")

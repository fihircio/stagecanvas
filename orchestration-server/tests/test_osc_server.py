import asyncio
import unittest
from pythonosc.udp_client import SimpleUDPClient
from app.io.osc_server import OSCServer

class TestOSCServer(unittest.IsolatedAsyncioTestCase):
    async def test_osc_trigger_mapping(self):
        received_payloads = []

        async def mock_callback(payload):
            received_payloads.append(payload)

        server = OSCServer(host="127.0.0.1", port=8001, trigger_callback=mock_callback)
        await server.start()

        client = SimpleUDPClient("127.0.0.1", 8001)
        client.send_message("/stagecanvas/trigger", ["cue-1", 0.5])

        # Give the event loop a moment to process the UDP packet
        await asyncio.sleep(0.1)

        server.stop()

        self.assertEqual(len(received_payloads), 1)
        payload = received_payloads[0]
        self.assertEqual(payload["rule_id"], "cue-1")
        self.assertEqual(payload["payload"]["value"], 0.5)
        self.assertEqual(payload["payload"]["source"], "osc")

if __name__ == '__main__':
    unittest.main()

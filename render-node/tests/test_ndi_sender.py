import unittest
from app.output.ndi_sender import NDISender
from app.output.webrtc_stream import WebRTCStreamer

class TestOutputBroadcasting(unittest.TestCase):
    def test_ndi_sender_flow(self):
        sender = NDISender(stream_name="TestStream")
        self.assertFalse(sender.is_running)
        
        sender.start()
        self.assertTrue(sender.is_running)
        self.assertEqual(sender.frame_count, 0)
        
        sender.send_frame(b"fake-frame")
        self.assertEqual(sender.frame_count, 1)
        
        sender.stop()
        self.assertFalse(sender.is_running)
        
        sender.send_frame(b"after-stop")
        self.assertEqual(sender.frame_count, 1)

    def test_webrtc_streamer_flow(self):
        streamer = WebRTCStreamer(port=9999)
        self.assertFalse(streamer.is_streaming)
        
        streamer.start()
        self.assertTrue(streamer.is_streaming)
        self.assertEqual(streamer.port, 9999)
        
        streamer.push_frame(b"fake-frame")
        
        streamer.stop()
        self.assertFalse(streamer.is_streaming)

if __name__ == "__main__":
    unittest.main()

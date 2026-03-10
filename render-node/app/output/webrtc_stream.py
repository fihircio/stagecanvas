import logging
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaRelay
import av
from fractions import Fraction
import time

logger = logging.getLogger(__name__)
relay = MediaRelay()

class RawVideoTrack(VideoStreamTrack):
    """
    A video track that receives raw frames from the renderer.
    """
    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue(maxsize=2)
        self._start_time = None

    def push_frame(self, frame_data: bytes, width: int = 1920, height: int = 1080):
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._queue.put_nowait((frame_data, width, height, time.time()))

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        frame_data, width, height, timestamp = await self._queue.get()
        
        # Convert bytes to VideoFrame
        # This is a simplification; real zero-copy would involve memoryviews
        frame = av.VideoFrame(width, height, 'rgb24')
        frame.planes[0].update(frame_data)
        
        frame.pts = pts
        frame.time_base = time_base
        return frame

class WebRTCStreamer:
    """
    Production WebRTC Streamer using aiortc.
    Encodes the render output to a real H.264 stream.
    """
    def __init__(self):
        self.pcs = set()
        self.video_track = RawVideoTrack()
        self.is_streaming = False

    async def create_offer(self):
        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await pc.close()
                self.pcs.discard(pc)

        pc.addTrack(relay.subscribe(self.video_track))
        
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        return pc.localDescription

    async def handle_answer(self, pc: RTCPeerConnection, sdp: str, type: str):
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type))

    def push_frame(self, frame_data: bytes, width: int = 1920, height: int = 1080):
        if self.is_streaming:
            self.video_track.push_frame(frame_data, width, height)

    def start(self):
        logger.info("[webrtc-stream] Starting WebRTC streamer engine")
        self.is_streaming = True

    async def stop(self):
        logger.info("[webrtc-stream] Stopping WebRTC monitor")
        self.is_streaming = False
        coros = [pc.close() for pc in self.pcs]
        await asyncio.gather(*coros)
        self.pcs.clear()

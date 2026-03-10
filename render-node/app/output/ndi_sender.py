import logging

logger = logging.getLogger(__name__)

class NDISender:
    """
    NDI Sender Stub for StageCanvas.
    In a production environment, this would interface with the NDI SDK.
    """
    def __init__(self, stream_name: str = "StageCanvas-Main"):
        self.stream_name = stream_name
        self.is_running = False
        self.frame_count = 0

    def start(self):
        logger.info(f"[ndi-sender] Starting NDI stream: {self.stream_name}")
        self.is_running = True

    def stop(self):
        logger.info(f"[ndi-sender] Stopping NDI stream: {self.stream_name}")
        self.is_running = False

    def send_frame(self, frame_data: bytes, width: int = 1920, height: int = 1080):
        """
        Simulate sending a frame to the NDI stream.
        """
        if not self.is_running:
            return

        self.frame_count += 1
        # In a real implementation, we would call NDIlib_send_video_v2
        # logger.debug(f"[ndi-sender] Sent frame {self.frame_count} ({len(frame_data)} bytes)")

import logging
import ctypes
import sys
import platform
import os
import time

logger = logging.getLogger(__name__)

# NDI struct definitions
class NDIlib_source_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_url_address", ctypes.c_char_p)
    ]

class NDIlib_send_create_t(ctypes.Structure):
    _fields_ = [
        ("p_ndi_name", ctypes.c_char_p),
        ("p_groups", ctypes.c_char_p),
        ("clock_video", ctypes.c_bool),
        ("clock_audio", ctypes.c_bool)
    ]

# Frame type enums (values based on NDI 5 headers)
NDIlib_FourCC_video_type_UYVY = 1
NDIlib_FourCC_video_type_BGRA = 3
NDIlib_FourCC_video_type_BGRX = 4
NDIlib_FourCC_video_type_RGBA = 5
NDIlib_FourCC_video_type_RGBX = 6

class NDIlib_video_frame_v2_t(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_int),
        ("yres", ctypes.c_int),
        ("FourCC", ctypes.c_int),
        ("frame_rate_N", ctypes.c_int),
        ("frame_rate_D", ctypes.c_int),
        ("picture_aspect_ratio", ctypes.c_float),
        ("frame_format_type", ctypes.c_int),
        ("timecode", ctypes.c_int64),
        ("p_data", ctypes.c_void_p),
        ("line_stride_in_bytes", ctypes.c_int),
        ("p_metadata", ctypes.c_char_p),
        ("timestamp", ctypes.c_int64)
    ]

class NDIlib_tally_t(ctypes.Structure):
    _fields_ = [
        ("on_program", ctypes.c_bool),
        ("on_preview", ctypes.c_bool)
    ]

class NDIlib_metadata_frame_t(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_int),
        ("timecode", ctypes.c_int64),
        ("p_data", ctypes.c_char_p)
    ]

class NDISender:
    """
    NDI Sender for StageCanvas.
    Interfaces with the native NDI 5 SDK, supporting Tally & Metadata.
    Falls back to stub behavior if libndi is not found.
    """
    def __init__(self, stream_name: str = "StageCanvas-Main", node_id: str = "node"):
        # SC-123 requirement: production-standard naming "StageCanvas (NodeID)"
        format_name = f"StageCanvas ({node_id})" if node_id else stream_name
        self.stream_name = format_name
        self.is_running = False
        self.frame_count = 0
        self.has_ndi = False
        self.ndi_lib = None
        self.ndi_send = None

        self._load_ndi_lib()

    def _load_ndi_lib(self):
        try:
            if platform.system() == "Darwin":
                lib_path = "libndi.dylib"
            elif platform.system() == "Windows":
                lib_path = "Processing.NDI.Lib.x64.dll"
            else:
                lib_path = "libndi.so"
            
            self.ndi_lib = ctypes.CDLL(lib_path)
            
            # Setup libndi functions we need
            self.ndi_lib.NDIlib_initialize.restype = ctypes.c_bool
            
            self.ndi_lib.NDIlib_send_create.argtypes = [ctypes.POINTER(NDIlib_send_create_t)]
            self.ndi_lib.NDIlib_send_create.restype = ctypes.c_void_p
            
            self.ndi_lib.NDIlib_send_destroy.argtypes = [ctypes.c_void_p]
            
            self.ndi_lib.NDIlib_send_send_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t)]
            
            self.ndi_lib.NDIlib_send_get_tally.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_tally_t), ctypes.c_uint32]
            self.ndi_lib.NDIlib_send_get_tally.restype = ctypes.c_bool
            
            self.ndi_lib.NDIlib_send_send_metadata.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_metadata_frame_t)]

            if not self.ndi_lib.NDIlib_initialize():
                logger.warning("[ndi-sender] NDI SDK found but failed to initialize.")
                return

            self.has_ndi = True
        except OSError:
            logger.warning("[ndi-sender] Native NDI SDK library not found. Operating in stub mode.")
            self.has_ndi = False

    def start(self):
        logger.info(f"[ndi-sender] Starting NDI stream: {self.stream_name}")
        self.is_running = True
        
        if self.has_ndi:
            try:
                name_bytes = self.stream_name.encode('utf-8')
                create_desc = NDIlib_send_create_t()
                create_desc.p_ndi_name = name_bytes
                create_desc.p_groups = None # default groups
                create_desc.clock_video = True
                create_desc.clock_audio = False

                self.ndi_send = self.ndi_lib.NDIlib_send_create(ctypes.byref(create_desc))
                if not self.ndi_send:
                    logger.error("[ndi-sender] Failed to create native NDI send instance. Falling back to stub.")
                    self.has_ndi = False
            except Exception as e:
                logger.error(f"[ndi-sender] Exception creating NDI instance: {e}")
                self.has_ndi = False

    def stop(self):
        logger.info(f"[ndi-sender] Stopping NDI stream: {self.stream_name}")
        self.is_running = False
        if self.has_ndi and self.ndi_send:
            try:
                self.ndi_lib.NDIlib_send_destroy(self.ndi_send)
                self.ndi_send = None
            except Exception as e:
                logger.error(f"[ndi-sender] Exception destroying NDI instance: {e}")

    def send_frame(self, frame_data: bytes, width: int = 1920, height: int = 1080):
        if not self.is_running:
            return

        self.frame_count += 1
        
        if self.has_ndi and self.ndi_send:
            try:
                video_frame = NDIlib_video_frame_v2_t()
                video_frame.xres = width
                video_frame.yres = height
                video_frame.FourCC = NDIlib_FourCC_video_type_RGBA
                video_frame.frame_rate_N = 60000
                video_frame.frame_rate_D = 1000
                video_frame.picture_aspect_ratio = float(width) / float(height)
                video_frame.frame_format_type = 0 # Progressive
                video_frame.timecode = -1 # NDIlib_send_timecode_synthesize
                video_frame.p_data = ctypes.cast(frame_data, ctypes.c_void_p)
                video_frame.line_stride_in_bytes = width * 4 # Assuming RGBA (4 bytes per pixel)
                video_frame.p_metadata = None
                video_frame.timestamp = 0
                
                self.ndi_lib.NDIlib_send_send_video_v2(self.ndi_send, ctypes.byref(video_frame))
            except Exception as e:
                pass # Fail silently for performance in loop

    def get_tally(self) -> dict:
        """Returns program/preview tally status."""
        if not self.is_running or not self.has_ndi or not self.ndi_send:
            return {"program": False, "preview": False}
        
        tally = NDIlib_tally_t()
        # 0 timeout for non-blocking poll
        if self.ndi_lib.NDIlib_send_get_tally(self.ndi_send, ctypes.byref(tally), 0):
            return {
                "program": bool(tally.on_program),
                "preview": bool(tally.on_preview)
            }
        return {"program": False, "preview": False}

    def send_metadata(self, xml_data: str):
        """Sends arbitrary XML metadata on the stream."""
        if not self.is_running or not self.has_ndi or not self.ndi_send:
            return
            
        try:
            xml_bytes = xml_data.encode('utf-8')
            meta_frame = NDIlib_metadata_frame_t()
            meta_frame.length = len(xml_bytes)
            meta_frame.timecode = -1 # NDIlib_send_timecode_synthesize
            meta_frame.p_data = xml_bytes
            
            self.ndi_lib.NDIlib_send_send_metadata(self.ndi_send, ctypes.byref(meta_frame))
        except Exception as e:
            logger.warning(f"[ndi-sender] Failed to send metadata: {e}")

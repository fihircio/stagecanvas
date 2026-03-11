import numpy as np
from typing import Dict, List, Any

class PixelMapper:
    """
    Extracts RGB values from a rendered frame (memoryview) at specific UV coordinates
    and packs them into DMX universe payloads for ArtNet dispatch.
    Optimized to handle >10 universes at high framerates using numpy.
    """
    def __init__(self, mapping_config: List[Dict[str, Any]], width: int, height: int):
        """
        mapping_config: List of dicts specifying UV coordinates and target DMX mappings.
        e.g. [{"universe": 1, "pixels": [{"x": 0.1, "y": 0.5, "channel": 1}, ...]}]
        """
        self.width = width
        self.height = height
        self.mapping_config = mapping_config
        self.universes = {}
        self._prepare_indices()

    def _prepare_indices(self):
        """
        Pre-calculate absolute pixel indices and DMX offsets to maximize mapping speed.
        """
        # Store as: dict { universe_id: (flat_indices_array, channel_offsets_array) }
        self.universes = {}
        for uni_config in self.mapping_config:
            universe = uni_config.get("universe", 0)
            pixels = uni_config.get("pixels", [])
            
            # Max array size for a universe is 512
            indices = []
            channels = []
            
            for p in pixels:
                # UV to absolute pixel coordinates
                u, v = p.get('u', 0.0), p.get('v', 0.0)
                ch = p.get('channel', 1) - 1 # 0-indexed internally
                
                x = int(u * self.width)
                y = int(v * self.height)
                
                # Clamp
                x = max(0, min(self.width - 1, x))
                y = max(0, min(self.height - 1, y))
                
                # Assuming RGBA (4 bytes per pixel)
                base_idx = (y * self.width + x) * 4
                
                # Store R, G, B indices
                indices.extend([base_idx, base_idx + 1, base_idx + 2])
                channels.extend([ch, ch + 1, ch + 2])
                
            if indices:
                self.universes[universe] = (
                    np.array(indices, dtype=np.int32),
                    np.array(channels, dtype=np.int32)
                )

    def update_config(self, mapping_config: List[Dict[str, Any]]):
        self.mapping_config = mapping_config
        self._prepare_indices()

    def map_frame(self, frame_data: memoryview) -> Dict[int, bytes]:
        """
        Extracts mapped pixels from the frame buffer and returns a dictionary of
        universe -> DMX payload bytes.
        """
        if not self.universes:
            return {}

        # Convert to numpy array for vectorized extraction
        # We assume frame_data is flat RGBA 8-bit
        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
        
        payloads = {}
        for universe, (indices, channels) in self.universes.items():
            # Create an empty 512-byte universe array
            dmx_data = np.zeros(512, dtype=np.uint8)
            
            # Extract requested bytes
            # indices array length == channels array length (R, G, B interleaved)
            extracted_vals = frame_array[indices]
            
            # Scatter into DMX slots
            # If multiple pixels map to same channel, later elements overwrite earlier (simplistic)
            dmx_data[channels] = extracted_vals
            
            # Find the max channel used to optimize payload size
            max_channel = np.max(channels) if len(channels) > 0 else 0
            
            # Ensure length is even and covers the max mapped channel
            payload_len = max_channel + 1
            if payload_len % 2 != 0:
                payload_len += 1
                
            payloads[universe] = dmx_data[:payload_len].tobytes()
            
        return payloads

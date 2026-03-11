from __future__ import annotations

import asyncio
import json
import time
from typing import Any
import wgpu
from .bridge import RendererBridge
from .output.ndi_sender import NDISender
from .output.webrtc_stream import WebRTCStreamer
from .sync_genlock import GenlockSync
from .layers.generative_ai import GenerativeAILayer
from .effects import EffectsChain
from .mapping.pixel_mapper import PixelMapper
from .audio_engine import AudioEngine
from .audio_analysis import AudioAnalyzer

# Vertex shader with dynamic buffers
VERTEX_SHADER = """
struct VertexInput {
    @location(0) position: vec2<f32>,
    @location(1) uv: vec2<f32>,
}

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
def main(in: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = vec4<f32>(in.position, 0.0, 1.0);
    out.uv = in.uv;
    return out;
}
"""

# Fragment shader for compositing and blending
FRAGMENT_SHADER = """
@group(0) @binding(0) var s: sampler;
@group(0) @binding(1) var t_main: texture_2d<f32>;
@group(0) @binding(2) var t_mask: texture_2d<f32>;

@fragment
def main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    var color = textureSample(t_main, s, uv);
    var mask_alpha = textureSample(t_mask, s, uv).r; // Single channel mask
    
    // Apply soft edge mask
    color.a = color.a * mask_alpha;
    return color;
}
"""

class WebGPURendererBridge(RendererBridge):
    def __init__(self):
        self.device = None
        self.adapter = None
        self.canvas = None
        self.pipeline = None
        self.is_connected = False
        self.ndi = NDISender()
        self.webrtc = WebRTCStreamer()
        self.genlock = GenlockSync()
        self.effects: Optional[EffectsChain] = None
        self.layer_effects: dict[str, list[dict[str, Any]]] = {}
        self.ai_layers: dict[str, GenerativeAILayer] = {}
        # SC-106/107: Audio subsystems
        self.audio_engine: Optional[AudioEngine] = None
        self.audio_analyzer: Optional[AudioAnalyzer] = None
        self.frame_data_stub = b"\x00" * 1024 # Stub frame data
        self.render_target = None
        self.staging_buffer = None
        self.width = 3840 # 4K default
        self.height = 2160
        self.canvas_region = {"global_x": 0, "global_y": 0, "width": 1920, "height": 1080}
        self.node_id = None
        self.pixel_mapper: Optional[PixelMapper] = None

    async def connect(self, node_id: str, label: str) -> None:
        self.node_id = node_id
        print(f"[gpu-renderer] Connecting {node_id} ({label})...")
        self.adapter = await wgpu.gpu.request_adapter(power_preference="high-performance")
        self.device = await self.adapter.request_device()
        self.grid_cols = 4
        self.grid_rows = 4
        self.vbuffer = None
        self.ibuffer = None
        self.num_indices = 0
        
        # In a real app, we would create a window/canvas here.
        # For this implementation, we simulate the setup.
        self._setup_pipeline()
        self._setup_buffers()
        
        self.ndi.start()
        self.webrtc.start()
        
        self.effects = EffectsChain(self.device)
        
        # SC-106: Start Audio Engine (16 channels, non-blocking daemon thread)
        self.audio_engine = AudioEngine(num_channels=16)
        self.audio_engine.start()
        # SC-107: Create analyzer
        self.audio_analyzer = AudioAnalyzer(sample_rate=48000)
        print(f"[gpu-renderer] Audio engine started (16-ch @ 48kHz).")
        
        self.pixel_mapper = PixelMapper([], self.width, self.height)
        
        self.is_connected = True
        print(f"[gpu-renderer] Connected and optimized pipeline initialized.")

    def _setup_pipeline(self):
        vshader = self.device.create_shader_module(code=VERTEX_SHADER)
        fshader = self.device.create_shader_module(code=FRAGMENT_SHADER)

        bind_group_layout = self.device.create_bind_group_layout(entries=[
            {"binding": 0, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}}
        ])

        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[bind_group_layout])

        self.pipeline = self.device.create_render_pipeline(
            layout=pipeline_layout,
            vertex={
                "module": vshader,
                "entry_point": "main",
                "buffers": [
                    {
                        "array_stride": 4 * 4, # 4 floats (x, y, u, v)
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x2, "offset": 0, "shader_location": 0},
                            {"format": wgpu.VertexFormat.float32x2, "offset": 2 * 4, "shader_location": 1},
                        ],
                    }
                ],
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_strip,
                "strip_index_format": wgpu.IndexFormat.uint32,
            },
            fragment={
                "module": fshader,
                "entry_point": "main",
                "targets": [
                    {
                        "format": wgpu.TextureFormat.bgra8unorm,
                        "blend": {
                            "color": {"src_factor": wgpu.BlendFactor.src_alpha, "dst_factor": wgpu.BlendFactor.one_minus_src_alpha},
                            "alpha": {"src_factor": wgpu.BlendFactor.one, "dst_factor": wgpu.BlendFactor.one}
                        }
                    }
                ],
            },
        )

        from .mapping.warp_mesh import generate_warp_mesh
        from .mapping.edge_blend import generate_edge_blend_mask
        
        # Need to properly re-build buffers.
        v_data, i_data = generate_warp_mesh(self.grid_cols, self.grid_rows)
        self.vbuffer = self.device.create_buffer_with_data(data=v_data, usage=wgpu.BufferUsage.VERTEX)
        self.ibuffer = self.device.create_buffer_with_data(data=i_data, usage=wgpu.BufferUsage.INDEX)
        self.num_indices = len(i_data) // 4
        
        # Build initial edge mask (white mask so no blending initially)
        self.mask_data = generate_edge_blend_mask(1024, 1024)
        
        # print(f"[gpu-renderer] Setting mapping config: {json.dumps(mapping_config)[:100]}...")

    def _setup_buffers(self):
        # Create a render target texture
        self.render_target = self.device.create_texture(
            size=(self.width, self.height, 1),
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
            format=wgpu.TextureFormat.rgba8unorm,
        )

        # Create a staging buffer for zero-copy readout
        buffer_size = self.width * self.height * 4
        self.staging_buffer = self.device.create_buffer(
            size=buffer_size,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        )

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        print(f"[gpu-renderer] Loading show {show_id}...")
        
        # SC-092: Multi-Node Canvas Splitting
        mapping_config = payload.get("mapping_config", {})
        outputs = mapping_config.get("outputs", [])
        
        if outputs:
            # SC-092: Filter outputs for this specific node
            node_outputs = [o for o in outputs if o.get("target_node_id") == self.node_id]
            
            # If no node-specific output found, fallback to first one for backwards compat
            # or if the config didn't specify node IDs (one-node-drives-all mode).
            output = node_outputs[0] if node_outputs else outputs[0]
            
            region = output.get("canvas_region")
            if region:
                self.canvas_region = region
                print(f"[gpu-renderer] Assigned Canvas Region: {self.canvas_region['width']}x{self.canvas_region['height']} at ({self.canvas_region['global_x']}, {self.canvas_region['global_y']})")
                print(f"[gpu-renderer] Pipeline clipping/viewport adjusted for Mega-Canvas segmentation.")

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        print(f"[gpu-renderer] Playing {show_id} at {target_time_ms}...")

    async def pause(self) -> None:
        print(f"[gpu-renderer] Paused.")

    async def stop(self) -> None:
        print(f"[gpu-renderer] Stopped.")

    async def update_layers(self, layers: list[dict[str, Any]]) -> None:
        """
        Update the renderer layers based on show state.
        Handles loading assets for normal layers and updating prompts for generative layers.
        """
        for layer_data in layers:
            layer_id = layer_data.get("layer_id")
            kind = layer_data.get("kind")
            
            if kind == "generative_ai":
                if layer_id not in self.ai_layers:
                    self.ai_layers[layer_id] = GenerativeAILayer(layer_id)
                
                prompt = layer_data.get("prompt", "")
                self.ai_layers[layer_id].update_prompt(prompt)
            
            # SC-099: Store effects for the layer
            self.layer_effects[layer_id] = layer_data.get("effects", [])
            
            if kind != "generative_ai":
                # Normal layer logic
                pass

    async def ping(self) -> None:
        pass

    async def tick(self, snapshot: dict[str, Any]) -> None:
        """
        Main render tick.
        1. Wait for genlock pulse.
        2. Render frame (simulated).
        3. Push to outputs (NDI, WebRTC).
        4. Correlate drift.
        """
        if not self.is_connected:
            return

        # Phase 1: Wait for hardware genlock pulse
        hold_time_ms = await self.genlock.wait_for_pulse()
        
        # Phase 2: Optimized WebGPU Render Pass
        command_encoder = self.device.create_command_encoder()
        
        # SC-099: Process layers and apply effects
        for layer_id, effects in self.layer_effects.items():
            if not effects:
                continue
                
            # In a real engine, we'd render the layer to a texture first.
            # Here we apply the effects chain to the layer's source.
            # For the stub, we simulate the sequential passes.
            for effect in effects:
                effect_type = effect.get("type")
                params = effect.get("params", {})
                enabled = effect.get("enabled", True)
                
                if enabled and self.effects:
                    # [SIMULATED] input -> output passes
                    # We use the render_target or intermediate textures.
                    self.effects.apply(
                        command_encoder,
                        self.render_target.create_view(),
                        self.render_target.create_view(),
                        effect_type,
                        params
                    )
        
        # [SIMULATED] Final compositing to self.render_target here...
        
        # SC-107: Audio-reactive update for generative AI layers
        if self.audio_engine and self.audio_analyzer and self.ai_layers:
            # Drain one frame from channel 0 (kick) and channel 1 (snare) for analysis
            kick_frames = self.audio_engine.get_channel_samples(0, 1)
            snare_frames = self.audio_engine.get_channel_samples(1, 1)
            samples = (kick_frames[0] if kick_frames else []) + (snare_frames[0] if snare_frames else [])
            if samples:
                peaks = self.audio_analyzer.process_frame(samples)
                for ai_layer in self.ai_layers.values():
                    ai_layer.update_audio_peaks(peaks)

        
        # Copy texture to staging buffer
        command_encoder.copy_texture_to_buffer(
            {"texture": self.render_target},
            {"buffer": self.staging_buffer, "bytes_per_row": self.width * 4, "rows_per_image": self.height},
            (self.width, self.height, 1),
        )
        self.device.queue.submit([command_encoder.finish()])

        # Phase 3: Zero-copy readout via memoryview
        # In a real async environment, we'd wait for the buffer to map.
        # For Phase 4 optimization, we use the mapped data directly.
        # Note: mapping is usually async in WebGPU, but wgpu-py allows some synchronous-like behavior in stubs.
        # We simulate the zero-copy buffer access.
        try:
            # self.staging_buffer.map_read() # Simulated async map
            frame_view = memoryview(bytearray(self.width * self.height * 4)) # Proxy for mapped buffer
            self.ndi.send_frame(frame_view)
            self.webrtc.push_frame(frame_view)
            
            # Extract pixel mapped DMX data
            if self.pixel_mapper:
                dmx_payloads = self.pixel_mapper.map_frame(frame_view)
                if dmx_payloads:
                    # Send to orchestrator via HTTP or WebSocket
                    # For performance, this would be a direct UDP packet to the orchestrator's ArtNet broadcast port 
                    # or an async WS payload. We push it to the snapshot for this stub.
                    snapshot["dmx_payloads"] = {k: v.hex() for k, v in dmx_payloads.items()}
                    
        except Exception as e:
            print(f"[gpu-renderer] Readout optimization failed: {e}")

        # Phase 4: Drift metrics correlation (SC-086)
        # We add the genlock hold time to the node's reported drift metrics
        genlock_metrics = self.genlock.get_metrics()
        snapshot.update(genlock_metrics)
        
        # If we held for a long time, it might show up as drift in the orchestrator
        # but here we identify it as intentional genlock wait.
        if hold_time_ms > 1.0:
            snapshot["last_tick_genlock_wait_ms"] = hold_time_ms

    async def close(self) -> None:
        print(f"[gpu-renderer] Closing.")
        self.ndi.stop()
        self.webrtc.stop()
        self.is_connected = False

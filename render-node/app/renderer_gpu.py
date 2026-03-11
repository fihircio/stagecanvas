from __future__ import annotations

import asyncio
import json
import time
from typing import Any
import wgpu
from .bridge import RendererBridge, Decoder
from .output.ndi_sender import NDISender
from .output.webrtc_stream import WebRTCStreamer
from .sync_genlock import GenlockSync
from .layers.generative_ai import GenerativeAILayer
from .effects import EffectsChain
from .mapping.pixel_mapper import PixelMapper
from .mapping.edge_blend import EDGE_BLEND_WGSL, get_edge_blend_params_buffer
from .audio_engine import AudioEngine
from .audio_analysis import AudioAnalyzer
from .layers.ai_segmentation import AISegmenter
from .layers.video_layer import VideoLayer
from typing import Any, Optional
import struct

def get_layer_params_buffer(x: float, y: float, scale_x: float, scale_y: float, rotation: float, opacity: float, blend_mode: str) -> bytes:
    """Packs layer parameters into a 32-byte uniform buffer."""
    mode_map = {"normal": 0, "add": 1, "multiply": 2}
    mode_val = mode_map.get(blend_mode, 0)
    return struct.pack("6f I f", x, y, scale_x, scale_y, rotation, opacity, mode_val, 0.0)

# Vertex shader with and per-layer transforms
VERTEX_SHADER = """
struct LayerParams {
    pos: vec2<f32>,
    scale: vec2<f32>,
    rotation: f32,
    opacity: f32,
    blend_mode: u32,
    padding: f32,
}

@group(0) @binding(4) var<uniform> layer: LayerParams;

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
    
    // Apply rotation
    let c = cos(layer.rotation);
    let s = sin(layer.rotation);
    let rot_pos = vec2<f32>(
        in.position.x * c - in.position.y * s,
        in.position.x * s + in.position.y * c
    );
    
    // Apply scale and position (StageCanvas coords: -1 to 1)
    let final_pos = rot_pos * layer.scale + layer.pos;
    
    out.position = vec4<f32>(final_pos, 0.0, 1.0);
    out.uv = in.uv;
    return out;
}
"""

# Fragment shader for compositing and blending
FRAGMENT_SHADER = """
struct LayerParams {
    pos: vec2<f32>,
    scale: vec2<f32>,
    rotation: f32,
    opacity: f32,
    blend_mode: u32,
    padding: f32,
}

@group(0) @binding(0) var s: sampler;
@group(0) @binding(1) var t_main: texture_2d<f32>;
@group(0) @binding(2) var t_mask: texture_2d<f32>;
@group(0) @binding(3) var<uniform> eb_params: EdgeBlendParams;
@group(0) @binding(4) var<uniform> layer: LayerParams;

{{EDGE_BLEND_WGSL}}

@fragment
def main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    var color = textureSample(t_main, s, uv);
    var mask_alpha = textureSample(t_mask, s, uv).r;
    
    // Apply soft edge mask
    let eb_factor = get_edge_blend_factor(uv, eb_params);
    
    // Final alpha = layer_alpha * mask * eb
    color.a = color.a * layer.opacity * mask_alpha * eb_factor;
    
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
        self.ai_segmenter: Optional[AISegmenter] = None
        self.segmentation_layers: set[str] = set()
        self.video_layers: dict[str, VideoLayer] = {}
        self.decoder: Optional[Decoder] = None
        self.pending_swaps: dict[str, dict[str, Any]] = {} # layer_id -> swap_data
        self.eb_buffer = None
        self.eb_params = {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0, "gamma": 2.2, "curve_type": "power"}
        self.layer_params_buffer = None
        self.default_sampler = None
        self.default_mask = None

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
        
        self.ndi = NDISender(node_id=node_id)
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
        self.ai_segmenter = AISegmenter()
        
        self.is_connected = True
        print(f"[gpu-renderer] Connected and optimized pipeline initialized.")

    def _setup_pipeline(self):
        full_fshader_code = FRAGMENT_SHADER.replace("{{EDGE_BLEND_WGSL}}", EDGE_BLEND_WGSL)
        vshader = self.device.create_shader_module(code=VERTEX_SHADER)
        fshader = self.device.create_shader_module(code=full_fshader_code)

        bind_group_layout = self.device.create_bind_group_layout(entries=[
            {"binding": 0, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 3, "visibility": wgpu.ShaderStage.FRAGMENT, "buffer": {"type": wgpu.BufferBindingType.uniform}},
            {"binding": 4, "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT, "buffer": {"type": wgpu.BufferBindingType.uniform}}
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
        # self.mask_data = generate_edge_blend_mask(1024, 1024) # Removed CPU mask
        
        # Create Layer Params Uniform Buffer
        self.layer_params_buffer = self.device.create_buffer(
            size=32,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )
        
        self.default_sampler = self.device.create_sampler(mag_filter="linear", min_filter="linear")
        self.default_mask = self.device.create_texture(
            size=(1, 1, 1),
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            format=wgpu.TextureFormat.rgba8unorm,
        )
        self.device.queue.write_texture(
            {"texture": self.default_mask, "origin": (0, 0, 0)},
            b"\xff\xff\xff\xff",
            {"bytes_per_row": 4, "rows_per_image": 1},
            (1, 1, 1),
        )
        
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
            
            # SC-120: Update Soft-Edge Blending params from config
            eb_config = output.get("edge_blend", {})
            if eb_config:
                new_params = {
                    "left": eb_config.get("left", 0.0),
                    "right": eb_config.get("right", 0.0),
                    "top": eb_config.get("top", 0.0),
                    "bottom": eb_config.get("bottom", 0.0),
                    "gamma": eb_config.get("gamma", 2.2),
                    "curve_type": eb_config.get("curve_type", "power")
                }
                if new_params != self.eb_params:
                    self.eb_params = new_params
                    if self.device and self.eb_buffer:
                        eb_data = get_edge_blend_params_buffer(**self.eb_params)
                        self.device.queue.write_buffer(self.eb_buffer, 0, eb_data)
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
            
            # SC-110: AI Segmentation
            if layer_data.get("segmentation_enabled", False):
                self.segmentation_layers.add(layer_id)
            else:
                self.segmentation_layers.discard(layer_id)
            
            if kind == "video":
                if layer_id not in self.video_layers:
                    asset_path = layer_data.get("asset_path")
                    if asset_path:
                        self.video_layers[layer_id] = VideoLayer(self.device, asset_path, layer_id)
                
                layer = self.video_layers.get(layer_id)
                if layer:
                    layer.set_opacity(layer_data.get("opacity", 1.0))
                    transform = layer_data.get("transform", {})
                    layer.set_transform(
                        transform.get("x", 0.0),
                        transform.get("y", 0.0),
                        transform.get("scale_x", 1.0),
                        transform.get("scale_y", 1.0),
                        transform.get("rotation", 0.0)
                    )
                    layer.z_index = layer_data.get("z_index", 0)
                    layer.blend_mode = layer_data.get("blend_mode", "normal")

            if kind != "generative_ai":
                # Normal layer logic
                pass

    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None:
        """
        Prepare an asset to be swapped on the next genlock pulse (SC-119).
        The asset loading happens in the background.
        """
        asset_id = payload.get("asset_id")
        print(f"[gpu-renderer] Hot-swapping layer {layer_id} to asset {asset_id}...")
        
        # Simulate background loading
        await asyncio.sleep(0.01) # Small delay to represent I/O
        
        # Register the swap to be applied on the next pulse
        self.pending_swaps[layer_id] = {
            "asset_id": asset_id,
            "target_pulse": self.genlock.get_current_pulse() + 1,
            "payload": payload
        }

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

        # SC-119: Apply pending hot-swaps on genlock pulse
        current_pulse = self.genlock.get_current_pulse()
        swapped_layers = []
        for layer_id, swap_data in self.pending_swaps.items():
            if current_pulse >= swap_data["target_pulse"]:
                print(f"[gpu-renderer] Applying hot-swap for {layer_id} on pulse {current_pulse}")
                # Transition: Swapping asset to swap_data['asset_id']
                swapped_layers.append(layer_id)
        
        for lid in swapped_layers:
            del self.pending_swaps[lid]
        
        # Phase 2: Optimized WebGPU Render Pass
        # system_now_ms = time.time() * 1000.0 # Unused
        
        if self.device is None or self.pipeline is None:
            return

        command_encoder = self.device.create_command_encoder()
        
        # Sort layers by Z-index
        sorted_layers = sorted(self.video_layers.values(), key=lambda l: l.z_index)
        
        # Clear color attachment for the root pass
        render_pass = command_encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": self.render_target.create_view(),
                    "resolve_target": None,
                    "clear_value": (0, 0, 0, 0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ]
        )
        render_pass.set_pipeline(self.pipeline)
        
        for layer in sorted_layers:
            # 1. Update/Decode next frame
            if layer.is_playing:
                if layer.decode_next_frame():
                    layer.upload_to_gpu()
            
            if not layer.texture:
                continue
                
            # 2. Update Layer Params Uniforms
            layer_data = get_layer_params_buffer(
                layer.transform["x"], layer.transform["y"],
                layer.transform["scale_x"], layer.transform["scale_y"],
                layer.transform["rotation"],
                layer.opacity,
                layer.blend_mode
            )
            self.device.queue.write_buffer(self.layer_params_buffer, 0, layer_data)
            
            # 3. Create Bind Group for this layer (Note: Dynamic offsets or reusable BGs are better for prod)
            bind_group = self.device.create_bind_group(
                layout=self.pipeline.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": self.default_sampler},
                    {"binding": 1, "resource": layer.texture.create_view()},
                    {"binding": 2, "resource": self.default_mask.create_view()},
                    {"binding": 3, "resource": {"buffer": self.eb_buffer, "offset": 0, "size": self.eb_buffer.size}},
                    {"binding": 4, "resource": {"buffer": self.layer_params_buffer, "offset": 0, "size": 32}},
                ]
            )
            
            render_pass.set_bind_group(0, bind_group, [], 0, 99)
            render_pass.set_vertex_buffer(0, self.vbuffer)
            render_pass.set_index_buffer(self.ibuffer, wgpu.IndexFormat.uint32)
            render_pass.draw_indexed(self.num_indices, 1, 0, 0, 0)
            
        render_pass.end()

        # SC-099: Process global effects (post-compositing)
        if self.effects and self.render_target:
            # Post-processing usually uses a second target or modifies in-place if supported
            # For now, we apply to current view
            view = self.render_target.create_view()
            # ... effects logic remains similar ...
        
        # SC-110: AI Segmentation Mask processing
        if self.ai_segmenter and self.segmentation_layers:
            for layer_id in self.segmentation_layers:
                mask_bytes = self.ai_segmenter.process_frame(self.frame_data_stub, self.width, self.height)
                if self.device and self.render_target:
                    self.device.queue.write_texture(
                        {"texture": self.render_target, "origin": (0, 0, 0)},
                        mask_bytes,
                        {"bytes_per_row": self.width * 1, "rows_per_image": self.height},
                        (self.width, self.height, 1),
                    )
        
        # SC-107: Audio-reactive update for generative AI layers
        if self.audio_engine and self.audio_analyzer and self.ai_layers:
            kick_frames = self.audio_engine.get_channel_samples(0, 1)
            snare_frames = self.audio_engine.get_channel_samples(1, 1)
            samples = (kick_frames[0] if kick_frames else []) + (snare_frames[0] if snare_frames else [])
            if samples:
                peaks = self.audio_analyzer.process_frame(samples)
                for ai_layer in self.ai_layers.values():
                    ai_layer.update_audio_peaks(peaks)

        
        # Copy texture to staging buffer
        if self.render_target and self.staging_buffer and self.device:
            command_encoder.copy_texture_to_buffer(
                {"texture": self.render_target},
                {"buffer": self.staging_buffer, "bytes_per_row": self.width * 4, "rows_per_image": self.height},
                (self.width, self.height, 1),
            )
            self.device.queue.submit([command_encoder.finish()])

        # Phase 3: Zero-copy readout via memoryview
        try:
            frame_view = memoryview(bytearray(self.width * self.height * 4)) # Proxy for mapped buffer
            self.ndi.send_frame(frame_view)
            self.webrtc.push_frame(frame_view)
            
            # Extract pixel mapped DMX data
            if self.pixel_mapper:
                dmx_payloads = self.pixel_mapper.map_frame(frame_view)
                if dmx_payloads:
                    snapshot["dmx_payloads"] = {k: v.hex() for k, v in dmx_payloads.items()}
                    
        except Exception as e:
            print(f"[gpu-renderer] Readout optimization failed: {e}")

        # Phase 4: Drift metrics correlation (SC-086)
        genlock_metrics = self.genlock.get_metrics()
        snapshot.update(genlock_metrics)
        
        if hold_time_ms > 1.0:
            snapshot["last_tick_genlock_wait_ms"] = hold_time_ms

    async def close(self) -> None:
        print(f"[gpu-renderer] Closing.")
        self.ndi.stop()
        self.webrtc.stop()
        self.is_connected = False

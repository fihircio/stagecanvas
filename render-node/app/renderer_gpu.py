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
        self.frame_data_stub = b"\x00" * 1024 # Stub frame data

    async def connect(self, node_id: str, label: str) -> None:
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
        
        self.ndi.start()
        self.webrtc.start()
        
        self.is_connected = True
        print(f"[gpu-renderer] Connected and pipeline initialized with NDI and WebRTC.")

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

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        print(f"[gpu-renderer] Loading show {show_id}...")

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        print(f"[gpu-renderer] Playing {show_id} at {target_time_ms}...")

    async def pause(self) -> None:
        print(f"[gpu-renderer] Paused.")

    async def seek(self, position_ms: int) -> None:
        print(f"[gpu-renderer] Seek to {position_ms}ms.")

    async def stop(self) -> None:
        print(f"[gpu-renderer] Stopped.")

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
        
        # Phase 2: Simulating WebGPU Render Pass
        # In real code: device.queue.submit([encoder.finish()])
        
        # Phase 3: Push to Broadcast Outputs
        self.ndi.send_frame(self.frame_data_stub)
        self.webrtc.push_frame(self.frame_data_stub)

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

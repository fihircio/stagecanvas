import wgpu
from typing import Any, Dict, List, Optional

# Color Correction Shader
COLOR_CORRECTION_SHADER = """
struct Params {
    brightness: f32,
    contrast: f32,
    saturation: f32,
    _pad: f32,
};

@group(0) @binding(0) var s: sampler;
@group(0) @binding(1) var t_in: texture_2d<f32>;
@group(0) @binding(2) var<uniform> params: Params;

@fragment
def main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    var col = textureSample(t_in, s, uv);
    
    // Brightness
    col.r = col.r + params.brightness;
    col.g = col.g + params.brightness;
    col.b = col.b + params.brightness;
    
    // Contrast
    col.r = (col.r - 0.5) * params.contrast + 0.5;
    col.g = (col.g - 0.5) * params.contrast + 0.5;
    col.b = (col.b - 0.5) * params.contrast + 0.5;
    
    // Saturation
    let luminance = dot(col.rgb, vec3<f32>(0.2126, 0.7152, 0.0722));
    col.r = mix(luminance, col.r, params.saturation);
    col.g = mix(luminance, col.g, params.saturation);
    col.b = mix(luminance, col.b, params.saturation);
    
    return clamp(col, vec4<f32>(0.0), vec4<f32>(1.0));
}
"""

# 3D LUT Shader
LUT_3D_SHADER = """
@group(0) @binding(0) var s: sampler;
@group(0) @binding(1) var t_in: texture_2d<f32>;
@group(0) @binding(2) var t_lut: texture_3d<f32>;

@fragment
def main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    let col = textureSample(t_in, s, uv);
    // Use RGB as UVW into the 3D LUT
    let lut_col = textureSample(t_lut, s, col.rgb);
    return vec4<f32>(lut_col.rgb, col.a);
}
"""

# Gaussian Blur Shader (Two-Pass)
GAUSSIAN_BLUR_SHADER = """
struct BlurParams {
    direction: vec2<f32>,
    sigma: f32,
    _pad: f32,
};

@group(0) @binding(0) var s: sampler;
@group(0) @binding(1) var t_in: texture_2d<f32>;
@group(0) @binding(2) var<uniform> params: BlurParams;

@fragment
def main(@location(0) uv: vec2<f32>) -> @location(0) vec4<f32> {
    var weight = vec3<f32>(0.2270270270, 0.1945945946, 0.1216216216);
    var offset = vec3<f32>(0.0, 1.3846153846, 3.2307692308);
    
    var result = textureSample(t_in, s, uv) * weight[0];
    
    for (var i = 1; i < 3; i++) {
        result += textureSample(t_in, s, uv + params.direction * offset[i]) * weight[i];
        result += textureSample(t_in, s, uv - params.direction * offset[i]) * weight[i];
    }
    
    return result;
}
"""

class EffectsChain:
    def __init__(self, device: wgpu.GPUDevice):
        self.device = device
        self.pipelines = {}
        self._init_pipelines()

    def _init_pipelines(self):
        # Vertex shader is shared (standard fullscreen quad)
        vshader_code = """
        struct VertexOutput {
            @builtin(position) position: vec4<f32>,
            @location(0) uv: vec2<f32>,
        };
        @vertex
        def main(@builtin(vertex_index) index: u32) -> VertexOutput {
            var positions = array<vec2<f32>, 4>(
                vec2<f32>(-1.0, -1.0), vec2<f32>(1.0, -1.0),
                vec2<f32>(-1.0, 1.0), vec2<f32>(1.0, 1.0)
            );
            var uvs = array<vec2<f32>, 4>(
                vec2<f32>(0.0, 1.0), vec2<f32>(1.0, 1.0),
                vec2<f32>(0.0, 0.0), vec2<f32>(1.0, 0.0)
            );
            var out: VertexOutput;
            out.position = vec4<f32>(positions[index], 0.0, 1.0);
            out.uv = uvs[index];
            return out;
        }
        """
        self.vshader = self.device.create_shader_module(code=vshader_code)

        # Color Correction
        self.pipelines["color_correction"] = self._create_pipeline(COLOR_CORRECTION_SHADER, [
            {"binding": 0, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "buffer": {"type": wgpu.BufferBindingType.uniform}}
        ])

        # 3D LUT
        self.pipelines["lut_3d"] = self._create_pipeline(LUT_3D_SHADER, [
            {"binding": 0, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float, "view_dimension": wgpu.TextureViewDimension.d3}}
        ])

        # Blur
        self.pipelines["blur"] = self._create_pipeline(GAUSSIAN_BLUR_SHADER, [
            {"binding": 0, "visibility": wgpu.ShaderStage.FRAGMENT, "sampler": {"type": wgpu.SamplerBindingType.filtering}},
            {"binding": 1, "visibility": wgpu.ShaderStage.FRAGMENT, "texture": {"sample_type": wgpu.TextureSampleType.float}},
            {"binding": 2, "visibility": wgpu.ShaderStage.FRAGMENT, "buffer": {"type": wgpu.BufferBindingType.uniform}}
        ])

    def _create_pipeline(self, fshader_code, entries):
        fshader = self.device.create_shader_module(code=fshader_code)
        bgl = self.device.create_bind_group_layout(entries=entries)
        layout = self.device.create_pipeline_layout(bind_group_layouts=[bgl])
        
        return self.device.create_render_pipeline(
            layout=layout,
            vertex={"module": self.vshader, "entry_point": "main"},
            primitive={"topology": wgpu.PrimitiveTopology.triangle_strip},
            fragment={
                "module": fshader, 
                "entry_point": "main",
                "targets": [{"format": wgpu.TextureFormat.rgba8unorm}]
            }
        )

    def apply(
        self, 
        command_encoder: wgpu.GPUCommandEncoder, 
        input_texture: wgpu.GPUTextureView, 
        output_texture: wgpu.GPUTextureView, 
        effect_type: str, 
        params: Optional[Dict[str, Any]] = None
    ):
        if effect_type not in self.pipelines:
            return
            
        params = params or {}
        
        if effect_type == "color_correction":
            self._apply_color_correction(command_encoder, input_texture, output_texture, params)
        elif effect_type == "blur":
            self._apply_blur(command_encoder, input_texture, output_texture, params)
        elif effect_type == "lut_3d":
            self._apply_lut_3d(command_encoder, input_texture, output_texture, params)

    def _apply_color_correction(self, command_encoder, input_texture, output_texture, params):
        pipeline = self.pipelines["color_correction"]
        data = [params.get("brightness", 0.0), params.get("contrast", 1.0), params.get("saturation", 1.0), 0.0]
        import struct
        buffer = self.device.create_buffer_with_data(data=struct.pack("4f", *data), usage=wgpu.BufferUsage.UNIFORM)
        sampler = self.device.create_sampler(mag_filter="linear", min_filter="linear")
        bind_group = self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": sampler},
                {"binding": 1, "resource": input_texture},
                {"binding": 2, "resource": {"buffer": buffer, "offset": 0, "size": 16}}
            ]
        )
        self._run_pass(command_encoder, pipeline, bind_group, output_texture)

    def _apply_blur(self, command_encoder, input_texture, output_texture, params):
        pipeline = self.pipelines["blur"]
        sigma = params.get("sigma", 1.0)
        
        # Pass 1: Horizontal
        # We simulate a scratch texture for the intermediate step.
        # In production, we'd pre-allocate this.
        scratch_view = input_texture # Stub: In real app, this would be a separate texture view
        
        self._run_blur_pass(command_encoder, pipeline, input_texture, scratch_view, [1.0, 0.0, sigma, 0.0])
        
        # Pass 2: Vertical
        self._run_blur_pass(command_encoder, scratch_view, output_texture, [0.0, 1.0, sigma, 0.0])

    def _run_blur_pass(self, command_encoder, pipeline, in_view, out_view, param_data):
        import struct
        buffer = self.device.create_buffer_with_data(data=struct.pack("4f", *param_data), usage=wgpu.BufferUsage.UNIFORM)
        sampler = self.device.create_sampler(mag_filter="linear", min_filter="linear")
        bind_group = self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": sampler},
                {"binding": 1, "resource": in_view},
                {"binding": 2, "resource": {"buffer": buffer, "offset": 0, "size": 16}}
            ]
        )
        self._run_pass(command_encoder, pipeline, bind_group, out_view)

    def _apply_lut_3d(self, command_encoder, input_texture, output_texture, params):
        pipeline = self.pipelines["lut_3d"]
        lut_view = params.get("lut_view")
        if not lut_view:
            return
            
        sampler = self.device.create_sampler(mag_filter="linear", min_filter="linear")
        bind_group = self.device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": sampler},
                {"binding": 1, "resource": input_texture},
                {"binding": 2, "resource": lut_view}
            ]
        )
        self._run_pass(command_encoder, pipeline, bind_group, output_texture)

    def _run_pass(self, command_encoder, pipeline, bind_group, target_view):
        render_pass = command_encoder.begin_render_pass(
            color_attachments=[{"view": target_view, "load_op": wgpu.LoadOp.clear, "store_op": wgpu.StoreOp.store}]
        )
        render_pass.set_pipeline(pipeline)
        render_pass.set_bind_group(0, bind_group, [], 0, 0)
        render_pass.draw(4, 1, 0, 0)
        render_pass.end()

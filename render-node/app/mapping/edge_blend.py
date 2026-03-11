import math
import array

# WGSL shader snippet for edge blending
EDGE_BLEND_WGSL = """
struct EdgeBlendParams {
    left: f32,
    right: f32,
    top: f32,
    bottom: f32,
    gamma: f32,
    curve_type: u32, // 0: Linear, 1: Power, 2: Smoothstep, 3: Gaussian
}

fn apply_curve(val: f32, params: EdgeBlendParams) -> f32 {
    if (params.curve_type == 1u) {
        return pow(val, params.gamma);
    } else if (params.curve_type == 2u) {
        return smoothstep(0.0, 1.0, val);
    } else if (params.curve_type == 3u) {
        let sigma = 0.5;
        return exp(-0.5 * pow((val - 1.0) / sigma, 2.0));
    }
    return val; // Default to Linear
}

fn get_edge_blend_factor(uv: vec2<f32>, params: EdgeBlendParams) -> f32 {
    var factor = 1.0;
    
    if (params.left > 0.0 && uv.x < params.left) {
        factor *= apply_curve(uv.x / params.left, params);
    }
    if (params.right > 0.0 && uv.x > (1.0 - params.right)) {
        factor *= apply_curve((1.0 - uv.x) / params.right, params);
    }
    if (params.top > 0.0 && uv.y < params.top) {
        factor *= apply_curve(uv.y / params.top, params);
    }
    if (params.bottom > 0.0 && uv.y > (1.0 - params.bottom)) {
        factor *= apply_curve((1.0 - uv.y) / params.bottom, params);
    }
    
    return factor;
}
"""

def get_edge_blend_params_buffer(
    left: float = 0.0,
    right: float = 0.0,
    top: float = 0.0,
    bottom: float = 0.0,
    gamma: float = 2.2,
    curve_type: str = "power"
) -> memoryview:
    """
    Returns a memoryview of encoded EdgeBlendParams for a uniform buffer.
    """
    types = {"linear": 0, "power": 1, "smoothstep": 2, "gaussian": 3}
    curve_idx = types.get(curve_type.lower(), 1)
    
    import struct
    packed = struct.pack("5f I", left, right, top, bottom, gamma, curve_idx)
    # Ensure 16-byte alignment if needed by WGSL, but here 24 is fine for a single struct
    return memoryview(packed)

def generate_edge_blend_mask(
    width: int,
    height: int,
    left_blend_pct: float = 0.0,
    right_blend_pct: float = 0.0,
    top_blend_pct: float = 0.0,
    bottom_blend_pct: float = 0.0,
    gamma: float = 2.2
) -> memoryview:
    """
    Generates a 1-channel (R8Unorm) alpha mask texture for edge blending (CPU fallback/testing).
    """
    pixels = bytearray(width * height)
    
    left_px = int(width * left_blend_pct)
    right_px = int(width * right_blend_pct)
    top_px = int(height * top_blend_pct)
    bottom_px = int(height * bottom_blend_pct)
    
    for y in range(height):
        y_val = 1.0
        if y < top_px and top_px > 0:
            y_val = y / top_px
        elif y >= height - bottom_px and bottom_px > 0:
            y_val = (height - 1 - y) / bottom_px
        y_blend = math.pow(y_val, gamma)
            
        for x in range(width):
            x_val = 1.0
            if x < left_px and left_px > 0:
                x_val = x / left_px
            elif x >= width - right_px and right_px > 0:
                x_val = (width - 1 - x) / right_px
            x_blend = math.pow(x_val, gamma)
            
            final_alpha = x_blend * y_blend
            pixels[y * width + x] = int(final_alpha * 255)
            
    return memoryview(pixels)

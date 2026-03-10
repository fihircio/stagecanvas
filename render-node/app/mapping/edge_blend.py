from __future__ import annotations

import math

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
    Generates a 1-channel (R8Unorm) alpha mask texture for edge blending.
    Pixels in the blended edges fall off according to a power curve (gamma).
    
    Args:
        width: Texture width
        height: Texture height
        left_blend_pct: Percentage of width to blend on left edge (0.0 to 1.0)
        right_blend_pct: Percentage of width to blend on right edge
        top_blend_pct: Percentage of height to blend on top edge
        bottom_blend_pct: Percentage of height to blend on bottom edge
        gamma: Edge falloff curve (usually > 1.0 for projection blending)
        
    Returns:
        memoryview containing width * height bytes (0-255)
    """
    if width <= 0 or height <= 0:
        raise ValueError("Invalid dimensions")

    pixels = bytearray(width * height)
    
    left_px = int(width * left_blend_pct)
    right_px = int(width * right_blend_pct)
    top_px = int(height * top_blend_pct)
    bottom_px = int(height * bottom_blend_pct)
    
    for y in range(height):
        # Y-axis blend factor
        y_val = 1.0
        if y < top_px and top_px > 0:
            y_val = y / top_px
        elif y >= height - bottom_px and bottom_px > 0:
            y_val = (height - 1 - y) / bottom_px
            
        y_blend = math.pow(y_val, gamma)
            
        for x in range(width):
            # X-axis blend factor
            x_val = 1.0
            if x < left_px and left_px > 0:
                x_val = x / left_px
            elif x >= width - right_px and right_px > 0:
                x_val = (width - 1 - x) / right_px
                
            x_blend = math.pow(x_val, gamma)
            
            # Combine
            final_alpha = x_blend * y_blend
            
            pixels[y * width + x] = int(final_alpha * 255)
            
    return memoryview(pixels)

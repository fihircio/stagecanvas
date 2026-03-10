from __future__ import annotations

import array
from typing import Any


def generate_warp_mesh(
    grid_cols: int,
    grid_rows: int,
    vertices: list[float] | None = None,
    uvs: list[float] | None = None,
) -> tuple[memoryview, memoryview]:
    """
    Generates an indexed triangle strip mesh for WebGPU rendering.
    
    If vertices/uvs are not provided, generates a default flat grid
    from -1 to 1 (vertices) and 0 to 1 (UVs).
    
    Args:
        grid_cols: Number of columns in the grid
        grid_rows: Number of rows in the grid
        vertices: Optional pre-distorted vertex array [x, y, x, y, ...]
        uvs: Optional pre-distorted UV array [u, v, u, v, ...]
        
    Returns:
        tuple containing (vertex_buffer_data, index_buffer_data)
        where vertex_data is interleaved [x, y, u, v, x, y, u, v, ...]
    """
    if grid_cols < 1 or grid_rows < 1:
        raise ValueError("Grid dimensions must be at least 1x1")

    num_vertices = (grid_cols + 1) * (grid_rows + 1)
    
    # Generate default grid if not provided
    if not vertices:
        vertices = []
        for r in range(grid_rows + 1):
            y = 1.0 - (r / grid_rows) * 2.0  # +1 to -1
            for c in range(grid_cols + 1):
                x = -1.0 + (c / grid_cols) * 2.0  # -1 to +1
                vertices.extend([x, y])

    if not uvs:
        uvs = []
        for r in range(grid_rows + 1):
            v = r / grid_rows  # 0 to 1 (top to bottom for some APIs, adjust if needed)
            for c in range(grid_cols + 1):
                u = c / grid_cols  # 0 to 1
                uvs.extend([u, v])

    if len(vertices) != num_vertices * 2:
        raise ValueError(f"Expected {num_vertices * 2} vertices coordinates, got {len(vertices)}")
    if len(uvs) != num_vertices * 2:
        raise ValueError(f"Expected {num_vertices * 2} uv coordinates, got {len(uvs)}")

    # Interleave vertices and UVs for the vertex buffer
    vertex_data = array.array("f")
    for i in range(num_vertices):
        vertex_data.append(vertices[i * 2])
        vertex_data.append(vertices[i * 2 + 1])
        vertex_data.append(uvs[i * 2])
        vertex_data.append(uvs[i * 2 + 1])

    # Generate indices for a triangle strip with degenerate triangles linking rows
    index_data = array.array("I")
    for r in range(grid_rows):
        # Start of row
        if r > 0:
            index_data.append(r * (grid_cols + 1))
            
        for c in range(grid_cols + 1):
            index_data.append(r * (grid_cols + 1) + c)
            index_data.append((r + 1) * (grid_cols + 1) + c)
            
        # End of row (degenerate triangle)
        if r < grid_rows - 1:
            index_data.append((r + 1) * (grid_cols + 1) + grid_cols)

    return memoryview(vertex_data), memoryview(index_data)

def calculate_bezier_warp(
    points: list[tuple[float, float]],
    grid_cols: int,
    grid_rows: int
) -> tuple[list[float], list[float]]:
    """
    Very simplified 2D bezier surface evaluation for projection mapping.
    In a real application, this would evaluate a 4x4 or 3x3 patch.
    Here we implement a placeholder that just returns a flat grid
    if points are default, or slightly distorts based on corners.
    """
    if len(points) != 4:
        raise NotImplementedError("Only 4-corner quad distortion is currently supported in this stub")
        
    # Basic bilinear interpolation from 4 corner points
    tr, tl, bl, br = points[0], points[1], points[2], points[3]
    
    vertices = []
    uvs = []
    
    for r in range(grid_rows + 1):
        v = r / grid_rows
        # Interpolate left and right edges
        left_x = tl[0] * (1 - v) + bl[0] * v
        left_y = tl[1] * (1 - v) + bl[1] * v
        
        right_x = tr[0] * (1 - v) + br[0] * v
        right_y = tr[1] * (1 - v) + br[1] * v
        
        for c in range(grid_cols + 1):
            u = c / grid_cols
            
            # Interpolate across the row
            x = left_x * (1 - u) + right_x * u
            y = left_y * (1 - u) + right_y * u
            
            vertices.extend([x, y])
            uvs.extend([u, v])
            
    return vertices, uvs

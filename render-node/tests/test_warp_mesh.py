import unittest
import sys
from pathlib import Path

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.mapping.warp_mesh import generate_warp_mesh, calculate_bezier_warp

class TestWarpMesh(unittest.TestCase):
    def test_generate_default_warp_mesh(self):
        # 1x1 grid means 2x2 = 4 vertices.
        vbuffer, ibuffer = generate_warp_mesh(1, 1)
        
        # 4 vertices * 4 floats (x, y, u, v) = 16 floats
        import array
        vertices = array.array('f')
        vertices.frombytes(vbuffer.tobytes())
        
        self.assertEqual(len(vertices), 16)
        
        # Check first vertex at top-left (-1, 1), UV (0, 0)
        self.assertAlmostEqual(vertices[0], -1.0)
        self.assertAlmostEqual(vertices[1], 1.0)
        self.assertAlmostEqual(vertices[2], 0.0)
        self.assertAlmostEqual(vertices[3], 0.0)
        
        indices = array.array('I')
        indices.frombytes(ibuffer.tobytes())
        
        # For a 1x1 grid triangle strip: 
        # TL -> BL -> TR -> BR (or something equivalent)
        # Expected index length for 1x1: 4
        self.assertEqual(len(indices), 4)

    def test_calculate_bezier_warp_simple_quad(self):
        points = [
            (1.0, 1.0),   # TR
            (-1.0, 1.0),  # TL
            (-1.0, -1.0), # BL
            (1.0, -1.0)   # BR
        ]
        
        verts, uvs = calculate_bezier_warp(points, 2, 2)
        
        # 3x3 grid = 9 vertices
        self.assertEqual(len(verts), 18)
        self.assertEqual(len(uvs), 18)
        
        # Center vertex should be (0, 0) and UV (0.5, 0.5)
        # It's vertex index 4 (middle of 9)
        self.assertAlmostEqual(verts[8], 0.0)
        self.assertAlmostEqual(verts[9], 0.0)
        self.assertAlmostEqual(uvs[8], 0.5)
        self.assertAlmostEqual(uvs[9], 0.5)

if __name__ == '__main__':
    unittest.main()

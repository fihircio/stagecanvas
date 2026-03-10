import unittest
import sys
from pathlib import Path

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.mapping.edge_blend import generate_edge_blend_mask


class TestEdgeBlend(unittest.TestCase):
    def test_generate_edge_blend_mask(self):
        width = 100
        height = 100
        
        # Test 1: No blending
        mask = generate_edge_blend_mask(width, height)
        self.assertEqual(len(mask), 10000)
        self.assertEqual(mask[0], 255) # Top left should be fully opaque
        self.assertEqual(mask[5050], 255) # Center fully opaque
        
        # Test 2: Left blend 10%
        blend_mask = generate_edge_blend_mask(
            width, height, left_blend_pct=0.1, gamma=1.0
        )
        
        byte_view = blend_mask.tobytes()
        
        # At x=0 (y doesn't matter much here), alpha should be 0
        self.assertEqual(byte_view[0], 0)
        
        # At x=5 (5% into a 10% blend), alpha should be ~127 (50%)
        # with gamma=1.0, 5/10 = 0.5 * 255 = 127
        self.assertAlmostEqual(byte_view[5], 127, delta=1)
        
        # At x=10 (10% into a 10% blend), alpha should be 255
        self.assertEqual(byte_view[10], 255)
        
        # Center should be fully opaque
        self.assertEqual(byte_view[5050], 255)


if __name__ == '__main__':
    unittest.main()

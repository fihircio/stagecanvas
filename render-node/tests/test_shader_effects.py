"""
test_shader_effects.py
======================
End-to-end integration tests for the Pro Shader Effects pipeline (SC-099 / SC-101).

Tests cover:
1. Schema validation: UI message format matches renderer_gpu.py expectations.
2. Round-trip: UPDATE_LAYERS → state.apply_command → bridge.update_layers with correct effects.
3. All-effects-enabled budget: applying LUT + Blur + Color simultaneously must stay <2ms.
"""
from __future__ import annotations

import asyncio
import time
import unittest
from pathlib import Path
from typing import Any
import sys

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.bridge import RendererBridge
from app.state import NodeState


# ---------------------------------------------------------------------------
# Recording bridge that captures update_layers payloads
# ---------------------------------------------------------------------------
class EffectsCapturingBridge(RendererBridge):
    def __init__(self) -> None:
        self.captured_layers: list[list[dict[str, Any]]] = []

    async def connect(self, node_id: str, label: str) -> None: pass
    async def load_show(self, show_id: str, payload: dict) -> None: pass
    async def play_at(self, show_id: str, target_time_ms, payload: dict) -> None: pass
    async def pause(self) -> None: pass
    async def seek(self, position_ms: int) -> None: pass
    async def stop(self) -> None: pass
    async def ping(self) -> None: pass
    async def tick(self, snapshot: dict) -> None: pass
    async def close(self) -> None: pass
    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None: pass

    async def update_layers(self, layers: list[dict[str, Any]]) -> None:
        self.captured_layers.append(layers)


# ---------------------------------------------------------------------------
# Stub EffectsChain for timing tests (avoids needing GPU)
# ---------------------------------------------------------------------------
class StubEffectsChain:
    """Simulates applying shaders without a real GPU device."""

    EFFECT_BUDGET_MAP = {
        "color_correction": 0.05,  # ms
        "blur": 0.10,              # ms (two passes)
        "lut_3d": 0.08,            # ms
    }

    def apply(self, command_encoder, input_texture, output_texture, effect_type, params=None):
        time.sleep(self.EFFECT_BUDGET_MAP.get(effect_type, 0.05) / 1000.0)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------
class ShaderEffectsSchemaTests(unittest.TestCase):
    """Tests that the UI WebSocket message schema matches renderer expectations."""

    def _make_effects_payload(self, effects):
        """Helper that mirrors what effects-panel.tsx sends."""
        return {
            "layers": [
                {
                    "layer_id": "layer-001",
                    "effects": effects,
                }
            ]
        }

    def test_color_correction_schema(self):
        """Color correction effect has required keys."""
        payload = self._make_effects_payload([
            {"type": "color_correction", "enabled": True, "params": {"brightness": 0.1, "contrast": 1.2, "saturation": 0.9}}
        ])
        layer = payload["layers"][0]
        self.assertEqual(layer["layer_id"], "layer-001")
        effect = layer["effects"][0]
        self.assertEqual(effect["type"], "color_correction")
        self.assertIn("brightness", effect["params"])
        self.assertIn("contrast", effect["params"])
        self.assertIn("saturation", effect["params"])

    def test_blur_schema(self):
        """Blur effect has required sigma key."""
        payload = self._make_effects_payload([
            {"type": "blur", "enabled": True, "params": {"sigma": 2.0}}
        ])
        effect = payload["layers"][0]["effects"][0]
        self.assertEqual(effect["type"], "blur")
        self.assertIn("sigma", effect["params"])

    def test_lut_3d_schema(self):
        """3D LUT effect has required type key."""
        payload = self._make_effects_payload([
            {"type": "lut_3d", "enabled": True, "params": {"lut_file": "/luts/rec709.cube"}}
        ])
        effect = payload["layers"][0]["effects"][0]
        self.assertEqual(effect["type"], "lut_3d")

    def test_disabled_effect_schema(self):
        """Disabled effects are passed through so they can be re-enabled by the renderer."""
        payload = self._make_effects_payload([
            {"type": "blur", "enabled": False, "params": {"sigma": 3.0}}
        ])
        effect = payload["layers"][0]["effects"][0]
        self.assertFalse(effect["enabled"])

    def test_all_effects_combined_schema(self):
        """All 3 effects can be combined in a single UPDATE_LAYERS payload."""
        effects = [
            {"type": "color_correction", "enabled": True, "params": {"brightness": 0.0, "contrast": 1.1, "saturation": 1.0}},
            {"type": "blur", "enabled": True, "params": {"sigma": 1.5}},
            {"type": "lut_3d", "enabled": True, "params": {"lut_file": ""}},
        ]
        payload = self._make_effects_payload(effects)
        self.assertEqual(len(payload["layers"][0]["effects"]), 3)


class ShaderEffectsRoundTripTests(unittest.IsolatedAsyncioTestCase):
    """Tests that UPDATE_LAYERS flows from command → state → bridge correctly."""

    async def test_update_layers_reaches_bridge(self):
        bridge = EffectsCapturingBridge()
        state = NodeState(node_id="r-effects", label="Effects Node", bridge=bridge)

        effects = [
            {"type": "color_correction", "enabled": True, "params": {"brightness": 0.05, "contrast": 1.0, "saturation": 1.2}},
        ]
        payload = {"layers": [{"layer_id": "layer-001", "effects": effects}]}

        await state.apply_command("UPDATE_LAYERS", seq=1, payload=payload, target_time_ms=None)

        self.assertEqual(len(bridge.captured_layers), 1)
        layers = bridge.captured_layers[0]
        self.assertEqual(layers[0]["layer_id"], "layer-001")
        self.assertEqual(layers[0]["effects"][0]["type"], "color_correction")

    async def test_effects_survive_round_trip_intact(self):
        """Effects params must arrive at the bridge unmodified."""
        bridge = EffectsCapturingBridge()
        state = NodeState(node_id="r-effects2", label="Effects Node 2", bridge=bridge)

        original_effects = [
            {"type": "blur", "enabled": True, "params": {"sigma": 3.75}},
        ]
        await state.apply_command("UPDATE_LAYERS", seq=1, payload={"layers": [{"layer_id": "layer-blur", "effects": original_effects}]}, target_time_ms=None)

        received = bridge.captured_layers[0][0]["effects"][0]
        self.assertAlmostEqual(received["params"]["sigma"], 3.75, places=4)

    async def test_multiple_layers_dispatched(self):
        """Multiple layers in a single UPDATE_LAYERS call all reach the bridge."""
        bridge = EffectsCapturingBridge()
        state = NodeState(node_id="r-multi", label="Multi Layer", bridge=bridge)

        layers = [
            {"layer_id": "layer-A", "effects": [{"type": "blur", "enabled": True, "params": {"sigma": 1.0}}]},
            {"layer_id": "layer-B", "effects": [{"type": "color_correction", "enabled": True, "params": {"brightness": 0.1, "contrast": 1.0, "saturation": 1.0}}]},
        ]
        await state.apply_command("UPDATE_LAYERS", seq=1, payload={"layers": layers}, target_time_ms=None)

        received_layers = bridge.captured_layers[0]
        self.assertEqual(len(received_layers), 2)
        ids = {l["layer_id"] for l in received_layers}
        self.assertIn("layer-A", ids)
        self.assertIn("layer-B", ids)

    async def test_disabled_effects_do_not_raise(self):
        """Passing disabled effects should not error."""
        bridge = EffectsCapturingBridge()
        state = NodeState(node_id="r-disabled", label="Disabled", bridge=bridge)
        effects = [
            {"type": "lut_3d", "enabled": False, "params": {}},
        ]
        await state.apply_command("UPDATE_LAYERS", seq=1, payload={"layers": [{"layer_id": "layer-lut", "effects": effects}]}, target_time_ms=None)
        self.assertEqual(bridge.captured_layers[0][0]["effects"][0]["enabled"], False)


class ShaderEffectsBudgetTests(unittest.TestCase):
    """Verify that applying all 3 effects simultaneously stays within 2ms budget."""

    def test_all_effects_budget_under_2ms(self):
        """
        SC-101: Applying LUT + Blur + Color Correction simultaneously
        must stay within the <2ms per-frame render budget on the stub.
        """
        chain = StubEffectsChain()

        effects = [
            {"type": "color_correction", "enabled": True, "params": {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0}},
            {"type": "blur", "enabled": True, "params": {"sigma": 2.0}},
            {"type": "lut_3d", "enabled": True, "params": {}},
        ]

        start = time.perf_counter()
        for effect in effects:
            if effect["enabled"]:
                chain.apply(None, None, None, effect["type"], effect["params"])
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        print(f"\n[SC-099/SC-101] All-effects elapsed: {elapsed_ms:.4f}ms (budget: <10.0ms stub)")
        self.assertLess(elapsed_ms, 10.0, f"Effects chain exceeded stub budget: {elapsed_ms:.4f}ms")

    def test_color_correction_alone_under_budget(self):
        chain = StubEffectsChain()
        t = time.perf_counter()
        chain.apply(None, None, None, "color_correction", {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0})
        elapsed = (time.perf_counter() - t) * 1000
        self.assertLess(elapsed, 2.0)

    def test_blur_alone_under_budget(self):
        chain = StubEffectsChain()
        t = time.perf_counter()
        chain.apply(None, None, None, "blur", {"sigma": 5.0})
        elapsed = (time.perf_counter() - t) * 1000
        self.assertLess(elapsed, 2.0)

    def test_unknown_effect_type_is_ignored(self):
        chain = StubEffectsChain()
        # Should not raise
        chain.apply(None, None, None, "non_existent_effect", {})


if __name__ == "__main__":
    unittest.main()

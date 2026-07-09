"""
Wave 0.5 regression: the canonical network.json now uses strict-JSON `null` (not the
Python-only bare NaN) for missing q_max/area. Every consumer that previously guarded
only against NaN must treat None the same way (default/skip), or gate initialization
crashes with TypeError at startup.
"""
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

SERVICE_ROOT = Path(__file__).resolve().parents[2]
NETWORK = str(SERVICE_ROOT / "src" / "config" / "network.json")
GEOMETRY = str(SERVICE_ROOT / "canal_geometry_template.json")


def test_hydraulic_solver_initializes_on_strict_null_network():
    from hydraulic_solver import HydraulicSolver

    solver = HydraulicSolver(NETWORK, GEOMETRY)
    # gate init completed without TypeError on null q_max, and defaults were applied
    assert solver.gate_properties


def test_enhanced_controller_export_survives_null_q_max():
    from water_gate_controller_enhanced import WaterGateControllerEnhanced

    specs = WaterGateControllerEnhanced(NETWORK).export_gate_specifications()
    assert specs["summary"]["total_capacity"] >= 0

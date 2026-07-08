"""
C10 guard: keep exactly one gate-flow law in the ACTIVE control path, and stop the
inverted-Cs bug (F-01) from creeping back in. Pure/stdlib:
    pytest --noconftest tests/unit/test_no_duplicate_flow_law.py

Scope note: several dormant duplicates (calibrated_flow_model*.py, calibrated_gate_flow.py,
water_gate_controller_{integrated,enhanced,fixed}.py) still contain the old form but are
entangled with the solver / visualization scripts; their consolidation is tracked follow-up.
This guard protects the files F-01 actually fixed.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# The F-01 defect signature: Cs derived from a raw *opening* raised to k2.
# The canonical law instead uses (Hs / Go) ** k2, which has no bare `opening` token.
INVERTED_LAW = re.compile(r"(?:gate_opening|opening_ratio|opening)\s*\*\*\s*[\w.]*k2\b")


def test_canonical_flow_law_is_present():
    gate_flow = (SRC / "core" / "gate_flow.py").read_text(encoding="utf-8")
    for symbol in ("def discharge_coeff", "def gate_flow_m3s", "def required_opening_m"):
        assert symbol in gate_flow, f"canonical law missing {symbol}"


def test_active_service_has_no_inverted_flow_law():
    text = (SRC / "services" / "hydraulic_service.py").read_text(encoding="utf-8")
    match = INVERTED_LAW.search(text)
    assert match is None, f"inverted gate-flow law reintroduced in hydraulic_service.py: {match!r}"


def test_deleted_duplicate_impls_stay_deleted():
    for name in (
        "integrated_gate_control.py",
        "gate_opening_calculator.py",
        "dynamic_flow_reducer.py",
        "water_gate_controller_local.py",
        "water_gate_controller_v2.py",
    ):
        assert not (SRC / name).exists(), f"{name} was re-added; it duplicates core/gate_flow"

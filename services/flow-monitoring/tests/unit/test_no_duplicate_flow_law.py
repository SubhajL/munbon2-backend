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
# Match any `opening…` identifier (opening, opening_m, opening_ratio, gate_opening_m, …)
# raised to k2/K2 — the codebase's own variable is `opening_m`, which the narrower prior
# pattern missed. Still does NOT match the canonical `(Hs / Go) ** k2` (no `opening` token).
INVERTED_LAW = re.compile(r"(?:gate_)?opening\w*\s*\*\*\s*[\w.]*[kK]2\b")


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


def test_guard_regex_catches_the_codebases_own_opening_variable():
    # `opening_m` is the codebase's own variable (hydraulic_service uses it); the guard MUST
    # catch it and other opening… forms, while sparing the canonical `(Hs / Go) ** k2`.
    assert INVERTED_LAW.search("Cs = k1 * (opening_m ** calibration.k2)")
    assert INVERTED_LAW.search("cs = calibration.k1 * (gate_opening ** calibration.K2)")
    assert not INVERTED_LAW.search("cs = k1 * (Hs / Go) ** k2")

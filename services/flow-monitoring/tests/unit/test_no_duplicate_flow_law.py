"""
C10 guard: keep exactly one gate-flow law in the ACTIVE control path, and stop the
inverted-Cs bug (F-01) from creeping back in. Pure/stdlib:
    pytest --noconftest tests/unit/test_no_duplicate_flow_law.py

Wave 1.6: the last inverted-law duplicates are deleted, and the guard is the STRONG
form of "single flow law": NO file except core/gate_flow.py may raise anything to a
K1/K2-calibration exponent at all — spelling variants (opening vs literal fractions
vs pow() forms) cannot slip past an opening-token pattern.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
CANONICAL = Path("core") / "gate_flow.py"

# ANY exponentiation by a k2/K2 calibration coefficient outside the canonical module
# is a duplicate flow law (however the base is spelled); pow(..., k2) likewise.
K2_EXPONENT = re.compile(r"\*\*\s*[\w.]*[kK]2\b|pow\s*\([^)]*[\w.]?[kK]2\b")


def test_canonical_flow_law_is_present():
    gate_flow = (SRC / "core" / "gate_flow.py").read_text(encoding="utf-8")
    for symbol in ("def discharge_coeff", "def gate_flow_m3s", "def required_opening_m"):
        assert symbol in gate_flow, f"canonical law missing {symbol}"


def test_no_k2_exponentiation_outside_the_canonical_module():
    # The strong single-law guard: any `... ** k2` (or pow(..., k2)) outside
    # core/gate_flow.py is a duplicate law regardless of how the base is spelled
    # (`opening ** k2`, `0.6 ** cal.k2`, `ratio ** K2` all count).
    offenders = {}
    for path in sorted(SRC.rglob("*.py")):
        if path.relative_to(SRC) == CANONICAL:
            continue
        match = K2_EXPONENT.search(path.read_text(encoding="utf-8", errors="replace"))
        if match:
            offenders[str(path.relative_to(SRC))] = match.group(0)
    assert not offenders, f"flow-law exponentiation outside core/gate_flow.py: {offenders}"


def test_canonical_module_still_carries_the_law():
    assert K2_EXPONENT.search((SRC / CANONICAL).read_text(encoding="utf-8"))


def test_deleted_duplicate_impls_stay_deleted():
    for name in (
        "integrated_gate_control.py",
        "gate_opening_calculator.py",
        "dynamic_flow_reducer.py",
        "water_gate_controller_local.py",
        "water_gate_controller_v2.py",
        "calibrated_gate_flow.py",
        "core/calibrated_flow_model.py",
        "core/calibrated_flow_model_v2.py",
        "core/calibrated_gate_hydraulics.py",
        "core/enhanced_hydraulic_solver.py",
        "api/v1/gate_control.py",
        "utils/load_calibrations.py",
        "enhanced_flow_monitoring_integration.py",
        "test_enhanced_flow_calculations.py",
        "test_zone6_irrigation_with_calibrations.py",
        "corrected_zone6_analysis_continuous_flow.py",
        "detailed_zone6_analysis_with_k1k2.py",
        "zone6_detailed_timing_analysis.py",
    ):
        assert not (SRC / name).exists(), f"{name} was re-added; it duplicates core/gate_flow"


def test_guard_regex_catches_every_known_spelling():
    assert K2_EXPONENT.search("Cs = k1 * (opening_m ** calibration.k2)")
    assert K2_EXPONENT.search("cs = calibration.k1 * (gate_opening ** calibration.K2)")
    assert K2_EXPONENT.search("actual_cs = cal.k1 * (0.6 ** cal.k2)")
    assert K2_EXPONENT.search("cs = k1 * pow(ratio, calibration.k2)")
    assert K2_EXPONENT.search("cs = k1 * (Hs / Go) ** k2")  # only legal in gate_flow.py
    assert not K2_EXPONENT.search("k2 = coefficients[1]  # assignment, not a law")

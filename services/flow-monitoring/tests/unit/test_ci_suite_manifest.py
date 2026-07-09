"""
CI suite-list drift guard (Wave 0.1, PROGRAM_REVIEW_2026-07-09).

The CI workflow runs an EXPLICIT list of isolated suites (bare `pytest` is unusable
until the Wave-1.9 dead-code purge). The risk of an explicit list is silent drift: a
new test file that nobody adds to the workflow gets a green gate without ever running.
This guard makes every `tests/unit/test_*.py` accountable — it must appear either in
the workflow's pytest invocation or in QUARANTINED below, and never in both.
"""
import re
from pathlib import Path

UNIT_DIR = Path(__file__).resolve().parent
WORKFLOW = UNIT_DIR.parents[3] / ".github" / "workflows" / "flow-monitoring-tests.yml"

# Legacy suites that predate the remediation: broken and/or coupled to the shared
# conftest's DB stack (23F/34E at the 2026-07-09 review). Quarantined pending the
# Wave-1.9 purge — do NOT add new files here without a roadmap-recorded reason.
QUARANTINED = {
    "test_api_endpoints.py",
    "test_calibrated_gate_hydraulics.py",
    "test_enhanced_hydraulic_solver.py",
    "test_gate_registry.py",
    "test_gradual_transition_controller.py",
}


def _workflow_suites() -> set:
    text = WORKFLOW.read_text(encoding="utf-8")
    return set(re.findall(r"tests/unit/(test_\w+\.py)", text))


def test_every_unit_test_file_is_in_ci_or_quarantined():
    on_disk = {p.name for p in UNIT_DIR.glob("test_*.py")}
    unaccounted = on_disk - _workflow_suites() - QUARANTINED
    assert not unaccounted, (
        f"unit test files not run by CI (add to {WORKFLOW.name}'s pytest list "
        f"or, with a recorded reason, to QUARANTINED): {sorted(unaccounted)}"
    )


def test_quarantine_and_ci_list_do_not_overlap():
    overlap = _workflow_suites() & QUARANTINED
    assert not overlap, f"suites both quarantined and CI-run: {sorted(overlap)}"


def test_workflow_lists_this_guard_itself():
    assert "test_ci_suite_manifest.py" in _workflow_suites()

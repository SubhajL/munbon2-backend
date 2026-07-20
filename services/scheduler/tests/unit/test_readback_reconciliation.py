"""PR 6.3b — the pure readback-reconciliation predicate (drift vs baseline, not target)."""

import pytest

from core.readback_reconciliation import (
    VERDICT_MISMATCH,
    VERDICT_OK,
    VERDICT_UNAVAILABLE,
    reconcile_gate_readback,
)


class TestReconcileGateReadback:
    def test_ok_when_observed_equals_expected_baseline(self):
        assert reconcile_gate_readback(2, 2, "ok") == VERDICT_OK

    def test_mismatch_when_fresh_levels_differ(self):
        assert reconcile_gate_readback(4, 2, "ok") == VERDICT_MISMATCH

    @pytest.mark.parametrize("quality", ["stale", "offline", "decode_error"])
    def test_unavailable_when_quality_is_not_ok(self, quality):
        # A non-fresh reading is never reconciled to a hold — acting on it would spuriously pause.
        assert reconcile_gate_readback(4, 2, quality) == VERDICT_UNAVAILABLE

    def test_unavailable_when_level_is_missing(self):
        assert reconcile_gate_readback(None, 2, "ok") == VERDICT_UNAVAILABLE

    def test_a_matching_stale_reading_is_still_unavailable_not_ok(self):
        # Even if the stale value happens to match, we cannot confirm it — unavailable wins.
        assert reconcile_gate_readback(2, 2, "stale") == VERDICT_UNAVAILABLE

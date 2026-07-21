import pytest

from core.operator_confirmation import (
    OperatorConfirmationError,
    expected_confirmation,
    require_exact_confirmation,
)


class TestExpectedConfirmation:
    def test_plan_action_binds_exact_plan_and_version(self):
        assert expected_confirmation("hold", "plan-123", 7) == "HOLD plan-123 v7"

    def test_grant_action_binds_exact_grant_id(self):
        assert expected_confirmation("revoke", "grant-456") == "REVOKE grant-456"

    def test_unknown_action_is_rejected(self):
        with pytest.raises(OperatorConfirmationError):
            expected_confirmation("execute", "plan-123", 7)


class TestRequireExactConfirmation:
    @pytest.mark.parametrize(
        "presented",
        [None, "", "hold plan-123 v7", "HOLD plan-123 v8", " HOLD plan-123 v7"],
    )
    def test_missing_or_inexact_confirmation_fails_closed(self, presented):
        with pytest.raises(OperatorConfirmationError):
            require_exact_confirmation(presented, "hold", "plan-123", 7)

    def test_exact_confirmation_passes(self):
        assert (
            require_exact_confirmation("HOLD plan-123 v7", "hold", "plan-123", 7)
            is None
        )

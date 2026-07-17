"""Mock-free unit coverage of the pure failure-strategy decision (PR 4.2).

Replaces the generation-drifted test_real_time_adapter.py, whose mocks
targeted methods and module symbols that do not exist."""

import pytest

from services.real_time_adapter import (  # the adapter's OWN enum —
    AdaptationStrategy,  # a schemas.adaptation twin exists; identity matters
    RealTimeAdapter,
)


def _strategy(repair_hours, shortage_m3, alternatives):
    adapter = RealTimeAdapter.__new__(RealTimeAdapter)  # pure method, no I/O
    return adapter._determine_failure_strategy(
        {"water_shortage_m3": shortage_m3}, alternatives, repair_hours
    )


@pytest.mark.parametrize(
    "repair_hours, shortage_m3, alternatives, expected",
    [
        (2.0, 500.0, [], AdaptationStrategy.DELAY_OPERATIONS),
        (4.0, 999.0, [], AdaptationStrategy.DELAY_OPERATIONS),
        (
            10.0,
            500.0,
            [{"additional_loss_percent": 10.0}],
            AdaptationStrategy.REROUTE_FLOW,
        ),
        (
            2.0,
            2000.0,
            [{"additional_loss_percent": 19.9}],
            AdaptationStrategy.REROUTE_FLOW,
        ),
        (
            10.0,
            500.0,
            [
                {"additional_loss_percent": 10.0},
                {"additional_loss_percent": 30.0},
            ],
            AdaptationStrategy.PARTIAL_DELIVERY,
        ),
        (10.0, 5001.0, [], AdaptationStrategy.EMERGENCY_OVERRIDE),
        (10.0, 3000.0, [], AdaptationStrategy.DELAY_OPERATIONS),
    ],
)
def test_determine_failure_strategy_branch_matrix(
    repair_hours, shortage_m3, alternatives, expected
):
    assert _strategy(repair_hours, shortage_m3, alternatives) is expected

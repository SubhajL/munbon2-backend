from functools import partial

import pytest
from pydantic import ValidationError

from algorithms.hydraulic_schedule_optimizer import (
    optimize_limited_adjustment_plan,
)
from core.config import Settings


def test_control_optimizer_settings_default_to_five_minutes_and_one_trim() -> None:
    settings = Settings()

    assert (
        settings.control_model_step_seconds,
        settings.control_max_intermediate_trims,
    ) == (300, 1)


def test_control_optimizer_settings_reject_more_than_two_trims() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 2"):
        Settings(control_max_intermediate_trims=3)


def test_scheduler_registers_the_bound_limited_adjustment_optimizer() -> None:
    from main import app

    optimizer = app.state.optimize_limited_adjustment_plan

    assert isinstance(optimizer, partial)
    assert optimizer.func is optimize_limited_adjustment_plan
    assert optimizer.keywords == {
        "model_step_seconds": 300,
        "max_intermediate_trims": 1,
        "solver_timeout_seconds": 60,
    }

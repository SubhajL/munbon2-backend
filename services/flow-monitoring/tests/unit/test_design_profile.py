import math

import pytest

from core.design_profile import (
    DesignProfileError,
    TrapezoidSection,
    forecast_design_level_msl,
    infer_effective_bed_msl,
    manning_flow_m3s,
    normal_depth_m,
    trapezoid_area_m2,
)

SECTION = TrapezoidSection(
    bottom_width_m=3.5,
    side_slope=1.5,
    manning_n=0.018,
    bed_slope=0.0002,
    max_depth_m=1.85,
)


class TestTrapezoidAreaM2:
    def test_returns_independent_geometric_area(self):
        depth_m = 1.2
        expected_m2 = 3.5 * depth_m + 1.5 * depth_m**2
        assert trapezoid_area_m2(depth_m, SECTION) == pytest.approx(expected_m2)


class TestNormalDepthM:
    def test_zero_flow_returns_dry_depth(self):
        assert normal_depth_m(0.0, SECTION) == 0.0

    def test_round_trips_manning_flow(self):
        expected_depth_m = 1.1
        flow_m3s = manning_flow_m3s(expected_depth_m, SECTION)
        assert normal_depth_m(flow_m3s, SECTION) == pytest.approx(
            expected_depth_m, abs=1e-8
        )

    def test_depth_increases_strictly_with_flow(self):
        capacity_m3s = manning_flow_m3s(SECTION.max_depth_m, SECTION)
        depths = [
            normal_depth_m(capacity_m3s * fraction, SECTION)
            for fraction in (0.1, 0.4, 0.8)
        ]
        assert depths[0] < depths[1] < depths[2] < SECTION.max_depth_m

    def test_flow_above_surveyed_design_depth_fails_closed(self):
        capacity_m3s = manning_flow_m3s(SECTION.max_depth_m, SECTION)
        with pytest.raises(DesignProfileError, match="design depth"):
            normal_depth_m(math.nextafter(capacity_m3s, math.inf), SECTION)

    @pytest.mark.parametrize(
        "section",
        [
            TrapezoidSection(0.0, 1.5, 0.018, 0.0002, 1.85),
            TrapezoidSection(3.5, -0.1, 0.018, 0.0002, 1.85),
            TrapezoidSection(3.5, 1.5, 0.0, 0.0002, 1.85),
            TrapezoidSection(3.5, 1.5, 0.018, 0.0, 1.85),
            TrapezoidSection(3.5, 1.5, 0.018, 0.0002, math.inf),
        ],
    )
    def test_invalid_physical_section_fails_closed(self, section):
        with pytest.raises(DesignProfileError):
            normal_depth_m(1.0, section)


class TestEffectiveDesignDatum:
    def test_design_flow_reproduces_fsl_exactly(self):
        design_fsl_msl_m = 205.561
        design_flow_m3s = 1.2
        effective_bed_msl_m = infer_effective_bed_msl(
            design_fsl_msl_m,
            design_flow_m3s,
            SECTION,
        )
        forecast_msl_m, depth_m = forecast_design_level_msl(
            design_flow_m3s,
            effective_bed_msl_m,
            SECTION,
        )
        assert (forecast_msl_m, depth_m) == pytest.approx(
            (design_fsl_msl_m, design_fsl_msl_m - effective_bed_msl_m),
            abs=1e-9,
        )

    def test_zero_flow_returns_dry_effective_bed(self):
        effective_bed_msl_m = infer_effective_bed_msl(205.561, 1.2, SECTION)
        assert forecast_design_level_msl(0.0, effective_bed_msl_m, SECTION) == (
            effective_bed_msl_m,
            0.0,
        )

    @pytest.mark.parametrize("value", [True, math.nan, math.inf])
    def test_non_finite_or_boolean_fsl_fails_closed(self, value):
        with pytest.raises(DesignProfileError, match="design_fsl_msl_m"):
            infer_effective_bed_msl(value, 1.2, SECTION)

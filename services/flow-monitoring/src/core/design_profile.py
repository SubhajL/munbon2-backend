"""Pure static hydraulic design-profile calculations."""

import math
from dataclasses import dataclass


class DesignProfileError(ValueError):
    """A design profile cannot be calculated from the supplied physical inputs."""


@dataclass(frozen=True)
class TrapezoidSection:
    bottom_width_m: float
    side_slope: float
    manning_n: float
    bed_slope: float
    max_depth_m: float


def trapezoid_area_m2(depth_m: float, section: TrapezoidSection) -> float:
    _validate_section(section)
    _validate_non_negative(depth_m, "depth_m")
    return depth_m * (section.bottom_width_m + section.side_slope * depth_m)


def manning_flow_m3s(depth_m: float, section: TrapezoidSection) -> float:
    area_m2 = trapezoid_area_m2(depth_m, section)
    if area_m2 == 0.0:
        return 0.0
    wetted_perimeter_m = section.bottom_width_m + 2.0 * depth_m * math.sqrt(
        1.0 + section.side_slope**2
    )
    hydraulic_radius_m = area_m2 / wetted_perimeter_m
    return (
        area_m2
        * hydraulic_radius_m ** (2.0 / 3.0)
        * math.sqrt(section.bed_slope)
        / section.manning_n
    )


def normal_depth_m(flow_m3s: float, section: TrapezoidSection) -> float:
    _validate_section(section)
    _validate_non_negative(flow_m3s, "flow_m3s")
    if flow_m3s == 0.0:
        return 0.0
    capacity_m3s = manning_flow_m3s(section.max_depth_m, section)
    if flow_m3s > capacity_m3s:
        raise DesignProfileError(
            f"flow_m3s {flow_m3s} exceeds Manning flow {capacity_m3s} at design depth"
        )
    low_m = 0.0
    high_m = section.max_depth_m
    for _ in range(80):
        depth_m = (low_m + high_m) / 2.0
        if manning_flow_m3s(depth_m, section) < flow_m3s:
            low_m = depth_m
        else:
            high_m = depth_m
    return (low_m + high_m) / 2.0


def infer_effective_bed_msl(
    design_fsl_msl_m: float,
    design_flow_m3s: float,
    section: TrapezoidSection,
) -> float:
    _validate_finite(design_fsl_msl_m, "design_fsl_msl_m")
    _validate_positive(design_flow_m3s, "design_flow_m3s")
    return design_fsl_msl_m - normal_depth_m(design_flow_m3s, section)


def forecast_design_level_msl(
    flow_m3s: float,
    effective_bed_msl_m: float,
    section: TrapezoidSection,
) -> tuple[float, float]:
    _validate_finite(effective_bed_msl_m, "effective_bed_msl_m")
    depth_m = normal_depth_m(flow_m3s, section)
    return effective_bed_msl_m + depth_m, depth_m


def _validate_section(section: TrapezoidSection) -> None:
    _validate_positive(section.bottom_width_m, "bottom_width_m")
    _validate_non_negative(section.side_slope, "side_slope")
    _validate_positive(section.manning_n, "manning_n")
    _validate_positive(section.bed_slope, "bed_slope")
    _validate_positive(section.max_depth_m, "max_depth_m")


def _validate_finite(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise DesignProfileError(f"{name} must be a finite number")


def _validate_non_negative(value: float, name: str) -> None:
    _validate_finite(value, name)
    if value < 0.0:
        raise DesignProfileError(f"{name} must be >= 0")


def _validate_positive(value: float, name: str) -> None:
    _validate_finite(value, name)
    if value <= 0.0:
        raise DesignProfileError(f"{name} must be > 0")

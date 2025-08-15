"""
Unit tests for Calibrated Gate Hydraulics
Tests the core gate flow equations and calibration functionality
"""

import pytest
import numpy as np
from unittest.mock import Mock

from core.calibrated_gate_hydraulics import (
    CalibratedGateHydraulics, GateProperties, GateCalibration,
    HydraulicConditions, FlowCalculationResult, GateType
)


class TestCalibratedGateHydraulics:
    """Test suite for calibrated gate hydraulics calculations"""
    
    def test_gate_properties_initialization(self):
        """Test GateProperties dataclass initialization"""
        props = GateProperties(
            gate_id="TEST_GATE",
            gate_type=GateType.RADIAL,
            width_m=5.0,
            height_m=4.0,
            sill_elevation_m=95.0,
            discharge_coefficient=0.65
        )
        
        assert props.gate_id == "TEST_GATE"
        assert props.gate_type == GateType.RADIAL
        assert props.width_m == 5.0
        assert props.height_m == 4.0
        assert props.discharge_coefficient == 0.65
    
    def test_calibration_coefficient_calculation(self, calibrated_hydraulics):
        """Test calibration coefficient Cs calculation"""
        # Test with calibrated gate
        conditions = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=2.0,
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        # Verify Cs calculation: Cs = K1 * (Hs/Go)^K2
        gate_props = calibrated_hydraulics.gate_properties["G_RES_J1"]
        Hs = conditions.upstream_level_m - gate_props.sill_elevation_m
        Go = conditions.gate_opening_m
        K1 = calibrated_hydraulics.calibrations["G_RES_J1"].K1
        K2 = calibrated_hydraulics.calibrations["G_RES_J1"].K2
        
        expected_Cs = K1 * (Hs / Go) ** K2
        assert abs(result.calibration_coefficient - expected_Cs) < 0.001
    
    def test_flow_calculation_with_calibration(self, calibrated_hydraulics):
        """Test flow calculation with calibrated gate equation"""
        conditions = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=2.0,
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        # Verify flow calculation: Q = Cs × L × Hs × √(2g × ΔH)
        assert result.flow_m3s > 0
        assert result.discharge_coefficient > 0
        assert result.calibration_coefficient > 0
        assert result.is_calibrated is True
        assert result.flow_regime == "free"  # Large head difference
    
    def test_flow_calculation_without_calibration(self, calibrated_hydraulics):
        """Test flow calculation falls back to standard equation without calibration"""
        conditions = HydraulicConditions(
            upstream_level_m=98.0,
            downstream_level_m=93.0,
            gate_opening_m=1.5,
            temperature_c=25.0
        )
        
        # G_J1_Z1 has no calibration data
        result = calibrated_hydraulics.calculate_flow("G_J1_Z1", conditions)
        
        assert result.flow_m3s > 0
        assert result.is_calibrated is False
        assert result.calibration_coefficient == 1.0  # No calibration applied
        assert "No calibration data" in result.warnings[0]
    
    def test_submerged_flow_detection(self, calibrated_hydraulics):
        """Test detection of submerged flow conditions"""
        # Create submerged conditions (small head difference)
        conditions = HydraulicConditions(
            upstream_level_m=100.5,
            downstream_level_m=100.0,  # Very close to upstream
            gate_opening_m=2.0,
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        assert result.flow_regime == "submerged"
        assert result.submergence_ratio > 0.67  # Typical threshold
        assert any("submerged" in w.lower() for w in result.warnings)
    
    def test_closed_gate_flow(self, calibrated_hydraulics):
        """Test flow calculation for closed gate"""
        conditions = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=0.0,  # Closed
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        assert result.flow_m3s == 0.0
        assert "Gate is closed" in result.warnings
    
    def test_negative_head_warning(self, calibrated_hydraulics):
        """Test handling of negative head (backflow) conditions"""
        conditions = HydraulicConditions(
            upstream_level_m=95.0,
            downstream_level_m=100.0,  # Higher than upstream
            gate_opening_m=1.0,
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        assert result.flow_m3s < 0  # Negative flow (backflow)
        assert any("backflow" in w.lower() for w in result.warnings)
    
    def test_extrapolation_warning(self, calibrated_hydraulics):
        """Test warning when extrapolating beyond calibration range"""
        conditions = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=4.0,  # Beyond max_tested_opening_m of 3.5
            temperature_c=25.0
        )
        
        result = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions)
        
        assert result.flow_m3s > 0
        assert any("extrapolating" in w.lower() for w in result.warnings)
    
    def test_gate_not_found(self, calibrated_hydraulics):
        """Test handling of unknown gate ID"""
        conditions = HydraulicConditions(
            upstream_level_m=100.0,
            downstream_level_m=95.0,
            gate_opening_m=1.0,
            temperature_c=25.0
        )
        
        with pytest.raises(ValueError, match="Gate UNKNOWN_GATE not found"):
            calibrated_hydraulics.calculate_flow("UNKNOWN_GATE", conditions)
    
    def test_batch_flow_calculation(self, calibrated_hydraulics):
        """Test batch calculation for multiple gates"""
        conditions_dict = {
            "G_RES_J1": HydraulicConditions(
                upstream_level_m=105.0,
                downstream_level_m=98.0,
                gate_opening_m=2.0,
                temperature_c=25.0
            ),
            "G_J1_Z1": HydraulicConditions(
                upstream_level_m=98.0,
                downstream_level_m=93.0,
                gate_opening_m=1.5,
                temperature_c=25.0
            )
        }
        
        results = calibrated_hydraulics.calculate_batch_flows(conditions_dict)
        
        assert len(results) == 2
        assert "G_RES_J1" in results
        assert "G_J1_Z1" in results
        assert results["G_RES_J1"].is_calibrated is True
        assert results["G_J1_Z1"].is_calibrated is False
    
    def test_temperature_effects(self, calibrated_hydraulics):
        """Test temperature effect on viscosity (if implemented)"""
        # Test at different temperatures
        conditions_cold = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=2.0,
            temperature_c=5.0  # Cold water
        )
        
        conditions_hot = HydraulicConditions(
            upstream_level_m=105.0,
            downstream_level_m=98.0,
            gate_opening_m=2.0,
            temperature_c=35.0  # Warm water
        )
        
        result_cold = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions_cold)
        result_hot = calibrated_hydraulics.calculate_flow("G_RES_J1", conditions_hot)
        
        # Flow should be slightly different due to viscosity changes
        # For now, just verify both calculate successfully
        assert result_cold.flow_m3s > 0
        assert result_hot.flow_m3s > 0
    
    def test_gate_type_specific_calculations(self):
        """Test different gate types have appropriate calculations"""
        # Radial gate
        radial_props = GateProperties(
            gate_id="RADIAL",
            gate_type=GateType.RADIAL,
            width_m=5.0,
            height_m=4.0,
            sill_elevation_m=95.0,
            discharge_coefficient=0.65
        )
        
        # Slide gate
        slide_props = GateProperties(
            gate_id="SLIDE",
            gate_type=GateType.SLIDE,
            width_m=5.0,
            height_m=4.0,
            sill_elevation_m=95.0,
            discharge_coefficient=0.60
        )
        
        hydraulics = CalibratedGateHydraulics(
            {"RADIAL": radial_props, "SLIDE": slide_props},
            {}
        )
        
        conditions = HydraulicConditions(
            upstream_level_m=100.0,
            downstream_level_m=96.0,
            gate_opening_m=1.0,
            temperature_c=25.0
        )
        
        radial_result = hydraulics.calculate_flow("RADIAL", conditions)
        slide_result = hydraulics.calculate_flow("SLIDE", conditions)
        
        # Different discharge coefficients should give different flows
        assert radial_result.flow_m3s != slide_result.flow_m3s
        assert radial_result.discharge_coefficient == 0.65
        assert slide_result.discharge_coefficient == 0.60
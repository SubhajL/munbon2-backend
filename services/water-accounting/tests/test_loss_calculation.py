"""Tests for loss calculation service"""

import pytest
from src.services import LossCalculationService

class TestLossCalculation:
    """Test water loss calculations"""
    
    @pytest.fixture
    def service(self):
        return LossCalculationService()
    
    @pytest.fixture
    def flow_data(self):
        return {
            "flow_rate_m3s": 0.5,
            "transit_time_hours": 2.0,
            "volume_m3": 3600
        }
    
    @pytest.fixture
    def canal_characteristics(self):
        return {
            "type": "lined",
            "length_km": 5.0,
            "width_m": 3.0,
            "water_depth_m": 1.0,
            "soil_type": "clay"
        }
    
    @pytest.fixture
    def environmental_conditions(self):
        return {
            "temperature_c": 30,
            "humidity_percent": 60,
            "wind_speed_ms": 2,
            "solar_radiation_wm2": 250
        }
    
    @pytest.mark.asyncio
    async def test_calculate_transit_losses(self, service, flow_data, canal_characteristics, environmental_conditions):
        """Test complete transit loss calculation"""
        result = await service.calculate_transit_losses(
            flow_data,
            canal_characteristics,
            environmental_conditions
        )
        
        assert "total_loss_m3" in result
        assert "breakdown" in result
        assert "loss_percentage" in result
        assert result["total_loss_m3"] > 0
        assert result["loss_percentage"] > 0
        assert result["loss_percentage"] < 100
    
    @pytest.mark.asyncio
    async def test_seepage_loss_lined_canal(self, service, flow_data, canal_characteristics):
        """Test seepage loss for lined canal"""
        result = await service.calculate_seepage_loss(
            flow_data,
            canal_characteristics
        )
        
        assert result["seepage_loss_m3"] > 0
        assert result["seepage_rate_percent"] > 0
        # Lined canals should have lower seepage
        assert result["seepage_rate_percent"] < 5
    
    @pytest.mark.asyncio
    async def test_seepage_loss_earthen_canal(self, service, flow_data):
        """Test seepage loss for earthen canal"""
        earthen_canal = {
            "type": "earthen",
            "length_km": 5.0,
            "soil_type": "sandy"
        }
        
        result = await service.calculate_seepage_loss(
            flow_data,
            earthen_canal
        )
        
        assert result["seepage_loss_m3"] > 0
        # Earthen canals should have higher seepage
        assert result["seepage_rate_percent"] > 5
    
    @pytest.mark.asyncio
    async def test_evaporation_loss(self, service, flow_data, canal_characteristics, environmental_conditions):
        """Test evaporation loss calculation"""
        result = await service.calculate_evaporation_loss(
            flow_data,
            canal_characteristics,
            environmental_conditions
        )
        
        assert result["evaporation_loss_m3"] > 0
        assert result["evaporation_rate_mm_hr"] > 0
        assert "calculation_method" in result
    
    @pytest.mark.asyncio
    async def test_evaporation_loss_high_temp(self, service, flow_data, canal_characteristics):
        """Test evaporation with high temperature"""
        hot_conditions = {
            "temperature_c": 45,
            "humidity_percent": 20,
            "wind_speed_ms": 5,
            "solar_radiation_wm2": 800
        }
        
        result = await service.calculate_evaporation_loss(
            flow_data,
            canal_characteristics,
            hot_conditions
        )
        
        # Higher temperature should increase evaporation
        assert result["evaporation_rate_mm_hr"] > 1.0
    
    @pytest.mark.asyncio
    async def test_operational_losses(self, service, flow_data):
        """Test operational loss calculation"""
        gate_data = {
            "leakage_rate_m3_hr": 5,
            "spillage_events": 2,
            "avg_spillage_m3": 50
        }
        
        result = await service.calculate_operational_losses(
            flow_data,
            gate_data
        )
        
        assert result["total_operational_loss_m3"] > 0
        assert result["leakage_loss_m3"] == 10  # 5 m³/hr * 2 hours
        assert result["spillage_loss_m3"] == 100  # 2 events * 50 m³
    
    @pytest.mark.asyncio
    async def test_loss_uncertainty(self, service):
        """Test uncertainty estimation"""
        loss_result = {
            "total_loss_m3": 500,
            "breakdown": {
                "seepage": 300,
                "evaporation": 150,
                "operational": 50
            },
            "calculation_confidence": {
                "seepage": 0.8,
                "evaporation": 0.7,
                "operational": 0.9
            }
        }
        
        uncertainty = await service.estimate_loss_uncertainty(loss_result)
        
        assert "total_uncertainty_m3" in uncertainty
        assert "confidence_interval" in uncertainty
        assert uncertainty["confidence_level"] > 0
        assert uncertainty["confidence_level"] <= 1
    
    @pytest.mark.asyncio
    async def test_model_calibration(self, service):
        """Test model calibration with measured data"""
        measured_data = [
            {
                "date": "2024-01-01",
                "predicted_loss_m3": 500,
                "measured_loss_m3": 480
            },
            {
                "date": "2024-01-02", 
                "predicted_loss_m3": 600,
                "measured_loss_m3": 650
            }
        ]
        
        calibration = await service.calibrate_loss_model(measured_data)
        
        assert "calibration_factor" in calibration
        assert "rmse" in calibration
        assert "r_squared" in calibration
        assert calibration["calibration_factor"] > 0
    
    @pytest.mark.asyncio
    async def test_zero_flow(self, service, canal_characteristics, environmental_conditions):
        """Test with zero flow"""
        zero_flow = {
            "flow_rate_m3s": 0,
            "transit_time_hours": 2.0,
            "volume_m3": 0
        }
        
        result = await service.calculate_transit_losses(
            zero_flow,
            canal_characteristics,
            environmental_conditions
        )
        
        assert result["total_loss_m3"] == 0
        assert result["loss_percentage"] == 0
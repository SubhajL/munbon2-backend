"""Tests for volume integration service"""

import pytest
from datetime import datetime, timedelta

from src.services import VolumeIntegrationService

class TestVolumeIntegration:
    """Test volume integration calculations"""
    
    @pytest.fixture
    def service(self):
        return VolumeIntegrationService()
    
    @pytest.fixture
    def sample_flow_data(self):
        """Create sample flow data with regular intervals"""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        return [
            {
                "timestamp": (base_time + timedelta(minutes=i*15)).isoformat(),
                "flow_rate_m3s": 0.5 + (i * 0.1)  # Increasing flow
            }
            for i in range(5)  # 0, 15, 30, 45, 60 minutes
        ]
    
    @pytest.fixture
    def irregular_flow_data(self):
        """Create flow data with irregular intervals"""
        timestamps = [0, 10, 35, 50, 90]  # Minutes
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        return [
            {
                "timestamp": (base_time + timedelta(minutes=t)).isoformat(),
                "flow_rate_m3s": 0.8
            }
            for t in timestamps
        ]
    
    @pytest.mark.asyncio
    async def test_trapezoidal_integration(self, service, sample_flow_data):
        """Test trapezoidal integration method"""
        result = await service.integrate_flow_to_volume(
            sample_flow_data,
            method="trapezoidal"
        )
        
        assert result["total_volume_m3"] > 0
        assert result["method"] == "trapezoidal"
        assert "integration_details" in result
        assert result["integration_details"]["data_points"] == 5
        assert result["integration_details"]["duration_hours"] == 1.0
    
    @pytest.mark.asyncio
    async def test_simpson_integration(self, service, sample_flow_data):
        """Test Simpson's rule integration"""
        result = await service.integrate_flow_to_volume(
            sample_flow_data,
            method="simpson"
        )
        
        assert result["total_volume_m3"] > 0
        assert result["method"] == "simpson"
    
    @pytest.mark.asyncio
    async def test_rectangular_integration(self, service, sample_flow_data):
        """Test rectangular integration method"""
        result = await service.integrate_flow_to_volume(
            sample_flow_data,
            method="rectangular"
        )
        
        assert result["total_volume_m3"] > 0
        assert result["method"] == "rectangular"
    
    @pytest.mark.asyncio
    async def test_cumulative_volume(self, service, sample_flow_data):
        """Test cumulative volume calculation"""
        result = await service.calculate_cumulative_volume(
            sample_flow_data,
            interval_minutes=15
        )
        
        assert len(result["cumulative_volumes"]) > 0
        assert result["final_volume_m3"] > 0
        
        # Check that cumulative volumes are increasing
        volumes = [v["cumulative_m3"] for v in result["cumulative_volumes"]]
        assert all(volumes[i] <= volumes[i+1] for i in range(len(volumes)-1))
    
    @pytest.mark.asyncio
    async def test_validate_flow_data(self, service, sample_flow_data):
        """Test flow data validation"""
        result = await service.validate_flow_data(sample_flow_data)
        
        assert result["is_valid"] == True
        assert result["total_points"] == 5
        assert result["valid_points"] == 5
        assert len(result["issues"]) == 0
    
    @pytest.mark.asyncio
    async def test_validate_flow_data_with_gaps(self, service, irregular_flow_data):
        """Test validation with data gaps"""
        result = await service.validate_flow_data(irregular_flow_data)
        
        assert result["is_valid"] == True  # Still valid but with warnings
        assert "Large time gap" in str(result["issues"])
    
    @pytest.mark.asyncio
    async def test_validate_flow_data_with_outliers(self, service):
        """Test validation with outliers"""
        flow_data = [
            {"timestamp": f"2024-01-01T10:{i:02d}:00", "flow_rate_m3s": 0.5}
            for i in range(0, 50, 10)
        ]
        # Add outlier
        flow_data[2]["flow_rate_m3s"] = 50.0  # Extremely high
        
        result = await service.validate_flow_data(flow_data)
        
        assert result["is_valid"] == False
        assert any("outlier" in issue.lower() for issue in result["issues"])
    
    @pytest.mark.asyncio
    async def test_empty_flow_data(self, service):
        """Test with empty flow data"""
        result = await service.integrate_flow_to_volume([])
        
        assert result["total_volume_m3"] == 0
        assert result["error"] is not None
    
    @pytest.mark.asyncio
    async def test_single_data_point(self, service):
        """Test with single data point"""
        flow_data = [{
            "timestamp": "2024-01-01T10:00:00",
            "flow_rate_m3s": 1.0
        }]
        
        result = await service.integrate_flow_to_volume(flow_data)
        
        assert result["total_volume_m3"] == 0  # Can't integrate single point
        assert "Insufficient data" in result.get("error", "")
"""Tests for efficiency calculator service"""

import pytest
from src.services import EfficiencyCalculator

class TestEfficiencyCalculator:
    """Test efficiency calculations"""
    
    @pytest.fixture
    def service(self):
        return EfficiencyCalculator()
    
    @pytest.fixture
    def delivery_data(self):
        return {
            "gate_outflow_m3": 1000,
            "section_inflow_m3": 900,
            "transit_loss_m3": 100,
            "water_consumed_m3": 765  # 85% of section inflow
        }
    
    @pytest.fixture
    def multiple_deliveries(self):
        return [
            {
                "gate_outflow_m3": 1000,
                "section_inflow_m3": 900,
                "transit_loss_m3": 100,
                "water_consumed_m3": 765
            },
            {
                "gate_outflow_m3": 1500,
                "section_inflow_m3": 1350,
                "transit_loss_m3": 150,
                "water_consumed_m3": 1147.5
            },
            {
                "gate_outflow_m3": 800,
                "section_inflow_m3": 720,
                "transit_loss_m3": 80,
                "water_consumed_m3": 612
            }
        ]
    
    @pytest.mark.asyncio
    async def test_calculate_delivery_efficiency(self, service):
        """Test delivery efficiency calculation"""
        result = await service.calculate_delivery_efficiency(
            gate_outflow_m3=1000,
            section_inflow_m3=900,
            transit_loss_m3=100
        )
        
        assert result["delivery_efficiency"] == 0.9
        assert result["loss_ratio"] == 0.1
        assert result["efficiency_percentage"] == 90.0
    
    @pytest.mark.asyncio
    async def test_calculate_application_efficiency(self, service):
        """Test application efficiency calculation"""
        result = await service.calculate_application_efficiency(
            water_applied_m3=900,
            water_consumed_m3=765
        )
        
        assert result["application_efficiency"] == 0.85
        assert result["return_flow_m3"] == 135
        assert result["efficiency_percentage"] == 85.0
    
    @pytest.mark.asyncio
    async def test_calculate_overall_efficiency(self, service):
        """Test overall system efficiency"""
        result = await service.calculate_overall_efficiency(
            delivery_efficiency=0.9,
            application_efficiency=0.85
        )
        
        assert result["overall_efficiency"] == 0.765
        assert result["efficiency_percentage"] == 76.5
        assert result["performance_rating"] in ["Good", "Excellent", "Fair", "Poor"]
    
    @pytest.mark.asyncio
    async def test_calculate_section_efficiency_metrics(self, service, multiple_deliveries):
        """Test section-level efficiency metrics"""
        section = {"id": "SEC-001", "name": "Test Section"}
        period = ("2024-01-01", "2024-01-07")
        
        result = await service.calculate_section_efficiency_metrics(
            section,
            multiple_deliveries,
            period
        )
        
        assert "section_id" in result
        assert "avg_delivery_efficiency" in result
        assert "avg_application_efficiency" in result
        assert "overall_efficiency" in result
        assert "total_water_delivered_m3" in result
        assert result["total_water_delivered_m3"] == 3300  # Sum of gate outflows
    
    @pytest.mark.asyncio
    async def test_classify_efficiency_performance(self, service):
        """Test efficiency performance classification"""
        # Test excellent performance
        result = await service.classify_efficiency_performance(0.85)
        assert result["category"] == "Excellent"
        assert result["color_code"] == "green"
        
        # Test good performance
        result = await service.classify_efficiency_performance(0.75)
        assert result["category"] == "Good"
        
        # Test fair performance
        result = await service.classify_efficiency_performance(0.65)
        assert result["category"] == "Fair"
        
        # Test poor performance
        result = await service.classify_efficiency_performance(0.55)
        assert result["category"] == "Poor"
        
        # Test very poor performance
        result = await service.classify_efficiency_performance(0.45)
        assert result["category"] == "Very Poor"
    
    @pytest.mark.asyncio
    async def test_generate_efficiency_report(self, service):
        """Test efficiency report generation"""
        sections_metrics = [
            {
                "section_id": "SEC-001",
                "section_name": "Section 1",
                "avg_delivery_efficiency": 0.90,
                "avg_application_efficiency": 0.85,
                "overall_efficiency": 0.765,
                "total_water_delivered_m3": 5000,
                "total_water_consumed_m3": 3825,
                "total_losses_m3": 1175
            },
            {
                "section_id": "SEC-002",
                "section_name": "Section 2",
                "avg_delivery_efficiency": 0.85,
                "avg_application_efficiency": 0.80,
                "overall_efficiency": 0.68,
                "total_water_delivered_m3": 4000,
                "total_water_consumed_m3": 2720,
                "total_losses_m3": 1280
            },
            {
                "section_id": "SEC-003",
                "section_name": "Section 3",
                "avg_delivery_efficiency": 0.70,
                "avg_application_efficiency": 0.75,
                "overall_efficiency": 0.525,
                "total_water_delivered_m3": 3000,
                "total_water_consumed_m3": 1575,
                "total_losses_m3": 1425
            }
        ]
        
        period = ("2024-01-01", "2024-01-07")
        zone_id = "ZONE-A"
        
        report = await service.generate_efficiency_report(
            sections_metrics,
            period,
            zone_id
        )
        
        assert "report_id" in report
        assert report["total_sections"] == 3
        assert "summary_statistics" in report
        assert "performance_distribution" in report
        assert "best_performers" in report
        assert "worst_performers" in report
        assert "recommendations" in report
        
        # Check summary statistics
        summary = report["summary_statistics"]
        assert summary["total_water_delivered_m3"] == 12000
        assert summary["total_water_consumed_m3"] == 8120
        assert summary["total_losses_m3"] == 3880
    
    @pytest.mark.asyncio
    async def test_zero_flow_efficiency(self, service):
        """Test efficiency with zero flow"""
        result = await service.calculate_delivery_efficiency(
            gate_outflow_m3=0,
            section_inflow_m3=0,
            transit_loss_m3=0
        )
        
        assert result["delivery_efficiency"] == 0
        assert result["efficiency_percentage"] == 0
        assert result["error"] is None
    
    @pytest.mark.asyncio
    async def test_perfect_efficiency(self, service):
        """Test perfect efficiency scenario"""
        result = await service.calculate_delivery_efficiency(
            gate_outflow_m3=1000,
            section_inflow_m3=1000,
            transit_loss_m3=0
        )
        
        assert result["delivery_efficiency"] == 1.0
        assert result["efficiency_percentage"] == 100.0
        assert result["loss_ratio"] == 0.0
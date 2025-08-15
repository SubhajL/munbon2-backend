"""Tests for deficit tracking service"""

import pytest
from datetime import datetime, timedelta
from src.services import DeficitTracker

class TestDeficitTracker:
    """Test deficit tracking and carry-forward"""
    
    @pytest.fixture
    def service(self):
        return DeficitTracker(carry_forward_weeks=4)
    
    @pytest.fixture
    def current_deficit(self):
        return {
            "section_id": "SEC-001",
            "week_number": 45,
            "year": 2024,
            "water_demand_m3": 5000,
            "water_delivered_m3": 4000,
            "water_consumed_m3": 3400,
            "delivery_deficit_m3": 1000,
            "deficit_percentage": 20.0,
            "stress_level": "moderate"
        }
    
    @pytest.fixture
    def previous_deficits(self):
        return [
            {
                "section_id": "SEC-001",
                "week_number": 42,
                "year": 2024,
                "water_demand_m3": 5000,
                "water_delivered_m3": 4500,
                "delivery_deficit_m3": 500,
                "deficit_percentage": 10.0,
                "stress_level": "mild"
            },
            {
                "section_id": "SEC-001",
                "week_number": 43,
                "year": 2024,
                "water_demand_m3": 5000,
                "water_delivered_m3": 4200,
                "delivery_deficit_m3": 800,
                "deficit_percentage": 16.0,
                "stress_level": "moderate"
            },
            {
                "section_id": "SEC-001",
                "week_number": 44,
                "year": 2024,
                "water_demand_m3": 5000,
                "water_delivered_m3": 5000,
                "delivery_deficit_m3": 0,
                "deficit_percentage": 0.0,
                "stress_level": "none"
            }
        ]
    
    @pytest.mark.asyncio
    async def test_calculate_delivery_deficit(self, service):
        """Test deficit calculation"""
        result = await service.calculate_delivery_deficit(
            section_id="SEC-001",
            water_demand_m3=5000,
            water_delivered_m3=4000,
            water_consumed_m3=3400,
            week_number=45,
            year=2024
        )
        
        assert result["delivery_deficit_m3"] == 1000
        assert result["deficit_percentage"] == 20.0
        assert result["stress_level"] == "moderate"
        assert "estimated_yield_impact" in result
    
    @pytest.mark.asyncio
    async def test_stress_level_classification(self, service):
        """Test stress level determination"""
        # No stress
        result = await service.calculate_delivery_deficit(
            "SEC-001", 1000, 1000, 850, 1, 2024
        )
        assert result["stress_level"] == "none"
        
        # Mild stress
        result = await service.calculate_delivery_deficit(
            "SEC-001", 1000, 950, 800, 1, 2024
        )
        assert result["stress_level"] == "mild"
        
        # Moderate stress
        result = await service.calculate_delivery_deficit(
            "SEC-001", 1000, 850, 700, 1, 2024
        )
        assert result["stress_level"] == "moderate"
        
        # Severe stress
        result = await service.calculate_delivery_deficit(
            "SEC-001", 1000, 650, 550, 1, 2024
        )
        assert result["stress_level"] == "severe"
    
    @pytest.mark.asyncio
    async def test_update_carry_forward(self, service, current_deficit, previous_deficits):
        """Test carry-forward update"""
        result = await service.update_carry_forward(
            "SEC-001",
            current_deficit,
            previous_deficits
        )
        
        assert result["active"] == True
        assert result["total_deficit_m3"] == 2300  # 500 + 800 + 1000
        assert result["weeks_in_deficit"] == 3
        assert "deficit_breakdown" in result
        assert len(result["deficit_breakdown"]) == 3
    
    @pytest.mark.asyncio
    async def test_carry_forward_window(self, service):
        """Test carry-forward window limit"""
        old_deficits = [
            {
                "section_id": "SEC-001",
                "week_number": 35,  # 10 weeks old
                "year": 2024,
                "delivery_deficit_m3": 1000,
                "deficit_percentage": 20.0
            }
        ]
        
        current = {
            "section_id": "SEC-001",
            "week_number": 45,
            "year": 2024,
            "delivery_deficit_m3": 500,
            "deficit_percentage": 10.0
        }
        
        result = await service.update_carry_forward(
            "SEC-001",
            current,
            old_deficits
        )
        
        # Old deficit should not be included
        assert result["total_deficit_m3"] == 500
        assert result["weeks_in_deficit"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_recovery_plan(self, service):
        """Test recovery plan generation"""
        carry_forward_data = {
            "section_id": "SEC-001",
            "total_deficit_m3": 2000,
            "weeks_in_deficit": 3
        }
        
        plan = await service.generate_recovery_plan(
            carry_forward_data,
            available_capacity_m3=600,
            upcoming_weeks=4
        )
        
        assert plan["recovery_needed"] == True
        assert plan["total_deficit_m3"] == 2000
        assert "recovery_plan" in plan
        assert plan["recovery_plan"]["weekly_compensation_m3"] == 500
        assert plan["recovery_plan"]["recovery_weeks"] == 4
        assert plan["recovery_plan"]["full_recovery_possible"] == True
    
    @pytest.mark.asyncio
    async def test_recovery_plan_insufficient_capacity(self, service):
        """Test recovery plan with limited capacity"""
        carry_forward_data = {
            "section_id": "SEC-001",
            "total_deficit_m3": 4000,
            "weeks_in_deficit": 3
        }
        
        plan = await service.generate_recovery_plan(
            carry_forward_data,
            available_capacity_m3=200,  # Very limited capacity
            upcoming_weeks=4
        )
        
        assert plan["recovery_plan"]["full_recovery_possible"] == False
        assert plan["recovery_plan"]["remaining_deficit_m3"] > 0
    
    @pytest.mark.asyncio
    async def test_get_deficit_summary_by_week(self, service):
        """Test weekly deficit summary"""
        section_deficits = [
            {
                "section_id": "SEC-001",
                "week_number": 45,
                "year": 2024,
                "water_demand_m3": 5000,
                "water_delivered_m3": 4000,
                "delivery_deficit_m3": 1000,
                "deficit_percentage": 20.0,
                "stress_level": "moderate",
                "estimated_yield_impact": 10.0
            },
            {
                "section_id": "SEC-002",
                "week_number": 45,
                "year": 2024,
                "water_demand_m3": 4000,
                "water_delivered_m3": 3800,
                "delivery_deficit_m3": 200,
                "deficit_percentage": 5.0,
                "stress_level": "mild",
                "estimated_yield_impact": 2.5
            },
            {
                "section_id": "SEC-003",
                "week_number": 45,
                "year": 2024,
                "water_demand_m3": 3000,
                "water_delivered_m3": 1800,
                "delivery_deficit_m3": 1200,
                "deficit_percentage": 40.0,
                "stress_level": "severe",
                "estimated_yield_impact": 20.0
            }
        ]
        
        summary = await service.get_deficit_summary_by_week(45, 2024, section_deficits)
        
        assert summary["total_sections"] == 3
        assert summary["summary_statistics"]["sections_in_deficit"] == 3
        assert summary["water_balance"]["total_deficit_m3"] == 2400
        assert "stress_distribution" in summary
        assert summary["stress_distribution"]["severe"] == 1
        assert len(summary["priority_sections"]) == 1  # Only severe stress
    
    @pytest.mark.asyncio
    async def test_yield_impact_estimation(self, service):
        """Test yield impact calculation"""
        # Test during critical period
        result = await service._estimate_yield_impact(
            deficit_percentage=20.0,
            stress_level="moderate",
            week_number=15  # Critical growth period
        )
        
        assert result > 0
        assert result <= 50.0  # Max cap
        
        # Test during non-critical period
        result_non_critical = await service._estimate_yield_impact(
            deficit_percentage=20.0,
            stress_level="moderate",
            week_number=25  # Non-critical period
        )
        
        assert result > result_non_critical  # Critical period has higher impact
    
    @pytest.mark.asyncio
    async def test_priority_score_calculation(self, service):
        """Test priority score for recovery"""
        active_deficits = [
            {"week": 42, "year": 2024, "deficit_m3": 500, "age_weeks": 3},
            {"week": 43, "year": 2024, "deficit_m3": 800, "age_weeks": 2},
            {"week": 45, "year": 2024, "deficit_m3": 1000, "age_weeks": 0}
        ]
        
        score = await service._calculate_priority_score(
            total_deficit=2300,
            active_deficits=active_deficits,
            current_stress="severe"
        )
        
        assert score > 0
        assert score <= 100
        
        # Higher stress should give higher score
        score_mild = await service._calculate_priority_score(
            total_deficit=2300,
            active_deficits=active_deficits,
            current_stress="mild"
        )
        
        assert score > score_mild
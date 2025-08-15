"""Integration tests for water accounting service"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import WaterAccountingService
from src.models import Section, WaterDelivery, DeliveryStatus

class TestWaterAccountingIntegration:
    """Integration tests for the complete water accounting workflow"""
    
    @pytest.fixture
    async def service(self):
        return WaterAccountingService()
    
    @pytest.fixture
    async def test_sections(self, db_session: AsyncSession):
        """Create test sections"""
        sections = []
        for i in range(3):
            section = Section(
                id=f"SEC-TEST-{i+1:03d}",
                name=f"Test Section {i+1}",
                zone_id="ZONE-TEST",
                area_hectares=100 + i * 50,
                canal_length_km=2.0 + i * 0.5,
                canal_type="lined" if i == 0 else "earthen",
                soil_type="clay",
                primary_crop="rice",
                crop_stage="vegetative",
                active=True
            )
            db_session.add(section)
            sections.append(section)
        
        await db_session.commit()
        return sections
    
    @pytest.fixture
    async def test_deliveries(self, db_session: AsyncSession, test_sections):
        """Create test deliveries"""
        deliveries = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i, section in enumerate(test_sections):
            for j in range(2):  # 2 deliveries per section
                delivery = WaterDelivery(
                    delivery_id=f"DEL-TEST-{section.id}-{j+1:02d}",
                    section_id=section.id,
                    gate_id=f"GATE-{i+1:03d}",
                    scheduled_start=base_time + timedelta(days=j*2),
                    scheduled_end=base_time + timedelta(days=j*2, hours=4),
                    scheduled_volume_m3=5000,
                    actual_start=base_time + timedelta(days=j*2, minutes=15),
                    actual_end=base_time + timedelta(days=j*2, hours=4, minutes=30),
                    gate_outflow_m3=4800 - (i * 100),  # Decreasing efficiency
                    section_inflow_m3=4600 - (i * 120),
                    transit_loss_m3=200 + (i * 20),
                    status=DeliveryStatus.COMPLETED,
                    flow_readings=[
                        {
                            "timestamp": (base_time + timedelta(days=j*2, hours=k)).isoformat(),
                            "flow_rate_m3s": 0.3 + k * 0.05,
                            "gate_id": f"GATE-{i+1:03d}"
                        }
                        for k in range(5)
                    ]
                )
                db_session.add(delivery)
                deliveries.append(delivery)
        
        await db_session.commit()
        return deliveries
    
    @pytest.mark.asyncio
    async def test_complete_delivery_workflow(self, service, test_sections, db_session, mock_external_services):
        """Test complete delivery processing workflow"""
        # Create new delivery data
        delivery_data = {
            "delivery_id": "DEL-WORKFLOW-001",
            "section_id": test_sections[0].id,
            "scheduled_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "scheduled_end": datetime.now().isoformat(),
            "scheduled_volume_m3": 5000,
            "actual_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "actual_end": datetime.now().isoformat(),
            "flow_readings": [
                {
                    "timestamp": (datetime.now() - timedelta(hours=4-i)).isoformat(),
                    "flow_rate_m3s": 0.4 + i * 0.05,
                    "gate_id": "GATE-001"
                }
                for i in range(9)  # Every 30 minutes
            ],
            "environmental_conditions": {
                "temperature_c": 32,
                "humidity_percent": 65,
                "wind_speed_ms": 2.5
            }
        }
        
        # Process delivery
        result = await service.complete_delivery(
            delivery_data,
            db_session,
            db_session  # Using same session for TimescaleDB in test
        )
        
        assert result["status"] == "completed"
        assert result["delivery_id"] == "DEL-WORKFLOW-001"
        assert "volumes" in result
        assert result["volumes"]["gate_outflow_m3"] > 0
        assert result["volumes"]["section_inflow_m3"] > 0
        assert result["volumes"]["transit_loss_m3"] > 0
        assert "efficiency" in result
        assert result["efficiency"]["delivery_efficiency"] > 0
    
    @pytest.mark.asyncio
    async def test_section_accounting_summary(self, service, test_sections, test_deliveries, db_session):
        """Test section accounting summary generation"""
        # Get accounting for first section
        result = await service.get_section_accounting(
            test_sections[0].id,
            db_session
        )
        
        assert result["section"]["id"] == test_sections[0].id
        assert len(result["recent_deliveries"]) == 2
        assert result["current_metrics"] is not None
        
        # Check metrics calculation
        if result["current_metrics"]:
            assert result["current_metrics"]["total_delivered_m3"] > 0
            assert result["current_metrics"]["delivery_efficiency"] > 0
    
    @pytest.mark.asyncio
    async def test_efficiency_report_generation(self, service, test_sections, test_deliveries, db_session):
        """Test efficiency report generation"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        report = await service.generate_efficiency_report(
            zone_id="ZONE-TEST",
            start_date=start_date,
            end_date=end_date,
            db=db_session
        )
        
        assert report["zone_id"] == "ZONE-TEST"
        assert report["total_sections"] == 3
        assert "summary_statistics" in report
        assert "performance_distribution" in report
        assert "best_performers" in report
        assert "worst_performers" in report
        assert "recommendations" in report
        
        # Check that best performer is the lined canal section
        if report["best_performers"]:
            assert report["best_performers"][0]["section_id"] == test_sections[0].id
    
    @pytest.mark.asyncio
    async def test_deficit_tracking_workflow(self, service, test_sections, db_session):
        """Test deficit tracking and carry-forward"""
        # Create deficit scenario
        section_id = test_sections[0].id
        
        # Week 1: Small deficit
        deficit1 = await service.deficit_service.calculate_delivery_deficit(
            section_id=section_id,
            water_demand_m3=5000,
            water_delivered_m3=4500,
            water_consumed_m3=3825,
            week_number=42,
            year=2024
        )
        
        # Week 2: Larger deficit
        deficit2 = await service.deficit_service.calculate_delivery_deficit(
            section_id=section_id,
            water_demand_m3=5000,
            water_delivered_m3=4000,
            water_consumed_m3=3400,
            week_number=43,
            year=2024
        )
        
        # Update carry-forward
        carry_forward = await service.deficit_service.update_carry_forward(
            section_id=section_id,
            current_deficit=deficit2,
            previous_deficits=[deficit1]
        )
        
        assert carry_forward["active"] == True
        assert carry_forward["total_deficit_m3"] == 1500  # 500 + 1000
        assert carry_forward["weeks_in_deficit"] == 2
        
        # Generate recovery plan
        recovery_plan = await service.deficit_service.generate_recovery_plan(
            carry_forward_data=carry_forward,
            available_capacity_m3=400,
            upcoming_weeks=4
        )
        
        assert recovery_plan["recovery_needed"] == True
        assert recovery_plan["recovery_plan"]["recovery_weeks"] == 4
    
    @pytest.mark.asyncio
    async def test_weekly_deficit_summary(self, service, test_sections, db_session):
        """Test weekly deficit summary generation"""
        # Create deficit records
        from src.models import DeficitRecord
        
        week = 45
        year = 2024
        
        for i, section in enumerate(test_sections):
            deficit = DeficitRecord(
                section_id=section.id,
                week_number=week,
                year=year,
                water_demand_m3=5000,
                water_delivered_m3=5000 - (i * 1000),  # Increasing deficit
                delivery_deficit_m3=i * 1000,
                deficit_percentage=i * 20.0,
                stress_level=["none", "moderate", "severe"][i],
                estimated_yield_impact=i * 10.0
            )
            db_session.add(deficit)
        
        await db_session.commit()
        
        # Get weekly summary
        summary = await service.get_weekly_deficits(week, year, db_session)
        
        assert summary["week_number"] == week
        assert summary["year"] == year
        assert summary["summary_statistics"]["total_sections"] == 3
        assert summary["summary_statistics"]["sections_in_deficit"] == 2  # Sections 2 and 3
        assert summary["water_balance"]["total_deficit_m3"] == 3000  # 0 + 1000 + 2000
        assert len(summary["priority_sections"]) >= 1
        assert summary["priority_sections"][0]["section_id"] == test_sections[2].id  # Highest deficit
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service, db_session):
        """Test error handling in various scenarios"""
        # Test with non-existent section
        with pytest.raises(ValueError, match="Section .* not found"):
            await service.get_section_accounting("INVALID-SECTION", db_session)
        
        # Test with empty flow readings
        delivery_data = {
            "delivery_id": "DEL-ERROR-001",
            "section_id": "SEC-TEST-001",
            "scheduled_start": datetime.now().isoformat(),
            "scheduled_end": datetime.now().isoformat(),
            "scheduled_volume_m3": 5000,
            "actual_start": datetime.now().isoformat(),
            "actual_end": datetime.now().isoformat(),
            "flow_readings": []  # Empty readings
        }
        
        # Should handle gracefully
        result = await service.complete_delivery(
            delivery_data,
            db_session,
            db_session
        )
        
        # Should still process but with zero volumes
        assert result["volumes"]["gate_outflow_m3"] == 0
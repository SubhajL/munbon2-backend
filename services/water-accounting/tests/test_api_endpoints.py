"""Tests for API endpoints"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

class TestAccountingAPI:
    """Test accounting API endpoints"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health endpoint"""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "water-accounting"
    
    @pytest.mark.asyncio
    async def test_get_section_accounting(self, client: AsyncClient, sample_section):
        """Test section accounting endpoint"""
        response = await client.get(f"/api/v1/accounting/section/{sample_section.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["section"]["id"] == sample_section.id
        assert data["section"]["name"] == sample_section.name
        assert "current_metrics" in data
        assert "recent_deliveries" in data
        assert "deficit_status" in data
    
    @pytest.mark.asyncio
    async def test_get_section_not_found(self, client: AsyncClient):
        """Test section not found"""
        response = await client.get("/api/v1/accounting/section/INVALID-ID")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_all_sections(self, client: AsyncClient, sample_section):
        """Test get all sections endpoint"""
        response = await client.get("/api/v1/accounting/sections")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_sections" in data
        assert "sections_with_deficit" in data
        assert "sections" in data
        assert isinstance(data["sections"], list)
    
    @pytest.mark.asyncio
    async def test_get_water_balance(self, client: AsyncClient, sample_section):
        """Test water balance endpoint"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        response = await client.get(
            f"/api/v1/accounting/balance/{sample_section.id}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["section_id"] == sample_section.id
        assert "water_balance" in data
        assert "losses_breakdown" in data
        assert "efficiency" in data

class TestDeliveryAPI:
    """Test delivery API endpoints"""
    
    @pytest.mark.asyncio
    async def test_complete_delivery(self, client: AsyncClient, sample_section, mock_external_services):
        """Test delivery completion"""
        delivery_data = {
            "delivery_id": "DEL-TEST-NEW",
            "section_id": sample_section.id,
            "scheduled_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "scheduled_end": datetime.now().isoformat(),
            "scheduled_volume_m3": 5000,
            "actual_start": (datetime.now() - timedelta(hours=4)).isoformat(),
            "actual_end": datetime.now().isoformat(),
            "flow_readings": [
                {
                    "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                    "flow_rate_m3s": 0.5
                }
                for i in range(5)
            ]
        }
        
        response = await client.post(
            "/api/v1/delivery/complete",
            json=delivery_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert data["delivery_id"] == "DEL-TEST-NEW"
        assert "accounting_summary" in data
    
    @pytest.mark.asyncio
    async def test_validate_flow_data(self, client: AsyncClient):
        """Test flow data validation"""
        flow_readings = [
            {
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "flow_rate_m3s": 0.5 + i * 0.1
            }
            for i in range(5)
        ]
        
        response = await client.post(
            "/api/v1/delivery/validate-flow-data",
            json=flow_readings
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "is_valid" in data
        assert "total_points" in data
        assert "issues" in data

class TestEfficiencyAPI:
    """Test efficiency API endpoints"""
    
    @pytest.mark.asyncio
    async def test_generate_efficiency_report(self, client: AsyncClient):
        """Test efficiency report generation"""
        response = await client.get(
            "/api/v1/efficiency/report",
            params={
                "report_type": "weekly"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "report_id" in data
        assert "summary_statistics" in data
        assert "performance_distribution" in data
        assert "recommendations" in data
    
    @pytest.mark.asyncio
    async def test_calculate_losses(self, client: AsyncClient):
        """Test loss calculation endpoint"""
        loss_data = {
            "flow_data": {
                "flow_rate_m3s": 0.5,
                "transit_time_hours": 2.0,
                "volume_m3": 3600
            },
            "canal_characteristics": {
                "type": "lined",
                "length_km": 5.0,
                "width_m": 3.0,
                "water_depth_m": 1.0
            }
        }
        
        response = await client.post(
            "/api/v1/efficiency/calculate-losses",
            json=loss_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "losses" in data
        assert "uncertainty" in data

class TestDeficitAPI:
    """Test deficit API endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_weekly_deficits(self, client: AsyncClient):
        """Test weekly deficit summary"""
        week = datetime.now().isocalendar().week
        year = datetime.now().year
        
        response = await client.get(f"/api/v1/deficits/week/{week}/{year}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["week_number"] == week
        assert data["year"] == year
        assert "summary_statistics" in data
        assert "water_balance" in data
    
    @pytest.mark.asyncio
    async def test_update_deficit(self, client: AsyncClient, sample_section):
        """Test deficit update"""
        deficit_data = {
            "section_id": sample_section.id,
            "water_demand_m3": 5000,
            "water_delivered_m3": 4000,
            "water_consumed_m3": 3400,
            "week_number": 45,
            "year": 2024
        }
        
        response = await client.post(
            "/api/v1/deficits/update",
            json=deficit_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "updated"
        assert "deficit_calculation" in data
    
    @pytest.mark.asyncio
    async def test_generate_recovery_plan(self, client: AsyncClient, sample_section):
        """Test recovery plan generation"""
        response = await client.post(
            f"/api/v1/deficits/recovery-plan?section_id={sample_section.id}&available_capacity_m3=500"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "section_id" in data
        assert "recovery_needed" in data
        if data["recovery_needed"]:
            assert "recovery_plan" in data

class TestReconciliationAPI:
    """Test reconciliation API endpoints"""
    
    @pytest.mark.asyncio
    async def test_perform_reconciliation(self, client: AsyncClient, sample_delivery):
        """Test weekly reconciliation"""
        week = 45
        year = 2024
        
        response = await client.post(f"/api/v1/reconciliation/weekly/{week}/{year}")
        assert response.status_code == 200
        
        data = response.json()
        assert "reconciliation_id" in data
        assert "status" in data
        assert "water_balance" in data
        assert "adjustments" in data
    
    @pytest.mark.asyncio
    async def test_estimate_manual_flow(self, client: AsyncClient):
        """Test manual gate flow estimation"""
        estimate_data = {
            "gate_id": "GATE-M001",
            "opening_hours": 4.0,
            "opening_percentage": 75.0,
            "head_difference_m": 1.5,
            "gate_width_m": 2.0
        }
        
        response = await client.post(
            "/api/v1/reconciliation/estimate-manual-flow",
            json=estimate_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["gate_id"] == "GATE-M001"
        assert "estimated_flow_rate_m3s" in data
        assert "estimated_volume_m3" in data
        assert "confidence_level" in data
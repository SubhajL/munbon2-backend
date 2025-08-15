"""
Integration tests for schedule API endpoints.
"""

import pytest
from datetime import date, datetime
from uuid import uuid4

from fastapi import status


class TestScheduleAPI:
    """Test schedule API endpoints"""
    
    @pytest.mark.asyncio
    async def test_generate_schedule_success(
        self, test_client, sample_schedule_data, mock_external_services, auth_headers
    ):
        """Test successful schedule generation"""
        response = test_client.post(
            "/api/v1/schedule/generate",
            json=sample_schedule_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["week_number"] == sample_schedule_data["week_number"]
        assert data["year"] == sample_schedule_data["year"]
        assert data["status"] == "draft"
        assert "id" in data
        assert "schedule_code" in data
    
    @pytest.mark.asyncio
    async def test_generate_schedule_duplicate(
        self, test_client, sample_schedule_data, sample_schedule, auth_headers
    ):
        """Test generating duplicate schedule returns conflict"""
        # Try to generate schedule for same week
        response = test_client.post(
            "/api/v1/schedule/generate",
            json={
                "week_number": sample_schedule.week_number,
                "year": sample_schedule.year,
                "constraints": {},
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_schedule_by_id(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test retrieving schedule by ID"""
        response = test_client.get(
            f"/api/v1/schedule/{sample_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == str(sample_schedule.id)
        assert data["schedule_code"] == sample_schedule.schedule_code
        assert data["week_number"] == sample_schedule.week_number
    
    @pytest.mark.asyncio
    async def test_get_schedule_not_found(
        self, test_client, auth_headers
    ):
        """Test retrieving non-existent schedule"""
        fake_id = str(uuid4())
        response = test_client.get(
            f"/api/v1/schedule/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_get_schedule_by_week(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test retrieving schedule by week number"""
        response = test_client.get(
            f"/api/v1/schedule/week/{sample_schedule.week_number}/{sample_schedule.year}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["week_number"] == sample_schedule.week_number
        assert data["year"] == sample_schedule.year
    
    @pytest.mark.asyncio
    async def test_list_schedules(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test listing schedules with filters"""
        # List all schedules
        response = test_client.get(
            "/api/v1/schedule/",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Filter by year
        response = test_client.get(
            f"/api/v1/schedule/?year={sample_schedule.year}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(s["year"] == sample_schedule.year for s in data)
        
        # Filter by status
        response = test_client.get(
            f"/api/v1/schedule/?status={sample_schedule.status}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(s["status"] == sample_schedule.status for s in data)
    
    @pytest.mark.asyncio
    async def test_approve_schedule(
        self, test_client, sample_schedule, mock_external_services, auth_headers
    ):
        """Test approving a draft schedule"""
        response = test_client.post(
            f"/api/v1/schedule/{sample_schedule.id}/approve",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "approved"
        assert data["id"] == str(sample_schedule.id)
    
    @pytest.mark.asyncio
    async def test_approve_non_draft_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test approving non-draft schedule fails"""
        # Set schedule to approved
        sample_schedule.status = "approved"
        
        response = test_client.post(
            f"/api/v1/schedule/{sample_schedule.id}/approve",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @pytest.mark.asyncio
    async def test_activate_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test activating an approved schedule"""
        # First approve the schedule
        sample_schedule.status = "approved"
        
        response = test_client.post(
            f"/api/v1/schedule/{sample_schedule.id}/activate",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "active"
        assert "activated_at" in data
    
    @pytest.mark.asyncio
    async def test_update_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test updating schedule metadata"""
        update_data = {
            "notes": "Updated schedule notes",
            "optimization_constraints": {
                "max_daily_operations": 60,
                "priority_zones": ["ZONE-001", "ZONE-003"],
            }
        }
        
        response = test_client.patch(
            f"/api/v1/schedule/{sample_schedule.id}",
            json=update_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["notes"] == update_data["notes"]
        assert data["optimization_constraints"]["max_daily_operations"] == 60
    
    @pytest.mark.asyncio
    async def test_update_non_draft_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test updating non-draft schedule fails"""
        sample_schedule.status = "active"
        
        response = test_client.patch(
            f"/api/v1/schedule/{sample_schedule.id}",
            json={"notes": "Should fail"},
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @pytest.mark.asyncio
    async def test_delete_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test deleting a draft schedule"""
        response = test_client.delete(
            f"/api/v1/schedule/{sample_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deleted successfully" in data["message"]
        
        # Verify schedule is deleted
        response = test_client.get(
            f"/api/v1/schedule/{sample_schedule.id}",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_delete_active_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test deleting active schedule fails"""
        sample_schedule.status = "active"
        
        response = test_client.delete(
            f"/api/v1/schedule/{sample_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    @pytest.mark.asyncio
    async def test_clone_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test cloning schedule to new week"""
        target_week = sample_schedule.week_number + 1
        
        response = test_client.post(
            f"/api/v1/schedule/{sample_schedule.id}/clone",
            params={
                "target_week": target_week,
                "target_year": sample_schedule.year,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["week_number"] == target_week
        assert data["year"] == sample_schedule.year
        assert data["status"] == "draft"
        assert data["version"] == 1
    
    @pytest.mark.asyncio
    async def test_schedule_validation(
        self, test_client, auth_headers
    ):
        """Test schedule request validation"""
        # Invalid week number
        response = test_client.post(
            "/api/v1/schedule/generate",
            json={
                "week_number": 54,  # Invalid
                "year": 2024,
                "constraints": {},
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Invalid year
        response = test_client.post(
            "/api/v1/schedule/generate",
            json={
                "week_number": 15,
                "year": 2023,  # Too old
                "constraints": {},
            },
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_schedule_authorization(
        self, test_client, sample_schedule
    ):
        """Test authorization is required"""
        # No auth headers
        response = test_client.get(
            f"/api/v1/schedule/{sample_schedule.id}"
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
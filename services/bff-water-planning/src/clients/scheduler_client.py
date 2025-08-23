"""
Scheduler Service Client
Handles communication with the scheduler service
"""

from typing import Dict, List, Optional
import httpx
from datetime import datetime
from core import get_logger
from config import settings

logger = get_logger(__name__)


class SchedulerClient:
    """Client for interacting with Scheduler service"""
    
    def __init__(self):
        # Use mock server URL if enabled, otherwise use actual scheduler service URL
        if settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/scheduler"
        else:
            self.base_url = settings.scheduler_url
        self.logger = logger.bind(client="scheduler")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
    
    async def get_schedules(
        self, 
        section_id: Optional[str] = None,
        schedule_type: Optional[str] = None,
        status: Optional[str] = None,
        date: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """Get irrigation schedules"""
        try:
            params = {}
            if section_id:
                params["section_id"] = section_id
            if schedule_type:
                params["schedule_type"] = schedule_type
            if status:
                params["status"] = status
            if date:
                params["date"] = date
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("schedules", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get schedules", error=str(e))
            return None
    
    async def create_schedule(self, schedule_data: Dict) -> Optional[Dict]:
        """Create a new irrigation schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/schedules",
                    json=schedule_data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to create schedule", error=str(e))
            return None
    
    async def update_schedule(self, schedule_id: str, updates: Dict) -> Optional[Dict]:
        """Update an existing schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}",
                    json=updates
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to update schedule", 
                            schedule_id=schedule_id, error=str(e))
            return None
    
    async def get_schedule_executions(
        self,
        schedule_id: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[Dict]]:
        """Get execution history for a schedule"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}/executions",
                    params={
                        "start_date": start_date,
                        "end_date": end_date
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("executions", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get schedule executions", 
                            schedule_id=schedule_id, error=str(e))
            return None
    
    async def check_schedule_conflicts(
        self,
        section_id: str,
        start_time: str,
        duration_minutes: int
    ) -> Optional[Dict]:
        """Check for scheduling conflicts"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/schedules/conflicts",
                    params={
                        "section_id": section_id,
                        "start_time": start_time,
                        "duration_minutes": duration_minutes
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to check schedule conflicts", 
                            section_id=section_id, error=str(e))
            return None
    
    async def execute_schedule_now(self, schedule_id: str) -> Optional[Dict]:
        """Execute a schedule immediately"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/schedules/{schedule_id}/execute"
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to execute schedule", 
                            schedule_id=schedule_id, error=str(e))
            return None
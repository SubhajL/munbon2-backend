"""
Flow Monitoring Service Client
Handles communication with the flow monitoring service
"""

from typing import Dict, List, Optional
import httpx
from datetime import datetime
from core import get_logger
from config import settings

logger = get_logger(__name__)


class FlowMonitoringClient:
    """Client for interacting with Flow Monitoring service"""
    
    def __init__(self):
        # Use mock server URL if enabled, otherwise use actual flow monitoring service URL
        if settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/flow"
        else:
            self.base_url = settings.flow_monitoring_url
        self.logger = logger.bind(client="flow_monitoring")
        self.timeout = httpx.Timeout(30.0, connect=5.0)
    
    async def get_current_flow(self, section_id: str) -> Optional[Dict]:
        """Get current flow readings for a section"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/flow/current",
                    params={"section_id": section_id}
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get current flow", 
                            section_id=section_id, error=str(e))
            return None
    
    async def get_flow_history(
        self, 
        section_id: str,
        start_date: str,
        end_date: str,
        interval: str = "hourly"
    ) -> Optional[Dict]:
        """Get historical flow data"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/flow/history",
                    params={
                        "section_id": section_id,
                        "start_date": start_date,
                        "end_date": end_date,
                        "interval": interval
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get flow history", 
                            section_id=section_id, error=str(e))
            return None
    
    async def get_flow_balance(self, section_id: str, date: Optional[str] = None) -> Optional[Dict]:
        """Get flow balance for a section"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                params = {"section_id": section_id}
                if date:
                    params["date"] = date
                
                response = await client.get(
                    f"{self.base_url}/api/v1/flow/balance/{section_id}",
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            self.logger.error("Failed to get flow balance", 
                            section_id=section_id, error=str(e))
            return None
    
    async def get_flow_sensors(self) -> Optional[List[Dict]]:
        """Get all flow sensor information"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/v1/flow/sensors")
                response.raise_for_status()
                data = response.json()
                return data.get("sensors", [])
        except httpx.HTTPError as e:
            self.logger.error("Failed to get flow sensors", error=str(e))
            return None
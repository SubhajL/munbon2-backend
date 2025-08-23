import httpx
from typing import Dict, List, Optional
from datetime import datetime
from core import get_logger
from config import settings

logger = get_logger(__name__)


class AWDControlClient:
    """Client for AWD Control Service integration"""
    
    def __init__(self):
        # Use mock server URL if enabled, otherwise use actual AWD service URL
        if settings.use_mock_server:
            self.base_url = f"{settings.mock_server_url}/awd"
        else:
            self.base_url = settings.awd_control_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"{settings.service_name}/1.0"
            }
        )
        self.logger = logger.bind(service="awd_client")
    
    async def get_plot_status(self, plot_id: str) -> Optional[Dict]:
        """Get AWD status for a specific plot"""
        try:
            response = await self.client.get(f"/api/v1/awd/plots/{plot_id}/status")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Plot {plot_id} not found in AWD system")
                return None
            self.logger.error(f"Failed to get AWD status for plot {plot_id}", error=str(e))
            raise
        except Exception as e:
            self.logger.error(f"AWD client error for plot {plot_id}", error=str(e))
            return None
    
    async def get_batch_status(self, plot_ids: List[str]) -> Dict[str, Dict]:
        """Get AWD status for multiple plots"""
        try:
            response = await self.client.post(
                "/api/v1/awd/batch-status",
                json={"plot_ids": plot_ids}
            )
            response.raise_for_status()
            data = response.json()
            
            # Convert list to dict for easy lookup
            status_map = {}
            for status in data.get("statuses", []):
                status_map[status["plot_id"]] = status
            
            return status_map
        except Exception as e:
            self.logger.error("Failed to get batch AWD status", error=str(e))
            return {}
    
    async def get_zone_summary(self, zone_id: str) -> Optional[Dict]:
        """Get AWD summary for an entire zone"""
        try:
            response = await self.client.get(f"/api/v1/awd/zones/{zone_id}/summary")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get AWD zone summary for {zone_id}", error=str(e))
            return None
    
    async def get_recommendations(
        self, 
        plot_ids: List[str],
        include_weather: bool = True
    ) -> List[Dict]:
        """Get AWD recommendations for multiple plots"""
        try:
            params = {
                "include_weather": include_weather
            }
            response = await self.client.post(
                "/api/v1/awd/recommendations",
                json={"plot_ids": plot_ids},
                params=params
            )
            response.raise_for_status()
            return response.json().get("recommendations", [])
        except Exception as e:
            self.logger.error("Failed to get AWD recommendations", error=str(e))
            return []
    
    async def update_moisture_reading(
        self,
        plot_id: str,
        moisture_level: float,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """Update moisture reading for a plot"""
        try:
            data = {
                "plot_id": plot_id,
                "moisture_level": moisture_level,
                "timestamp": (timestamp or datetime.utcnow()).isoformat()
            }
            response = await self.client.post(
                "/api/v1/awd/moisture-readings",
                json=data
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to update moisture for plot {plot_id}",
                error=str(e),
                moisture_level=moisture_level
            )
            return False
    
    async def activate_awd(
        self,
        plot_id: str,
        parameters: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Activate AWD mode for a plot"""
        try:
            data = {
                "plot_id": plot_id,
                "parameters": parameters or {
                    "dry_threshold": 15,  # cm below surface
                    "wet_threshold": 5,   # cm below surface
                    "monitoring_interval_hours": 24
                }
            }
            response = await self.client.post(
                f"/api/v1/awd/plots/{plot_id}/activate",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to activate AWD for plot {plot_id}", error=str(e))
            return None
    
    async def deactivate_awd(self, plot_id: str, reason: str = "") -> bool:
        """Deactivate AWD mode for a plot"""
        try:
            response = await self.client.post(
                f"/api/v1/awd/plots/{plot_id}/deactivate",
                json={"reason": reason}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"Failed to deactivate AWD for plot {plot_id}", error=str(e))
            return False
    
    async def get_water_savings_report(
        self,
        zone_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[Dict]:
        """Get water savings report for AWD implementation"""
        try:
            params = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
            response = await self.client.get(
                f"/api/v1/awd/zones/{zone_id}/savings-report",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(
                f"Failed to get savings report for zone {zone_id}",
                error=str(e)
            )
            return None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
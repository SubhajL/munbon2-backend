from typing import List, Optional, Dict
import httpx
from .base_loader import BaseDataLoader
from config import settings


class AWDStatusLoader(BaseDataLoader):
    """DataLoader for batch loading AWD status from AWD Control Service"""
    
    def __init__(self, db_manager):
        super().__init__(db_manager)
        self.client = httpx.AsyncClient(
            base_url=settings.awd_control_url,
            timeout=30.0
        )
    
    async def batch_load_fn(self, plot_ids: List[str]) -> List[Optional[Dict]]:
        """
        Batch load AWD status for multiple plots
        
        Args:
            plot_ids: List of plot IDs to load AWD status for
            
        Returns:
            List of AWD status data in same order as requested IDs
        """
        if not plot_ids:
            return []
        
        self.logger.info(f"Batch loading AWD status for {len(plot_ids)} plots")
        
        try:
            # Call AWD Control Service batch endpoint
            response = await self.client.post(
                "/api/v1/awd/batch-status",
                json={"plot_ids": plot_ids}
            )
            response.raise_for_status()
            
            data = response.json()
            awd_statuses = data.get("statuses", [])
            
            # Convert to dict format
            status_map = {
                status["plot_id"]: {
                    "plot_id": status["plot_id"],
                    "is_active": status.get("is_active", False),
                    "current_phase": status.get("current_phase", "unknown"),
                    "moisture_level": status.get("moisture_level"),
                    "last_irrigation": status.get("last_irrigation"),
                    "next_check": status.get("next_check"),
                    "recommendation": status.get("recommendation", ""),
                    "expected_savings": status.get("expected_savings", 0)
                }
                for status in awd_statuses
            }
            
            # Return in requested order
            return [status_map.get(plot_id) for plot_id in plot_ids]
            
        except Exception as e:
            self.logger.error(f"Failed to load AWD statuses: {e}")
            # Return None for all requested IDs on error
            return [None] * len(plot_ids)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
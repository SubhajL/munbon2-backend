"""
Client for Gate Control service integration
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from .base_client import BaseServiceClient
import logging

logger = logging.getLogger(__name__)


class GateControlClient(BaseServiceClient):
    """Client for interacting with Gate Control service"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url, "Gate Control Service")
    
    async def get_gate_status(self, gate_id: str) -> Dict[str, Any]:
        """Get current gate status including position and mode"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/status"
            
            response = await self.get(endpoint)
            
            return {
                "gate_id": gate_id,
                "current_opening_m": response.get("current_opening_m", 0),
                "target_opening_m": response.get("target_opening_m", 0),
                "operation_mode": response.get("operation_mode", "manual"),
                "control_level": response.get("control_level", "L0"),
                "is_operational": response.get("is_operational", True),
                "last_movement": response.get("last_movement"),
                "alarm_status": response.get("alarm_status", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get gate status for {gate_id}: {str(e)}")
            raise
    
    async def set_gate_position(
        self,
        gate_id: str,
        target_opening_m: float,
        mode: str = "automatic"
    ) -> Dict[str, Any]:
        """Set gate target position for automatic gates"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/position"
            data = {
                "target_opening_m": target_opening_m,
                "mode": mode,
                "source": "simulation"
            }
            
            response = await self.post(endpoint, data)
            
            return {
                "gate_id": gate_id,
                "accepted": response.get("accepted", False),
                "estimated_time_seconds": response.get("estimated_time_seconds", 0),
                "message": response.get("message", "")
            }
            
        except Exception as e:
            logger.error(f"Failed to set gate position for {gate_id}: {str(e)}")
            raise
    
    async def get_discrete_control_levels(self, gate_id: str) -> List[Dict[str, float]]:
        """Get discrete control levels for automatic gates"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/control-levels"
            
            response = await self.get(endpoint)
            
            return response.get("levels", [])
            
        except Exception as e:
            logger.error(f"Failed to get control levels for {gate_id}: {str(e)}")
            raise
    
    async def batch_gate_control(
        self,
        gate_commands: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Control multiple gates in batch"""
        try:
            endpoint = "/api/v1/gates/batch-control"
            data = {"commands": gate_commands}
            
            response = await self.post(endpoint, data)
            
            return response.get("results", [])
            
        except Exception as e:
            logger.error(f"Failed to batch control gates: {str(e)}")
            raise
    
    async def get_gate_maintenance_status(self, gate_id: str) -> Dict[str, Any]:
        """Get maintenance status and constraints for a gate"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/maintenance"
            
            response = await self.get(endpoint)
            
            return {
                "gate_id": gate_id,
                "maintenance_required": response.get("maintenance_required", False),
                "next_maintenance": response.get("next_maintenance"),
                "operational_hours": response.get("operational_hours", 0),
                "movement_count": response.get("movement_count", 0),
                "restrictions": response.get("restrictions", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get maintenance status for {gate_id}: {str(e)}")
            raise
    
    async def get_zone_gates(self, zone: int) -> List[Dict[str, Any]]:
        """Get all gates in a specific zone"""
        try:
            endpoint = "/api/v1/zones/{zone}/gates"
            
            response = await self.get(endpoint)
            
            return response.get("gates", [])
            
        except Exception as e:
            logger.error(f"Failed to get gates for zone {zone}: {str(e)}")
            raise
    
    async def simulate_gate_operation(
        self,
        gate_id: str,
        from_opening_m: float,
        to_opening_m: float
    ) -> Dict[str, Any]:
        """Simulate gate operation timing and constraints"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/simulate"
            data = {
                "from_opening_m": from_opening_m,
                "to_opening_m": to_opening_m
            }
            
            response = await self.post(endpoint, data)
            
            return {
                "duration_seconds": response.get("duration_seconds", 0),
                "energy_kwh": response.get("energy_kwh", 0),
                "feasible": response.get("feasible", True),
                "constraints": response.get("constraints", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to simulate gate operation: {str(e)}")
            raise
    
    async def get_gate_operation_history(
        self,
        gate_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get historical gate operations"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/history"
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            response = await self.get(endpoint, params=params)
            
            return response.get("operations", [])
            
        except Exception as e:
            logger.error(f"Failed to get operation history: {str(e)}")
            raise
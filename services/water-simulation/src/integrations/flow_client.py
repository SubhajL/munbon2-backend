"""
Client for Flow Monitoring service integration
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from .base_client import BaseServiceClient
import logging

logger = logging.getLogger(__name__)


class FlowMonitoringClient(BaseServiceClient):
    """Client for interacting with Flow Monitoring service"""
    
    def __init__(self, base_url: str):
        super().__init__(base_url, "Flow Monitoring Service")
    
    async def calculate_gate_flow(
        self,
        gate_id: str,
        opening_m: float,
        upstream_level_m: float,
        downstream_level_m: float
    ) -> Dict[str, Any]:
        """Calculate flow through a gate using calibrated flow models"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/flow"
            data = {
                "opening_m": opening_m,
                "upstream_level_m": upstream_level_m,
                "downstream_level_m": downstream_level_m
            }
            
            response = await self.post(endpoint, data)
            
            return {
                "gate_id": gate_id,
                "flow_m3s": response.get("flow_m3s", 0),
                "flow_type": response.get("flow_type", "unknown"),
                "velocity_ms": response.get("velocity_ms", 0),
                "froude_number": response.get("froude_number", 0),
                "discharge_coefficient": response.get("discharge_coefficient", 0),
                "k1_coefficient": response.get("k1_coefficient", 0),
                "k2_coefficient": response.get("k2_coefficient", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate flow for gate {gate_id}: {str(e)}")
            raise
    
    async def get_gate_properties(self, gate_id: str) -> Dict[str, Any]:
        """Get enhanced gate properties including shape and dimensions"""
        try:
            endpoint = f"/api/v1/gates/{gate_id}/properties"
            
            response = await self.get(endpoint)
            
            return {
                "gate_id": gate_id,
                "gate_type": response.get("gate_type", "sluice"),
                "shape": response.get("shape", "rectangular"),
                "width_m": response.get("width_m", 1.0),
                "height_m": response.get("height_m", 1.0),
                "diameter_m": response.get("diameter_m"),
                "invert_level_m": response.get("invert_level_m", 0),
                "max_opening_m": response.get("max_opening_m", 1.0),
                "control_type": response.get("control_type", "manual"),
                "discrete_levels": response.get("discrete_levels", []),
                "zone": response.get("zone", 0),
                "location": response.get("location", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get properties for gate {gate_id}: {str(e)}")
            raise
    
    async def get_multiple_gate_flows(
        self,
        gate_configs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calculate flows for multiple gates in batch"""
        try:
            endpoint = "/api/v1/gates/batch-flow"
            data = {"gates": gate_configs}
            
            response = await self.post(endpoint, data)
            
            return response.get("flows", [])
            
        except Exception as e:
            logger.error(f"Failed to calculate batch flows: {str(e)}")
            raise
    
    async def estimate_water_level(
        self,
        location_id: str,
        inflow_m3s: float,
        outflow_m3s: float,
        current_level_m: float,
        time_step_seconds: int = 3600
    ) -> float:
        """Estimate water level change at a location"""
        try:
            endpoint = f"/api/v1/locations/{location_id}/water-level"
            data = {
                "inflow_m3s": inflow_m3s,
                "outflow_m3s": outflow_m3s,
                "current_level_m": current_level_m,
                "time_step_seconds": time_step_seconds
            }
            
            response = await self.post(endpoint, data)
            
            return response.get("new_level_m", current_level_m)
            
        except Exception as e:
            logger.error(f"Failed to estimate water level at {location_id}: {str(e)}")
            raise
    
    async def get_canal_properties(self, canal_id: str) -> Dict[str, Any]:
        """Get canal hydraulic properties"""
        try:
            endpoint = f"/api/v1/canals/{canal_id}/properties"
            
            response = await self.get(endpoint)
            
            return {
                "canal_id": canal_id,
                "cross_section_area_m2": response.get("cross_section_area_m2", 10),
                "wetted_perimeter_m": response.get("wetted_perimeter_m", 5),
                "hydraulic_radius_m": response.get("hydraulic_radius_m", 2),
                "manning_n": response.get("manning_n", 0.025),
                "bed_slope": response.get("bed_slope", 0.0001),
                "length_km": response.get("length_km", 1),
                "capacity_m3s": response.get("capacity_m3s", 20)
            }
            
        except Exception as e:
            logger.error(f"Failed to get canal properties for {canal_id}: {str(e)}")
            raise
    
    async def create_job_order(
        self,
        gate_id: str,
        target_opening_m: float,
        priority: str = "normal",
        reason: str = "Simulation scheduled operation"
    ) -> Dict[str, Any]:
        """Create a job order for manual gate operation"""
        try:
            endpoint = "/api/v1/job-orders"
            data = {
                "gate_id": gate_id,
                "target_opening_m": target_opening_m,
                "priority": priority,
                "reason": reason
            }
            
            response = await self.post(endpoint, data)
            
            return {
                "order_id": response.get("order_id"),
                "gate_id": gate_id,
                "scheduled_time": response.get("scheduled_time"),
                "estimated_duration_minutes": response.get("estimated_duration_minutes", 30),
                "status": response.get("status", "pending")
            }
            
        except Exception as e:
            logger.error(f"Failed to create job order: {str(e)}")
            raise
    
    async def get_flow_network_state(
        self,
        zone: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get current state of the flow network"""
        try:
            endpoint = "/api/v1/network/state"
            params = {"zone": zone} if zone is not None else {}
            
            response = await self.get(endpoint, params=params)
            
            return {
                "timestamp": response.get("timestamp"),
                "gates": response.get("gates", {}),
                "water_levels": response.get("water_levels", {}),
                "flows": response.get("flows", {}),
                "active_job_orders": response.get("active_job_orders", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get flow network state: {str(e)}")
            raise
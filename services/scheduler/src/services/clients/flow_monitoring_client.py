from typing import List, Dict, Any, Optional
import asyncio
import json
import websockets

from .base_client import BaseServiceClient
from ...core.config import settings
from ...core.logger import get_logger

logger = get_logger(__name__)


class FlowMonitoringClient(BaseServiceClient):
    """Client for Flow Monitoring Service"""
    
    def __init__(self):
        super().__init__(settings.flow_monitoring_url, "FlowMonitoring")
        self.ws_url = settings.flow_monitoring_url.replace("http://", "ws://").replace("https://", "wss://")
    
    async def get_hydraulic_model(
        self,
        gate_settings: Dict[str, float],
        target_flows: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Get hydraulic model results for given gate settings"""
        data = {
            "gateSettings": gate_settings,
        }
        if target_flows:
            data["targetFlows"] = target_flows
        
        response = await self.get("/api/v1/hydraulics/model", data)
        return response.get("data", {})
    
    async def calculate_gate_flow(
        self,
        gate_id: str,
        opening_percent: float,
        upstream_level: float,
        downstream_level: float
    ) -> Dict[str, Any]:
        """Calculate flow through a gate"""
        data = {
            "gateId": gate_id,
            "openingPercent": opening_percent,
            "upstreamLevel": upstream_level,
            "downstreamLevel": downstream_level,
        }
        
        response = await self.post("/api/v1/flow/calculate", data)
        return response.get("data", {})
    
    async def get_current_flow(self, location_id: str) -> Dict[str, Any]:
        """Get current flow rate at a location"""
        response = await self.get(f"/api/v1/flow/latest/{location_id}")
        return response.get("data", {})
    
    async def get_water_propagation(
        self,
        source_gate: str,
        flow_change: float,
        duration_hours: float
    ) -> Dict[str, Any]:
        """Calculate water propagation through network"""
        data = {
            "sourceGate": source_gate,
            "flowChange": flow_change,
            "durationHours": duration_hours,
        }
        
        response = await self.post("/api/v1/model/propagation", data)
        return response.get("data", {})
    
    async def get_network_efficiency(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get network efficiency metrics"""
        params = {}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        response = await self.get("/api/v1/analytics/efficiency", params)
        return response.get("data", {})
    
    async def get_anomalies(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent anomaly detections"""
        params = {"limit": limit}
        response = await self.get("/api/v1/alerts/anomalies", params)
        return response.get("data", [])
    
    async def subscribe_gate_states(self, callback):
        """Subscribe to real-time gate state updates via WebSocket"""
        ws_endpoint = f"{self.ws_url}/ws/gate-states"
        
        try:
            async with websockets.connect(ws_endpoint) as websocket:
                logger.info("Connected to Flow Monitoring WebSocket")
                
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        await callback(data)
                    except websockets.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {str(e)}")
            raise
    
    async def get_gate_positions(self) -> Dict[str, float]:
        """Get current positions of all gates"""
        response = await self.get("/api/v1/gates/positions")
        return response.get("data", {})
    
    async def get_travel_time(
        self,
        from_gate: str,
        to_gate: str,
        flow_rate: float
    ) -> float:
        """Get water travel time between gates"""
        params = {
            "fromGate": from_gate,
            "toGate": to_gate,
            "flowRate": flow_rate,
        }
        
        response = await self.get("/api/v1/hydraulics/travel-time", params)
        return response.get("data", {}).get("travelTimeHours", 0.0)
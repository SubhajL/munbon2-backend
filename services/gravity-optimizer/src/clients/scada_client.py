"""SCADA Integration Service client for gate control and monitoring"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
from enum import Enum
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class GateStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    FAULT = "fault"
    MAINTENANCE = "maintenance"


class GateControl(BaseModel):
    """Gate control command"""
    gate_id: str
    target_opening: float  # 0.0 to 1.0
    rate_of_change: Optional[float] = 0.1  # opening units per second
    priority: int = 5  # 1-10, higher = more urgent


class GateReading(BaseModel):
    """Real-time gate reading from SCADA"""
    gate_id: str
    current_opening: float  # 0.0 to 1.0
    status: GateStatus
    upstream_level: Optional[float]  # meters
    downstream_level: Optional[float]  # meters
    flow_rate: Optional[float]  # m³/s
    timestamp: datetime
    quality: str  # good, uncertain, bad


class ChannelReading(BaseModel):
    """Channel sensor readings"""
    channel_id: str
    location: str
    water_level: float  # meters
    flow_rate: Optional[float]  # m³/s
    velocity: Optional[float]  # m/s
    timestamp: datetime
    sensor_id: str


class SCADAClient(BaseServiceClient):
    """Client for SCADA Integration Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        # Get URL from service registry if not provided
        if not base_url:
            from .service_registry import service_registry
            import asyncio
            service_info = asyncio.run(service_registry.discover('scada'))
            base_url = service_info.url if service_info else 'http://localhost:3008'
        
        super().__init__(
            service_name='SCADA Service',
            base_url=base_url,
            timeout=10.0  # Shorter timeout for real-time operations
        )
    
    async def get_gate_status(self, gate_id: str) -> Optional[GateReading]:
        """Get current status of a gate"""
        try:
            response = await self.get(f'/api/v1/scada/gates/{gate_id}/status')
            return GateReading(**response)
            
        except Exception as e:
            logger.error(f"Failed to get gate {gate_id} status: {e}")
            return None
    
    async def get_all_gates_status(self) -> List[GateReading]:
        """Get status of all gates"""
        try:
            response = await self.get('/api/v1/scada/gates/status')
            
            readings = []
            for reading_data in response.get('gates', []):
                readings.append(GateReading(**reading_data))
            
            logger.info(f"Retrieved status for {len(readings)} gates")
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get all gates status: {e}")
            return []
    
    async def control_gate(self, control: GateControl) -> bool:
        """Send gate control command"""
        try:
            response = await self.post(
                f'/api/v1/scada/gates/{control.gate_id}/control',
                model=control
            )
            
            success = response.get('success', False)
            if success:
                logger.info(f"Gate {control.gate_id} control command sent successfully")
            else:
                logger.warning(f"Gate {control.gate_id} control failed: {response.get('message')}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to control gate {control.gate_id}: {e}")
            return False
    
    async def batch_control_gates(self, controls: List[GateControl]) -> Dict[str, bool]:
        """Send multiple gate control commands"""
        try:
            data = {
                'controls': [c.model_dump() for c in controls],
                'coordination_mode': 'synchronized'
            }
            
            response = await self.post('/api/v1/scada/gates/batch-control', data=data)
            
            results = response.get('results', {})
            success_count = sum(1 for v in results.values() if v)
            logger.info(f"Batch control: {success_count}/{len(controls)} gates controlled successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to batch control gates: {e}")
            return {c.gate_id: False for c in controls}
    
    async def get_channel_readings(self, channel_id: str) -> List[ChannelReading]:
        """Get sensor readings for a channel"""
        try:
            response = await self.get(f'/api/v1/scada/channels/{channel_id}/readings')
            
            readings = []
            for reading_data in response.get('readings', []):
                readings.append(ChannelReading(**reading_data))
            
            return readings
            
        except Exception as e:
            logger.error(f"Failed to get channel {channel_id} readings: {e}")
            return []
    
    async def subscribe_gate_updates(self, gate_ids: List[str], callback):
        """Subscribe to real-time gate updates (WebSocket)"""
        # This would typically use WebSocket for real-time updates
        # For now, we'll use polling as a simplified version
        logger.warning("Real-time subscription not implemented, use polling instead")
        pass
    
    async def emergency_stop(self, gate_ids: List[str], reason: str) -> bool:
        """Emergency stop for gates"""
        try:
            response = await self.post(
                '/api/v1/scada/emergency/stop',
                data={
                    'gate_ids': gate_ids,
                    'reason': reason,
                    'initiated_by': 'gravity-optimizer',
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            success = response.get('success', False)
            if success:
                logger.warning(f"Emergency stop executed for {len(gate_ids)} gates: {reason}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to execute emergency stop: {e}")
            return False
    
    async def get_maintenance_status(self) -> Dict[str, str]:
        """Get maintenance status of gates"""
        try:
            response = await self.get('/api/v1/scada/maintenance/status')
            return response.get('gates', {})
            
        except Exception as e:
            logger.error(f"Failed to get maintenance status: {e}")
            return {}
    
    async def verify_gate_position(
        self, 
        gate_id: str, 
        expected_opening: float,
        tolerance: float = 0.05
    ) -> bool:
        """Verify gate reached expected position"""
        try:
            status = await self.get_gate_status(gate_id)
            
            if not status:
                return False
            
            actual = status.current_opening
            expected = expected_opening
            
            within_tolerance = abs(actual - expected) <= tolerance
            
            if not within_tolerance:
                logger.warning(
                    f"Gate {gate_id} position mismatch: "
                    f"expected={expected:.2f}, actual={actual:.2f}"
                )
            
            return within_tolerance
            
        except Exception as e:
            logger.error(f"Failed to verify gate {gate_id} position: {e}")
            return False
    
    async def calibrate_gate(self, gate_id: str) -> bool:
        """Request gate calibration"""
        try:
            response = await self.post(
                f'/api/v1/scada/gates/{gate_id}/calibrate',
                data={'requested_by': 'gravity-optimizer'}
            )
            
            return response.get('success', False)
            
        except Exception as e:
            logger.error(f"Failed to calibrate gate {gate_id}: {e}")
            return False
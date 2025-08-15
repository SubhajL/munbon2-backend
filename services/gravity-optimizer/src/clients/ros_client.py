"""ROS (Resource Optimization Service) client for water allocation data"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date
from pydantic import BaseModel
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class WaterAllocation(BaseModel):
    """Water allocation from ROS"""
    zone_id: str
    allocated_volume: float  # m³
    required_flow_rate: float  # m³/s
    priority: int
    start_time: datetime
    end_time: datetime
    crop_type: Optional[str] = None
    irrigation_method: Optional[str] = None


class WaterDemand(BaseModel):
    """Water demand forecast"""
    zone_id: str
    date: date
    base_demand: float  # m³
    weather_adjusted_demand: float  # m³
    crop_coefficient: float
    efficiency_factor: float


class IrrigationSchedule(BaseModel):
    """Irrigation schedule from ROS"""
    schedule_id: str
    zone_id: str
    start_time: datetime
    duration_hours: float
    volume_m3: float
    flow_rate_m3s: float
    priority: int
    status: str  # scheduled, active, completed, cancelled


class ROSClient(BaseServiceClient):
    """Client for Resource Optimization Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        # Get URL from service registry if not provided
        if not base_url:
            from .service_registry import service_registry
            import asyncio
            service_info = asyncio.run(service_registry.discover('ros'))
            base_url = service_info.url if service_info else 'http://localhost:3047'
        
        super().__init__(
            service_name='ROS Service',
            base_url=base_url
        )
    
    async def get_current_allocations(self) -> List[WaterAllocation]:
        """Get current water allocations for all zones"""
        try:
            response = await self.get('/api/v1/ros/allocations/current')
            
            allocations = []
            for alloc_data in response.get('allocations', []):
                allocations.append(WaterAllocation(**alloc_data))
            
            logger.info(f"Retrieved {len(allocations)} current allocations from ROS")
            return allocations
            
        except Exception as e:
            logger.error(f"Failed to get current allocations: {e}")
            raise
    
    async def get_zone_allocation(self, zone_id: str) -> Optional[WaterAllocation]:
        """Get allocation for specific zone"""
        try:
            response = await self.get(f'/api/v1/ros/allocations/zones/{zone_id}')
            
            if response:
                return WaterAllocation(**response)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get allocation for zone {zone_id}: {e}")
            return None
    
    async def get_water_demands(
        self, 
        start_date: date, 
        end_date: date,
        zone_ids: Optional[List[str]] = None
    ) -> List[WaterDemand]:
        """Get water demand forecasts"""
        try:
            params = {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
            
            if zone_ids:
                params['zones'] = ','.join(zone_ids)
            
            response = await self.get('/api/v1/ros/demands/forecast', params=params)
            
            demands = []
            for demand_data in response.get('demands', []):
                demands.append(WaterDemand(**demand_data))
            
            return demands
            
        except Exception as e:
            logger.error(f"Failed to get water demands: {e}")
            return []
    
    async def get_irrigation_schedule(
        self, 
        date: Optional[date] = None,
        zone_id: Optional[str] = None
    ) -> List[IrrigationSchedule]:
        """Get irrigation schedules"""
        try:
            params = {}
            if date:
                params['date'] = date.isoformat()
            if zone_id:
                params['zone_id'] = zone_id
            
            response = await self.get('/api/v1/ros/schedules', params=params)
            
            schedules = []
            for sched_data in response.get('schedules', []):
                schedules.append(IrrigationSchedule(**sched_data))
            
            return schedules
            
        except Exception as e:
            logger.error(f"Failed to get irrigation schedules: {e}")
            return []
    
    async def report_delivery_status(
        self,
        zone_id: str,
        delivered_volume: float,
        actual_flow_rate: float,
        efficiency: float,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """Report water delivery status back to ROS"""
        try:
            data = {
                'zone_id': zone_id,
                'delivered_volume': delivered_volume,
                'actual_flow_rate': actual_flow_rate,
                'efficiency': efficiency,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'reported_by': 'gravity-optimizer'
            }
            
            await self.post('/api/v1/ros/delivery/report', data=data)
            logger.info(f"Reported delivery status for zone {zone_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to report delivery status: {e}")
            return False
    
    async def get_crop_coefficients(self, zone_ids: List[str]) -> Dict[str, float]:
        """Get current crop coefficients for zones"""
        try:
            response = await self.post(
                '/api/v1/ros/crops/coefficients',
                data={'zone_ids': zone_ids}
            )
            
            return response.get('coefficients', {})
            
        except Exception as e:
            logger.error(f"Failed to get crop coefficients: {e}")
            return {}
    
    async def request_schedule_adjustment(
        self,
        zone_id: str,
        reason: str,
        suggested_time: Optional[datetime] = None,
        suggested_flow_rate: Optional[float] = None
    ) -> Optional[str]:
        """Request schedule adjustment due to hydraulic constraints"""
        try:
            data = {
                'zone_id': zone_id,
                'reason': reason,
                'requested_by': 'gravity-optimizer',
                'hydraulic_constraint': True
            }
            
            if suggested_time:
                data['suggested_time'] = suggested_time.isoformat()
            if suggested_flow_rate:
                data['suggested_flow_rate'] = suggested_flow_rate
            
            response = await self.post('/api/v1/ros/schedules/adjust', data=data)
            
            request_id = response.get('request_id')
            if request_id:
                logger.info(f"Schedule adjustment requested for zone {zone_id}: {request_id}")
            
            return request_id
            
        except Exception as e:
            logger.error(f"Failed to request schedule adjustment: {e}")
            return None
    
    async def get_water_balance(self) -> Dict:
        """Get current water balance information"""
        try:
            response = await self.get('/api/v1/ros/water-balance/current')
            return response
            
        except Exception as e:
            logger.error(f"Failed to get water balance: {e}")
            return {}
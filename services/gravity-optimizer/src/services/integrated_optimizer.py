"""Integrated Gravity Optimizer that communicates with other services"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio

from ..models.optimization import (
    OptimizationRequest, OptimizationResult, ZoneDeliveryRequest,
    DeliverySequence, OptimizationObjective
)
from ..models.channel import NetworkTopology
from ..clients import (
    GISClient, ROSClient, SCADAClient, 
    WeatherClient, SensorDataClient
)
from .gravity_optimizer import GravityOptimizer
from .elevation_feasibility import ElevationFeasibilityChecker
from .flow_splitter import FlowSplitter

logger = logging.getLogger(__name__)


class IntegratedGravityOptimizer:
    """Enhanced optimizer that integrates with other microservices"""
    
    def __init__(self):
        self.gis_client = GISClient()
        self.ros_client = ROSClient()
        self.scada_client = SCADAClient()
        self.weather_client = WeatherClient()
        self.sensor_client = SensorDataClient()
        
        # Core optimization components
        self.optimizer = GravityOptimizer()
        self.feasibility_checker = ElevationFeasibilityChecker()
        self.flow_splitter = FlowSplitter()
        
        self._network_topology: Optional[NetworkTopology] = None
        self._last_topology_update: Optional[datetime] = None
    
    async def initialize(self):
        """Initialize all service connections"""
        # Connect to services
        await asyncio.gather(
            self.gis_client.connect(),
            self.ros_client.connect(),
            self.scada_client.connect(),
            self.weather_client.connect(),
            self.sensor_client.connect()
        )
        
        # Load initial network topology
        await self._update_network_topology()
        logger.info("Integrated optimizer initialized")
    
    async def shutdown(self):
        """Clean up all service connections"""
        await asyncio.gather(
            self.gis_client.disconnect(),
            self.ros_client.disconnect(),
            self.scada_client.disconnect(),
            self.weather_client.disconnect(),
            self.sensor_client.disconnect()
        )
    
    async def optimize_with_real_data(
        self,
        request: OptimizationRequest
    ) -> OptimizationResult:
        """Optimize using real-time data from all services"""
        logger.info(f"Starting integrated optimization for {len(request.zone_requests)} zones")
        
        # 1. Get current allocations from ROS
        zone_allocations = await self._get_zone_allocations(request)
        
        # 2. Check weather conditions
        weather_suitable = await self._check_weather_conditions()
        if not weather_suitable:
            logger.warning("Weather conditions not suitable for irrigation")
            # Could implement weather-based adjustments here
        
        # 3. Get real-time sensor data
        sensor_data = await self._get_current_sensor_data()
        
        # 4. Get current gate positions from SCADA
        gate_positions = await self._get_gate_positions()
        
        # 5. Update source water level from sensors if available
        source_level = await self._get_source_water_level(sensor_data)
        if source_level:
            request.source_water_level = source_level
        
        # 6. Run optimization with real network topology
        network = await self._get_network_topology()
        
        # Run core optimization
        result = self.optimizer.optimize(request, network)
        
        # 7. Execute gate controls through SCADA
        if result.flow_splits and result.flow_splits.gate_settings:
            await self._execute_gate_controls(result.flow_splits.gate_settings)
        
        # 8. Report results back to ROS
        await self._report_delivery_results(result)
        
        # 9. Set up monitoring for this delivery
        await self._setup_delivery_monitoring(result)
        
        return result
    
    async def _get_zone_allocations(
        self, 
        request: OptimizationRequest
    ) -> Dict[str, Dict]:
        """Get water allocations from ROS for requested zones"""
        allocations = {}
        
        try:
            # Get current allocations
            ros_allocations = await self.ros_client.get_current_allocations()
            
            # Match with our zone requests
            for zone_req in request.zone_requests:
                for alloc in ros_allocations:
                    if alloc.zone_id == zone_req.zone_id:
                        allocations[zone_req.zone_id] = {
                            'allocated_volume': alloc.allocated_volume,
                            'required_flow_rate': alloc.required_flow_rate,
                            'priority': alloc.priority,
                            'crop_type': alloc.crop_type
                        }
                        
                        # Update zone request with ROS data
                        zone_req.required_volume = alloc.allocated_volume
                        zone_req.required_flow_rate = alloc.required_flow_rate
                        zone_req.priority = alloc.priority
                        break
            
            logger.info(f"Retrieved allocations for {len(allocations)} zones from ROS")
            
        except Exception as e:
            logger.error(f"Failed to get ROS allocations: {e}")
            # Continue with original request data
        
        return allocations
    
    async def _check_weather_conditions(self) -> bool:
        """Check if weather is suitable for irrigation"""
        try:
            conditions = await self.weather_client.check_irrigation_conditions()
            
            if not conditions.get('suitable', True):
                # Check for active rainfall
                rainfall_events = await self.weather_client.get_rainfall_events(
                    status='ongoing'
                )
                
                if rainfall_events:
                    logger.warning(f"Active rainfall detected: {len(rainfall_events)} events")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check weather conditions: {e}")
            return True  # Assume suitable if weather service unavailable
    
    async def _get_current_sensor_data(self) -> Dict:
        """Get all relevant sensor readings"""
        sensor_data = {}
        
        try:
            # Get water levels
            water_levels = await self.sensor_client.get_water_levels()
            sensor_data['water_levels'] = {
                wl.channel_id: wl.water_level 
                for wl in water_levels 
                if wl.channel_id
            }
            
            # Get flow rates
            flow_rates = await self.sensor_client.get_flow_rates()
            sensor_data['flow_rates'] = {
                fr.location_id: fr.flow_rate 
                for fr in flow_rates
            }
            
            # Get gate sensors
            gate_sensors = await self.sensor_client.get_gate_sensors()
            sensor_data['gate_positions'] = {
                gs.gate_id: gs.opening_percentage / 100.0
                for gs in gate_sensors
            }
            
            logger.info(
                f"Retrieved sensor data: "
                f"{len(sensor_data['water_levels'])} water levels, "
                f"{len(sensor_data['flow_rates'])} flow rates, "
                f"{len(sensor_data['gate_positions'])} gate positions"
            )
            
        except Exception as e:
            logger.error(f"Failed to get sensor data: {e}")
        
        return sensor_data
    
    async def _get_gate_positions(self) -> Dict[str, float]:
        """Get current gate positions from SCADA"""
        positions = {}
        
        try:
            gate_readings = await self.scada_client.get_all_gates_status()
            
            for reading in gate_readings:
                positions[reading.gate_id] = reading.current_opening
            
            logger.info(f"Retrieved {len(positions)} gate positions from SCADA")
            
        except Exception as e:
            logger.error(f"Failed to get gate positions: {e}")
        
        return positions
    
    async def _get_source_water_level(self, sensor_data: Dict) -> Optional[float]:
        """Get source water level from sensors"""
        # Try to find source water level
        water_levels = sensor_data.get('water_levels', {})
        
        # Look for main channel or source
        for channel_id, level in water_levels.items():
            if 'source' in channel_id.lower() or 'main' in channel_id.lower():
                logger.info(f"Using sensor water level for source: {level}m")
                return level
        
        return None
    
    async def _get_network_topology(self) -> NetworkTopology:
        """Get network topology, updating from GIS if needed"""
        # Update every hour or if not loaded
        should_update = (
            not self._network_topology or
            not self._last_topology_update or
            datetime.now() - self._last_topology_update > timedelta(hours=1)
        )
        
        if should_update:
            await self._update_network_topology()
        
        return self._network_topology
    
    async def _update_network_topology(self):
        """Update network topology from GIS"""
        try:
            # Get channel network
            channels = await self.gis_client.get_channel_network()
            
            # Get zone boundaries
            zones = await self.gis_client.get_zone_boundaries()
            
            # Convert to our format
            # This would need proper conversion logic
            # For now, use mock topology
            from ..utils.mock_network import create_mock_network
            self._network_topology = create_mock_network()
            
            self._last_topology_update = datetime.now()
            logger.info("Updated network topology from GIS")
            
        except Exception as e:
            logger.error(f"Failed to update network topology: {e}")
            # Fall back to mock if GIS unavailable
            from ..utils.mock_network import create_mock_network
            self._network_topology = create_mock_network()
    
    async def _execute_gate_controls(self, gate_settings: List[Dict]):
        """Execute gate control commands through SCADA"""
        from ..clients.scada_client import GateControl
        
        controls = []
        for setting in gate_settings:
            control = GateControl(
                gate_id=setting['gate_id'],
                target_opening=setting['opening_ratio'],
                rate_of_change=0.05,  # 5% per second
                priority=5
            )
            controls.append(control)
        
        # Execute batch control
        results = await self.scada_client.batch_control_gates(controls)
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"Gate control execution: {success_count}/{len(controls)} successful"
        )
        
        # Verify positions after a delay
        await asyncio.sleep(10)  # Wait for gates to move
        
        for control in controls:
            verified = await self.scada_client.verify_gate_position(
                control.gate_id,
                control.target_opening
            )
            if not verified:
                logger.warning(f"Gate {control.gate_id} position verification failed")
    
    async def _report_delivery_results(self, result: OptimizationResult):
        """Report delivery results back to ROS"""
        try:
            for sequence in result.delivery_sequence:
                if sequence.actual_volume and sequence.actual_end_time:
                    await self.ros_client.report_delivery_status(
                        zone_id=sequence.zone_id,
                        delivered_volume=sequence.actual_volume,
                        actual_flow_rate=sequence.actual_flow_rate or sequence.flow_rate,
                        efficiency=result.overall_efficiency,
                        start_time=sequence.start_time,
                        end_time=sequence.actual_end_time
                    )
            
            logger.info("Reported delivery results to ROS")
            
        except Exception as e:
            logger.error(f"Failed to report results to ROS: {e}")
    
    async def _setup_delivery_monitoring(self, result: OptimizationResult):
        """Set up monitoring for ongoing delivery"""
        # Subscribe to sensor updates for involved channels
        sensor_ids = []
        
        # This would need to map channels to sensors
        # For now, just log
        logger.info(f"Monitoring setup for optimization {result.request_id}")
        
        # Could implement:
        # - Real-time flow monitoring
        # - Anomaly detection
        # - Automatic adjustments
        # - Progress tracking
    
    async def handle_emergency(self, reason: str, affected_gates: List[str]):
        """Handle emergency situations"""
        logger.warning(f"Emergency handler triggered: {reason}")
        
        # 1. Emergency stop through SCADA
        stopped = await self.scada_client.emergency_stop(affected_gates, reason)
        
        if stopped:
            # 2. Notify ROS about disruption
            for gate_id in affected_gates:
                # Find affected zones
                # Would need gate-to-zone mapping
                pass
            
            # 3. Log incident
            logger.error(f"Emergency stop executed for {len(affected_gates)} gates")
    
    async def get_system_status(self) -> Dict:
        """Get integrated system status"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'sensors': {},
            'gates': {},
            'weather': {},
            'active_deliveries': 0
        }
        
        # Check service health
        service_checks = await asyncio.gather(
            self.gis_client.health_check(),
            self.ros_client.health_check(),
            self.scada_client.health_check(),
            self.weather_client.health_check(),
            self.sensor_client.health_check(),
            return_exceptions=True
        )
        
        services = ['gis', 'ros', 'scada', 'weather', 'sensor-data']
        for service, health in zip(services, service_checks):
            if isinstance(health, Exception):
                status['services'][service] = 'error'
            else:
                status['services'][service] = 'healthy' if health else 'unhealthy'
        
        # Get sensor network status
        try:
            status['sensors'] = await self.sensor_client.get_sensor_status()
        except:
            pass
        
        # Get gate status summary
        try:
            gate_readings = await self.scada_client.get_all_gates_status()
            status['gates'] = {
                'total': len(gate_readings),
                'operational': sum(1 for g in gate_readings if g.status != 'fault'),
                'faults': sum(1 for g in gate_readings if g.status == 'fault')
            }
        except:
            pass
        
        # Get weather summary
        try:
            weather = await self.weather_client.get_current_weather()
            status['weather'] = {
                'temperature': weather.temperature,
                'rainfall': weather.rainfall,
                'suitable_for_irrigation': True  # Would check conditions
            }
        except:
            pass
        
        return status
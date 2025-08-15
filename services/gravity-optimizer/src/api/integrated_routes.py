"""API routes for integrated optimization with other services"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from ..models.optimization import OptimizationRequest, OptimizationResult
from ..services.integrated_optimizer import IntegratedGravityOptimizer
from ..config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{settings.api_prefix}/integrated",
    tags=["integrated-optimization"]
)

# Global instance (in production, use dependency injection)
integrated_optimizer = IntegratedGravityOptimizer()


class ServiceHealthResponse(BaseModel):
    """Service health status"""
    service: str
    status: str
    last_check: datetime
    details: Optional[Dict] = None


class SystemStatusResponse(BaseModel):
    """System-wide status"""
    timestamp: datetime
    services: Dict[str, str]
    sensors: Dict
    gates: Dict
    weather: Dict
    active_deliveries: int


class RealTimeOptimizationRequest(BaseModel):
    """Request for real-time optimization"""
    use_ros_allocations: bool = True
    check_weather: bool = True
    auto_execute_gates: bool = False
    monitor_delivery: bool = True


@router.on_event("startup")
async def startup_event():
    """Initialize integrated optimizer on startup"""
    try:
        await integrated_optimizer.initialize()
        logger.info("Integrated optimizer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize integrated optimizer: {e}")


@router.on_event("shutdown") 
async def shutdown_event():
    """Clean up on shutdown"""
    try:
        await integrated_optimizer.shutdown()
        logger.info("Integrated optimizer shutdown complete")
    except Exception as e:
        logger.error(f"Error during integrated optimizer shutdown: {e}")


@router.get("/health", response_model=List[ServiceHealthResponse])
async def check_services_health():
    """Check health of all integrated services"""
    services = [
        ('GIS', integrated_optimizer.gis_client),
        ('ROS', integrated_optimizer.ros_client),
        ('SCADA', integrated_optimizer.scada_client),
        ('Weather', integrated_optimizer.weather_client),
        ('Sensor Data', integrated_optimizer.sensor_client)
    ]
    
    health_status = []
    
    for service_name, client in services:
        try:
            is_healthy = await client.health_check()
            status = 'healthy' if is_healthy else 'unhealthy'
        except Exception as e:
            status = 'error'
            logger.error(f"{service_name} health check failed: {e}")
        
        health_status.append(ServiceHealthResponse(
            service=service_name,
            status=status,
            last_check=datetime.now()
        ))
    
    return health_status


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get comprehensive system status"""
    try:
        status = await integrated_optimizer.get_system_status()
        return SystemStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


@router.post("/optimize/realtime", response_model=OptimizationResult)
async def optimize_with_realtime_data(
    request: OptimizationRequest,
    options: RealTimeOptimizationRequest = RealTimeOptimizationRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Run optimization using real-time data from all integrated services
    
    This endpoint:
    1. Fetches current water allocations from ROS
    2. Checks weather conditions
    3. Gets real-time sensor readings
    4. Retrieves current gate positions from SCADA
    5. Runs optimization with actual network topology from GIS
    6. Optionally executes gate controls automatically
    7. Reports results back to ROS
    8. Sets up monitoring for the delivery
    """
    try:
        # Validate request
        if not request.zone_requests:
            raise HTTPException(status_code=400, detail="No zones specified")
        
        # Check if weather conditions are suitable
        if options.check_weather:
            weather_ok = await integrated_optimizer._check_weather_conditions()
            if not weather_ok:
                logger.warning("Weather conditions not suitable, but proceeding with optimization")
        
        # Run integrated optimization
        result = await integrated_optimizer.optimize_with_real_data(request)
        
        # Set up background monitoring if requested
        if options.monitor_delivery:
            background_tasks.add_task(
                monitor_delivery_progress,
                result.request_id,
                result.delivery_sequence
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Integrated optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensors/current")
async def get_current_sensor_readings():
    """Get current sensor readings relevant to optimization"""
    try:
        sensor_data = await integrated_optimizer._get_current_sensor_data()
        return sensor_data
    except Exception as e:
        logger.error(f"Failed to get sensor data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sensor data")


@router.get("/gates/positions")
async def get_gate_positions():
    """Get current gate positions from SCADA"""
    try:
        positions = await integrated_optimizer._get_gate_positions()
        return {"gates": positions, "timestamp": datetime.now()}
    except Exception as e:
        logger.error(f"Failed to get gate positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve gate positions")


@router.post("/gates/control")
async def control_gates(gate_settings: List[Dict]):
    """Manually control gates through SCADA"""
    try:
        await integrated_optimizer._execute_gate_controls(gate_settings)
        return {"status": "success", "gates_controlled": len(gate_settings)}
    except Exception as e:
        logger.error(f"Failed to control gates: {e}")
        raise HTTPException(status_code=500, detail="Failed to control gates")


@router.post("/emergency/stop")
async def emergency_stop(
    reason: str = Query(..., description="Reason for emergency stop"),
    gates: List[str] = Query(..., description="List of gate IDs to stop")
):
    """Execute emergency stop for specified gates"""
    try:
        await integrated_optimizer.handle_emergency(reason, gates)
        return {
            "status": "executed",
            "reason": reason,
            "affected_gates": gates,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(status_code=500, detail="Emergency stop failed")


@router.get("/network/topology")
async def get_network_topology():
    """Get current network topology from GIS"""
    try:
        topology = await integrated_optimizer._get_network_topology()
        return {
            "nodes": len(topology.nodes),
            "channels": len(topology.channels),
            "gates": len(topology.gates),
            "last_updated": integrated_optimizer._last_topology_update
        }
    except Exception as e:
        logger.error(f"Failed to get network topology: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve network topology")


@router.post("/sync/allocations")
async def sync_with_ros():
    """Synchronize with ROS for latest water allocations"""
    try:
        allocations = await integrated_optimizer.ros_client.get_current_allocations()
        return {
            "status": "synced",
            "allocations_count": len(allocations),
            "zones": [a.zone_id for a in allocations],
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to sync with ROS: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync allocations")


async def monitor_delivery_progress(request_id: str, delivery_sequence: List):
    """Background task to monitor delivery progress"""
    logger.info(f"Starting delivery monitoring for request {request_id}")
    
    # This would implement real-time monitoring logic
    # For example:
    # - Check flow rates against targets
    # - Detect anomalies
    # - Adjust gates if needed
    # - Report progress to ROS
    
    # Simplified version - just log
    await asyncio.sleep(60)  # Check every minute
    logger.info(f"Delivery monitoring complete for request {request_id}")
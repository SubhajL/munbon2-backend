from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime
from ..models.optimization import (
    ZoneDeliveryRequest, OptimizationResult, OptimizationObjective,
    ElevationFeasibility, DepthRequirement, FlowSplitOptimization,
    EnergyRecoveryPotential, ContingencyPlan
)
from ..models.channel import NetworkTopology
from ..services.gravity_optimizer import GravityOptimizer
from ..services.elevation_feasibility import ElevationFeasibilityChecker
from ..services.minimum_depth_calculator import MinimumDepthCalculator
from ..services.flow_splitter import FlowSplitter
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.api_prefix, tags=["gravity-optimizer"])

# Import integrated routes
from .integrated_routes import router as integrated_router

# Placeholder for dependency injection
async def get_network_topology() -> NetworkTopology:
    """Get current network topology from database or cache"""
    # TODO: Implement actual network loading from PostGIS
    # For now, return a mock network
    from ..utils.mock_network import create_mock_network
    return create_mock_network()


async def get_optimizer(network: NetworkTopology = Depends(get_network_topology)) -> GravityOptimizer:
    """Get gravity optimizer instance"""
    return GravityOptimizer(network)


@router.post("/optimize", response_model=OptimizationResult)
async def optimize_delivery(
    zone_requests: List[ZoneDeliveryRequest],
    source_water_level: Optional[float] = Query(None, description="Source water level in MSL meters"),
    objective: OptimizationObjective = Query(OptimizationObjective.BALANCED),
    include_contingency: bool = Query(True, description="Generate contingency plans"),
    include_energy_recovery: bool = Query(True, description="Analyze energy recovery potential"),
    optimizer: GravityOptimizer = Depends(get_optimizer)
):
    """
    Perform complete gravity flow optimization for water delivery
    
    This endpoint:
    1. Checks elevation feasibility for all zones
    2. Calculates minimum depth requirements
    3. Optimizes flow distribution through automated gates
    4. Generates optimal delivery sequence
    5. Identifies energy recovery opportunities
    6. Creates contingency plans for common failures
    """
    try:
        result = await optimizer.optimize_delivery(
            zone_requests=zone_requests,
            source_water_level=source_water_level,
            objective=objective,
            include_contingency=include_contingency,
            include_energy_recovery=include_energy_recovery
        )
        
        logger.info(
            f"Optimization completed: {len(zone_requests)} zones, "
            f"efficiency: {result.overall_efficiency:.1%}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feasibility/check", response_model=List[ElevationFeasibility])
async def check_feasibility(
    zone_requests: List[ZoneDeliveryRequest],
    source_water_level: Optional[float] = Query(None),
    network: NetworkTopology = Depends(get_network_topology)
):
    """
    Check elevation feasibility for water delivery to specified zones
    
    Returns detailed feasibility analysis including:
    - Whether gravity delivery is possible
    - Minimum required source water level
    - Critical channel sections
    - Recommended flow rates
    """
    checker = ElevationFeasibilityChecker(network)
    results = checker.check_all_zones_feasibility(zone_requests, source_water_level)
    
    feasible_count = sum(1 for r in results if r.is_feasible)
    logger.info(f"Feasibility check: {feasible_count}/{len(results)} zones feasible")
    
    return results


@router.get("/feasibility/{zone_id}", response_model=ElevationFeasibility)
async def check_zone_feasibility(
    zone_id: str,
    required_flow: float = Query(..., description="Required flow rate in m³/s"),
    source_water_level: Optional[float] = Query(None),
    network: NetworkTopology = Depends(get_network_topology)
):
    """Check feasibility for a specific zone"""
    checker = ElevationFeasibilityChecker(network)
    
    # Get zone elevation
    zone_key = zone_id.lower().replace("-", "_")
    if zone_key not in settings.zone_elevations:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    
    zone_elevation = settings.zone_elevations[zone_key]["min"]
    
    result = checker.check_zone_feasibility(
        zone_id=zone_id,
        zone_elevation=zone_elevation,
        required_flow=required_flow,
        source_water_level=source_water_level
    )
    
    return result


@router.post("/depth/calculate")
async def calculate_minimum_depths(
    channel_id: str,
    flow_rate: float = Query(..., description="Design flow rate in m³/s"),
    network: NetworkTopology = Depends(get_network_topology)
):
    """
    Calculate minimum depth requirements for a channel
    
    Returns depth requirements including:
    - Hydraulic minimum depth
    - Sediment transport minimum
    - Operational minimum
    - Critical depth
    - Flow regime classification
    """
    calculator = MinimumDepthCalculator()
    
    # Find channel
    channel = next((c for c in network.channels if c.channel_id == channel_id), None)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    
    requirements = calculator.calculate_channel_requirements(
        channel=channel,
        flow_rate=flow_rate,
        check_transitions=True
    )
    
    return requirements


@router.post("/flow-split/optimize", response_model=FlowSplitOptimization)
async def optimize_flow_split(
    total_inflow: float,
    zone_requests: List[ZoneDeliveryRequest],
    objective: OptimizationObjective = Query(OptimizationObjective.BALANCED),
    network: NetworkTopology = Depends(get_network_topology)
):
    """
    Optimize flow distribution through automated gates
    
    Returns optimal gate settings to achieve desired zone flows
    """
    splitter = FlowSplitter(network)
    
    result = splitter.optimize_flow_split(
        total_inflow=total_inflow,
        zone_requests=zone_requests,
        objective=objective
    )
    
    return result


@router.get("/energy-recovery/potential", response_model=List[EnergyRecoveryPotential])
async def get_energy_recovery_potential(
    min_power_kw: float = Query(50, description="Minimum power threshold in kW"),
    optimizer: GravityOptimizer = Depends(get_optimizer)
):
    """
    Identify locations with micro-hydro energy recovery potential
    
    Returns sites with significant elevation drops suitable for power generation
    """
    sites = await optimizer._analyze_energy_recovery()
    
    # Filter by minimum power
    filtered_sites = [s for s in sites if s.potential_power >= min_power_kw]
    
    logger.info(f"Found {len(filtered_sites)} energy recovery sites >= {min_power_kw} kW")
    
    return filtered_sites


@router.get("/contingency/plans", response_model=List[ContingencyPlan])
async def get_contingency_plans(
    scenario: Optional[str] = Query(None, description="Specific scenario to plan for"),
    optimizer: GravityOptimizer = Depends(get_optimizer)
):
    """
    Get contingency plans for common failure scenarios
    
    Scenarios include:
    - main_channel_blockage
    - gate_failure_[gate_id]
    - low_water_level
    """
    # Create dummy zone requests for planning
    zone_requests = [
        ZoneDeliveryRequest(
            zone_id=f"zone_{i}",
            required_volume=10000,
            required_flow_rate=20,
            priority=1
        )
        for i in range(1, 7)
    ]
    
    # Generate nominal flow splits
    flow_splits = await optimizer._optimize_flow_splits(
        total_inflow=120,
        zone_requests=zone_requests,
        objective=OptimizationObjective.BALANCED
    )
    
    # Generate contingency plans
    plans = await optimizer._generate_contingency_plans(zone_requests, flow_splits)
    
    # Filter by scenario if specified
    if scenario:
        plans = [p for p in plans if scenario in p.plan_id]
    
    return plans


@router.get("/status")
async def get_optimizer_status():
    """Get current optimizer service status"""
    return {
        "service": settings.service_name,
        "version": settings.version,
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "automated_gates": settings.automated_gates_count,
            "min_flow_depth": settings.min_flow_depth,
            "source_elevation": settings.source_elevation,
            "zones_configured": len(settings.zone_elevations)
        }
    }


@router.get("/zones")
async def get_configured_zones():
    """Get all configured zones with elevation data"""
    zones = []
    for zone_key, elevations in settings.zone_elevations.items():
        zone_id = zone_key.replace("_", "-")
        zones.append({
            "zone_id": zone_id,
            "min_elevation": elevations["min"],
            "max_elevation": elevations["max"],
            "elevation_range": elevations["max"] - elevations["min"]
        })
    
    return sorted(zones, key=lambda x: x["min_elevation"], reverse=True)


# Include integrated routes
router.include_router(integrated_router)
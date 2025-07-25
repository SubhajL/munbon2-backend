"""
Gravity Flow Optimizer Service
Optimizes water delivery using only gravity in the Munbon irrigation system
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import sys

from models import (
    GravityOptimizationRequest,
    GravityOptimizationResponse,
    EnergyProfileResponse,
    FeasibilityCheckRequest,
    FeasibilityCheckResponse,
    FrictionLossResponse,
    HealthResponse
)
from hydraulic_engine import HydraulicEngine
from optimization_engine import OptimizationEngine
from feasibility_checker import FeasibilityChecker
from energy_calculator import EnergyCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize engines
hydraulic_engine = HydraulicEngine()
optimization_engine = OptimizationEngine()
feasibility_checker = FeasibilityChecker()
energy_calculator = EnergyCalculator()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Gravity Flow Optimizer Service on port 3025")
    yield
    logger.info("Shutting down Gravity Flow Optimizer Service")

app = FastAPI(
    title="Gravity Flow Optimizer",
    description="Optimizes water delivery using gravity-fed system constraints",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="gravity-optimizer",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )

@app.post("/api/v1/gravity/optimize-flow", response_model=GravityOptimizationResponse)
async def optimize_gravity_flow(request: GravityOptimizationRequest):
    """
    Optimize water flow using gravity constraints
    - Maximizes delivery reach while minimizing losses
    - Considers elevation differences and friction losses
    - Optimizes gate sequencing for energy conservation
    """
    try:
        logger.info(f"Optimizing gravity flow for {len(request.target_deliveries)} deliveries")
        
        # Check feasibility first
        feasibility_results = await feasibility_checker.check_all_deliveries(
            request.target_deliveries,
            request.source_elevation,
            request.constraints
        )
        
        if not feasibility_results.all_feasible:
            logger.warning(f"Not all deliveries feasible: {feasibility_results.infeasible_sections}")
        
        # Calculate optimal gate settings
        optimization_result = await optimization_engine.optimize_flow(
            request.target_deliveries,
            request.current_gate_states,
            feasibility_results,
            request.constraints
        )
        
        # Calculate energy profiles
        energy_profiles = await energy_calculator.calculate_profiles(
            optimization_result.gate_settings,
            request.network_topology
        )
        
        return GravityOptimizationResponse(
            optimal_gate_settings=optimization_result.gate_settings,
            energy_profiles=energy_profiles,
            total_head_loss=optimization_result.total_head_loss,
            delivery_times=optimization_result.delivery_times,
            feasibility_warnings=feasibility_results.warnings,
            optimization_metrics={
                "iterations": optimization_result.iterations,
                "convergence_error": optimization_result.convergence_error,
                "computation_time_ms": optimization_result.computation_time_ms
            }
        )
        
    except Exception as e:
        logger.error(f"Optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/gravity/energy-profile/{path}", response_model=EnergyProfileResponse)
async def get_energy_profile(path: str):
    """
    Get hydraulic grade line and energy profile for a specific path
    Shows elevation, pressure head, velocity head, and total energy
    """
    try:
        logger.info(f"Calculating energy profile for path: {path}")
        
        # Parse path (e.g., "Source->M(0,0)->M(0,2)->Zone_2")
        nodes = path.split("->")
        
        # Get current hydraulic state
        current_state = await hydraulic_engine.get_current_state(nodes)
        
        # Calculate energy profile
        profile = await energy_calculator.calculate_path_profile(
            nodes,
            current_state
        )
        
        return EnergyProfileResponse(
            path=path,
            nodes=nodes,
            energy_profile=profile.energy_points,
            hydraulic_grade_line=profile.hgl_points,
            total_head_loss=profile.total_head_loss,
            critical_points=profile.critical_points,
            minimum_pressure_head=profile.min_pressure_head
        )
        
    except Exception as e:
        logger.error(f"Energy profile calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/gravity/verify-feasibility", response_model=FeasibilityCheckResponse)
async def verify_feasibility(request: FeasibilityCheckRequest):
    """
    Verify if water can reach target sections by gravity alone
    Considers elevation differences, friction losses, and minimum depths
    """
    try:
        logger.info(f"Verifying feasibility for section {request.target_section}")
        
        # Check elevation feasibility
        elevation_check = await feasibility_checker.check_elevation_feasibility(
            request.source_node,
            request.target_section,
            request.required_flow_m3s
        )
        
        # Check minimum depth requirements
        depth_check = await feasibility_checker.check_minimum_depths(
            request.path_nodes,
            request.required_flow_m3s
        )
        
        # Calculate required upstream level
        required_level = await hydraulic_engine.calculate_required_upstream_level(
            request.target_section,
            request.target_elevation,
            request.required_flow_m3s,
            request.path_nodes
        )
        
        return FeasibilityCheckResponse(
            feasible=elevation_check.feasible and depth_check.feasible,
            required_upstream_level=required_level,
            available_head=elevation_check.available_head,
            total_losses=elevation_check.total_losses,
            minimum_depths_met=depth_check.all_depths_met,
            critical_sections=depth_check.critical_sections,
            recommendations=feasibility_checker.get_recommendations(
                elevation_check,
                depth_check
            )
        )
        
    except Exception as e:
        logger.error(f"Feasibility check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/gravity/friction-losses/{canal_id}", response_model=FrictionLossResponse)
async def get_friction_losses(canal_id: str, flow_m3s: float = None):
    """
    Calculate friction losses for a specific canal section
    Uses Manning's equation with canal characteristics
    """
    try:
        logger.info(f"Calculating friction losses for canal: {canal_id}")
        
        # Get canal characteristics
        canal_data = await hydraulic_engine.get_canal_characteristics(canal_id)
        
        # Use provided flow or current flow
        if flow_m3s is None:
            flow_m3s = canal_data.current_flow_m3s
        
        # Calculate losses
        losses = await hydraulic_engine.calculate_friction_loss(
            canal_id,
            flow_m3s,
            canal_data
        )
        
        return FrictionLossResponse(
            canal_id=canal_id,
            flow_m3s=flow_m3s,
            friction_loss_m=losses.friction_loss,
            friction_slope=losses.friction_slope,
            velocity_ms=losses.velocity,
            hydraulic_radius_m=losses.hydraulic_radius,
            reynolds_number=losses.reynolds_number,
            flow_regime=losses.flow_regime,
            manning_n=canal_data.manning_n,
            length_m=canal_data.length_m
        )
        
    except Exception as e:
        logger.error(f"Friction loss calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/gravity/optimization-status")
async def get_optimization_status():
    """Get current optimization engine status and metrics"""
    return {
        "engine_status": "operational",
        "active_optimizations": optimization_engine.get_active_count(),
        "completed_today": optimization_engine.get_daily_stats(),
        "average_computation_time_ms": optimization_engine.get_avg_computation_time(),
        "cache_hit_rate": optimization_engine.get_cache_hit_rate()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3025)
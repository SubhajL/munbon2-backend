"""
Enhanced Gravity Flow Optimizer Service with additional endpoints
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict
import logging
import sys

from models import *
from hydraulic_engine import HydraulicEngine
from optimization_engine import OptimizationEngine
from feasibility_checker import FeasibilityChecker
from energy_calculator import EnergyCalculator
from micro_hydro_analyzer import MicroHydroAnalyzer
from travel_time_predictor import TravelTimePredictor
from sequencing_optimizer import SequencingOptimizer, ZoneDeliveryRequest
from contingency_router import ContingencyRouter, Blockage, BlockageType

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
micro_hydro_analyzer = MicroHydroAnalyzer()
travel_time_predictor = TravelTimePredictor()
sequencing_optimizer = SequencingOptimizer()
contingency_router = ContingencyRouter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Enhanced Gravity Flow Optimizer Service on port 3025")
    yield
    logger.info("Shutting down Gravity Flow Optimizer Service")

app = FastAPI(
    title="Gravity Flow Optimizer (Enhanced)",
    description="Advanced gravity-fed water delivery optimization with contingency planning",
    version="2.0.0",
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

# Include all original endpoints from main.py
# (Health, optimize-flow, energy-profile, verify-feasibility, friction-losses)

@app.post("/api/v1/gravity/sequence-deliveries")
async def sequence_deliveries(request: Dict[str, any]):
    """
    Optimize delivery sequence for multiple zones
    Minimizes water residence time and maximizes efficiency
    """
    try:
        # Convert request to delivery objects
        delivery_requests = []
        for zone_data in request.get("zones", []):
            req = ZoneDeliveryRequest(
                zone_id=zone_data["zone_id"],
                volume_m3=zone_data["volume_m3"],
                priority=zone_data.get("priority", 5),
                deadline=datetime.fromisoformat(zone_data["deadline"]),
                min_flow_m3s=zone_data.get("min_flow_m3s", 0.5),
                max_flow_m3s=zone_data.get("max_flow_m3s", 3.0)
            )
            delivery_requests.append(req)
        
        # Optimize sequence
        optimal_sequence = sequencing_optimizer.optimize_delivery_sequence(
            delivery_requests,
            request.get("constraints", {})
        )
        
        return {
            "optimal_sequence": optimal_sequence.sequence,
            "total_time_hours": optimal_sequence.total_time_hours,
            "total_volume_m3": optimal_sequence.total_volume_m3,
            "avg_residence_time_hours": optimal_sequence.avg_residence_time_hours,
            "efficiency_score": optimal_sequence.efficiency_score,
            "gate_operations": optimal_sequence.gate_operations
        }
        
    except Exception as e:
        logger.error(f"Sequencing optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/gravity/travel-time")
async def predict_travel_time(request: Dict[str, any]):
    """
    Predict water travel times to different zones
    """
    try:
        gate_settings = request.get("gate_settings", {})
        target_zones = request.get("target_zones", [])
        start_time = datetime.fromisoformat(request["start_time"]) if "start_time" in request else None
        
        predictions = travel_time_predictor.predict_delivery_times(
            gate_settings,
            target_zones,
            start_time
        )
        
        result = {}
        for zone, pred in predictions.items():
            result[zone] = {
                "path": pred.path,
                "total_distance_m": pred.total_distance_m,
                "travel_time_hours": pred.travel_time_hours,
                "arrival_time": pred.arrival_time.isoformat(),
                "confidence_level": pred.confidence_level,
                "segments": [
                    {
                        "segment_id": seg.segment_id,
                        "length_m": seg.length_m,
                        "velocity_ms": seg.velocity_ms,
                        "travel_time_s": seg.travel_time_s
                    }
                    for seg in pred.segments
                ]
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Travel time prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/gravity/micro-hydro-potential")
async def analyze_micro_hydro(request: Dict[str, any]):
    """
    Analyze micro-hydro potential at automated gates
    """
    try:
        gate_flows = request.get("gate_flows", {})
        automated_gates = request.get("automated_gates", [])
        
        potential_sites = micro_hydro_analyzer.analyze_network_potential(
            gate_flows,
            automated_gates
        )
        
        result = {
            "total_sites": len(potential_sites),
            "total_power_kW": sum(site.power_potential_kW for site in potential_sites.values()),
            "total_annual_energy_MWh": sum(site.annual_energy_MWh for site in potential_sites.values()),
            "total_co2_reduction_tons": sum(site.co2_reduction_tons for site in potential_sites.values()),
            "sites": {}
        }
        
        for gate_id, site in potential_sites.items():
            result["sites"][gate_id] = {
                "head_m": site.head_m,
                "flow_m3s": site.flow_m3s,
                "power_potential_kW": site.power_potential_kW,
                "annual_energy_MWh": site.annual_energy_MWh,
                "payback_years": site.payback_years,
                "co2_reduction_tons": site.co2_reduction_tons,
                "feasibility_score": site.feasibility_score,
                "turbine_recommendation": micro_hydro_analyzer.optimize_turbine_selection(
                    site.head_m,
                    site.flow_m3s
                )
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Micro-hydro analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/gravity/contingency-routes")
async def find_contingency_routes(request: Dict[str, any]):
    """
    Find alternative routes when primary paths are blocked
    """
    try:
        source = request.get("source", "Source")
        destination = request["destination"]
        required_flow_m3s = request["required_flow_m3s"]
        
        # Parse blockages
        blockages = []
        for block_data in request.get("blockages", []):
            blockage = Blockage(
                location=block_data["location"],
                type=BlockageType(block_data["type"]),
                severity=block_data["severity"],
                estimated_duration_hours=block_data["duration_hours"],
                affected_segments=block_data["affected_segments"]
            )
            blockages.append(blockage)
        
        # Find alternatives
        alternatives = contingency_router.find_alternative_routes(
            source,
            destination,
            blockages,
            required_flow_m3s
        )
        
        return {
            "alternatives_found": len(alternatives),
            "routes": [
                {
                    "route_id": alt.route_id,
                    "path": alt.path,
                    "total_length_m": alt.total_length_m,
                    "elevation_change_m": alt.elevation_change_m,
                    "capacity_m3s": alt.capacity_m3s,
                    "efficiency_ratio": alt.efficiency_ratio,
                    "feasibility_score": alt.feasibility_score,
                    "required_operations": alt.required_gate_operations
                }
                for alt in alternatives
            ]
        }
        
    except Exception as e:
        logger.error(f"Contingency routing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/gravity/blockage-impact")
async def simulate_blockage_impact(request: Dict[str, any]):
    """
    Simulate impact of blockages on current deliveries
    """
    try:
        # Parse blockages
        blockages = []
        for block_data in request.get("blockages", []):
            blockage = Blockage(
                location=block_data["location"],
                type=BlockageType(block_data["type"]),
                severity=block_data["severity"],
                estimated_duration_hours=block_data["duration_hours"],
                affected_segments=block_data["affected_segments"]
            )
            blockages.append(blockage)
        
        current_deliveries = request.get("current_deliveries", {})
        
        # Analyze impact
        impact_analysis = contingency_router.simulate_blockage_impact(
            blockages,
            current_deliveries
        )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "blockages_analyzed": len(blockages),
            "zones_affected": len(impact_analysis),
            "impact_details": impact_analysis
        }
        
    except Exception as e:
        logger.error(f"Impact simulation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/gravity/dry-startup-time/{zone}")
async def estimate_dry_startup_time(zone: str, initial_flow_m3s: float = 2.0):
    """
    Estimate time to deliver water through dry channels
    """
    try:
        path = contingency_router.primary_routes.get(zone, [])
        if not path:
            raise HTTPException(status_code=404, detail=f"No path found for {zone}")
        
        startup_time = travel_time_predictor.predict_dry_channel_startup_time(
            path,
            initial_flow_m3s
        )
        
        return {
            "zone": zone,
            "path": path,
            "initial_flow_m3s": initial_flow_m3s,
            "startup_time_hours": startup_time,
            "recommendations": [
                "Pre-wet channels if possible",
                "Start with higher initial flow to reduce filling time",
                "Monitor for excessive seepage in first 2 hours"
            ]
        }
        
    except Exception as e:
        logger.error(f"Dry startup estimation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/gravity/network-status")
async def get_network_status():
    """Get current network optimization status"""
    return {
        "service_status": "operational",
        "engines": {
            "hydraulic": "ready",
            "optimization": {
                "active_optimizations": optimization_engine.get_active_count(),
                "completed_today": optimization_engine.get_daily_stats(),
                "avg_computation_time_ms": optimization_engine.get_avg_computation_time()
            },
            "feasibility": "ready",
            "energy": "ready",
            "sequencing": "ready",
            "contingency": "ready"
        },
        "network_stats": {
            "total_zones": 6,
            "total_gates": 20,
            "automated_gates": 20,
            "cross_connections": len(contingency_router.cross_connections)
        },
        "elevation_range": {
            "source_m": 221.0,
            "lowest_zone_m": 215.5,
            "total_drop_m": 5.5
        }
    }

@app.get("/docs/visualization")
async def get_visualization_html():
    """Return HTML for network visualization"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gravity Flow Network</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .info { background: #f0f0f0; padding: 10px; margin: 10px 0; }
            .elevation { color: #0066cc; font-weight: bold; }
            .flow { color: #009900; }
            .warning { color: #ff6600; }
        </style>
    </head>
    <body>
        <h1>Munbon Gravity Flow Network</h1>
        <div class="info">
            <h2>Elevation Profile</h2>
            <p>Source: <span class="elevation">221.0m</span></p>
            <p>Zone 1: <span class="elevation">219.0m</span> (Δ 2.0m)</p>
            <p>Zone 2: <span class="elevation">217.5m</span> (Δ 3.5m)</p>
            <p>Zone 3: <span class="elevation">217.0m</span> (Δ 4.0m)</p>
            <p>Zone 4: <span class="elevation">216.5m</span> (Δ 4.5m)</p>
            <p>Zone 5: <span class="elevation">215.5m</span> (Δ 5.5m)</p>
            <p>Zone 6: <span class="elevation">215.5m</span> (Δ 5.5m)</p>
        </div>
        <div class="info">
            <h2>Gravity Optimization Features</h2>
            <ul>
                <li>Energy-efficient delivery sequencing</li>
                <li>Micro-hydro potential at 20 automated gates</li>
                <li>Real-time travel time prediction</li>
                <li>Contingency routing for blockages</li>
                <li>Minimum depth maintenance</li>
            </ul>
        </div>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3025)
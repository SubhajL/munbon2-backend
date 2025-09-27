"""
API routes for single section water delivery scenarios
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...core.database import get_db
from ...core.models import Scenario, SectionDemand
from ...core.schemas import ScenarioCreate, SimulationStatus
from ...scenarios.single_section_scenario import SingleSectionScenarioBuilder
from ...integrations.service_factory import get_service_clients
from ..dependencies import get_current_user


router = APIRouter(prefix="/single-section", tags=["single-section-scenarios"])


@router.post("/create-scenario")
async def create_single_section_scenario(
    section_id: str,
    water_depth_cm: float,
    scenario_name: Optional[str] = None,
    base_date: Optional[datetime] = None,
    duration_days: int = 7,
    set_others_to_zero: bool = True,
    zone_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Create a scenario for single section water delivery
    
    Args:
        section_id: Target section ID (e.g., "01-06-02-42")
        water_depth_cm: Required water depth in centimeters
        scenario_name: Optional custom name
        base_date: Simulation start date
        duration_days: Simulation duration
        set_others_to_zero: Set all other sections to zero demand
        zone_id: Limit zero demands to specific zone
    """
    # Get service clients
    clients = await get_service_clients()
    
    # Create scenario builder
    builder = SingleSectionScenarioBuilder(
        clients["gis_client"],
        clients["flow_client"]
    )
    
    try:
        # Build scenario configuration
        scenario_config = await builder.create_single_section_scenario(
            section_id=section_id,
            water_depth_cm=water_depth_cm,
            scenario_name=scenario_name,
            base_date=base_date,
            duration_days=duration_days
        )
        
        # Create scenario in database
        scenario = Scenario(
            name=scenario_config["scenario"]["name"],
            description=scenario_config["scenario"]["description"],
            base_date=scenario_config["scenario"]["base_date"],
            duration_days=scenario_config["scenario"]["duration_days"],
            time_step_minutes=scenario_config["scenario"]["time_step_minutes"],
            optimization_objective=scenario_config["scenario"]["optimization_objective"],
            created_by=current_user,
            metadata={
                "scenario_type": "single_section_delivery",
                "target_section": scenario_config["target_section"],
                "delivery_path": scenario_config["delivery_path"],
                "canal_volumes": scenario_config["canal_volumes"],
                "total_water_required_m3": scenario_config["total_water_required_m3"]
            }
        )
        
        db.add(scenario)
        await db.flush()
        
        # Add section demand for target section
        target_demand = scenario_config["section_demands"][0]
        demand = SectionDemand(
            scenario_id=scenario.scenario_id,
            section_id=target_demand["section_id"],
            week_number=target_demand["week_number"],
            base_demand_m3=target_demand["base_demand_m3"],
            priority_override=target_demand["priority_override"],
            delivery_window_hours=target_demand["delivery_window_hours"]
        )
        db.add(demand)
        
        # Set other sections to zero if requested
        if set_others_to_zero:
            zero_demands = await builder.create_zero_demand_overrides(
                scenario.scenario_id,
                section_id,
                zone_id
            )
            
            for zero_demand in zero_demands[:100]:  # Limit to prevent too many records
                demand = SectionDemand(
                    scenario_id=scenario.scenario_id,
                    section_id=zero_demand["section_id"],
                    week_number=zero_demand["week_number"],
                    base_demand_m3=0,
                    priority_override=0,
                    min_delivery_m3=0,
                    max_delivery_m3=0
                )
                db.add(demand)
        
        await db.commit()
        await db.refresh(scenario)
        
        # Return scenario with additional details
        return {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "target_section": scenario_config["target_section"],
            "delivery_path_length": len(scenario_config["delivery_path"]),
            "canal_fill_volume_m3": scenario_config["canal_volumes"]["total_volume_m3"],
            "section_water_volume_m3": scenario_config["target_section"]["water_volume_m3"],
            "total_water_required_m3": scenario_config["total_water_required_m3"],
            "estimated_travel_time_hours": scenario_config["canal_volumes"]["travel_time_hours"],
            "zero_demand_sections": len(zero_demands) if set_others_to_zero else 0
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # Cleanup clients
        for client in clients.values():
            await client.close()


@router.get("/analyze-delivery-path/{section_id}")
async def analyze_delivery_path(
    section_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze water delivery path for a section without creating scenario
    
    Returns path details, canal volumes, and travel time estimates
    """
    clients = await get_service_clients()
    
    builder = SingleSectionScenarioBuilder(
        clients["gis_client"],
        clients["flow_client"]
    )
    
    try:
        # Get section details
        section_info = await clients["gis_client"].get_section_details(section_id)
        
        # Trace delivery path
        delivery_path = await builder._trace_delivery_path(section_id)
        
        # Calculate canal volumes
        canal_volumes = await builder._calculate_canal_volumes(delivery_path)
        
        # Get gate details along path
        gates_in_path = []
        for segment in delivery_path:
            if segment["to"].startswith("GATE"):
                try:
                    gate_props = await clients["flow_client"].get_gate_properties(segment["to"])
                    gates_in_path.append({
                        "gate_id": segment["to"],
                        "shape": gate_props.get("shape"),
                        "max_opening_m": gate_props.get("max_opening_m", 2.0)
                    })
                except Exception:
                    gates_in_path.append({
                        "gate_id": segment["to"],
                        "shape": "unknown",
                        "max_opening_m": 2.0
                    })
        
        return {
            "section_id": section_id,
            "delivery_gate": section_info.get("delivery_gate"),
            "area_hectares": section_info.get("area_hectares"),
            "path_segments": delivery_path,
            "path_length": len(delivery_path),
            "total_distance_km": canal_volumes["total_distance_km"],
            "canal_fill_volume_m3": canal_volumes["total_volume_m3"],
            "travel_time_hours": canal_volumes["travel_time_hours"],
            "gates_in_path": gates_in_path,
            "canal_details": canal_volumes["canal_segments"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for client in clients.values():
            await client.close()


@router.post("/simulate-delivery")
async def simulate_single_section_delivery(
    scenario_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Run simulation for single section delivery scenario
    
    This will simulate:
    1. Initial canal filling along delivery path
    2. Gate operations to deliver water
    3. Water travel time to reach section
    4. Final delivery to target section
    """
    # Verify scenario exists and is single section type
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    metadata = scenario.metadata or {}
    if metadata.get("scenario_type") != "single_section_delivery":
        raise HTTPException(
            status_code=400,
            detail="Scenario is not a single section delivery type"
        )
    
    # Create simulation run
    from ...core.models import SimulationRun
    
    run = SimulationRun(
        scenario_id=scenario_id,
        status=SimulationStatus.pending.value,
        started_by=current_user,
        parameters={
            "target_section": metadata.get("target_section"),
            "include_canal_filling": True,
            "track_water_front": True
        }
    )
    
    db.add(run)
    await db.commit()
    await db.refresh(run)
    
    # Start simulation in background
    from ...services.simulation_service import SimulationService
    
    background_tasks.add_task(
        SimulationService.run_single_section_simulation,
        run.run_id,
        scenario_id
    )
    
    return {
        "run_id": run.run_id,
        "status": run.status,
        "message": f"Simulation started for delivering water to {metadata['target_section']['section_id']}",
        "estimated_completion_time": metadata.get("canal_volumes", {}).get("travel_time_hours", 24)
    }


@router.get("/track-water-front/{run_id}")
async def track_water_front(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Track water front progression in single section delivery
    
    Returns current position of water front and estimated time to target
    """
    from ...core.models import SimulationRun, SimulationState
    
    # Get simulation run
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    
    # Get latest state
    result = await db.execute(
        select(SimulationState)
        .where(SimulationState.run_id == run_id)
        .order_by(SimulationState.simulation_time.desc())
        .limit(1)
    )
    latest_state = result.scalar_one_or_none()
    
    if not latest_state:
        return {
            "run_id": run_id,
            "status": run.status,
            "water_front_position": "Not started",
            "progress_percent": 0
        }
    
    # Extract water front tracking from state
    state_data = latest_state.state_data or {}
    water_tracking = state_data.get("water_tracking", {})
    
    return {
        "run_id": run_id,
        "status": run.status,
        "simulation_time": latest_state.simulation_time,
        "water_front_position": water_tracking.get("current_position", "Unknown"),
        "distance_traveled_km": water_tracking.get("distance_traveled_km", 0),
        "total_distance_km": water_tracking.get("total_distance_km", 0),
        "progress_percent": water_tracking.get("progress_percent", 0),
        "estimated_arrival_time": water_tracking.get("estimated_arrival_time"),
        "gates_passed": water_tracking.get("gates_passed", []),
        "current_segment": water_tracking.get("current_segment"),
        "water_delivered_m3": state_data.get("metrics", {}).get("total_delivered_m3", 0)
    }
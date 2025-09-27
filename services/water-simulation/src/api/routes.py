"""
API routes for Water Simulation Service
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.schemas import (
    ScenarioCreate, ScenarioUpdate, ScenarioResponse,
    SectionDemandCreate, SimulationRunCreate, SimulationRunResponse,
    SimulationStateResponse, OptimizationResultResponse,
    AnalysisResultResponse, SimulationSummary, PaginatedResponse,
    GateOperationSchedule
)
from src.core.models import Scenario, SimulationRun, SectionDemand
from src.core.simulation_engine import SimulationEngine
from src.services.demand_simulator import DemandSimulator, DemandScenario
from src.services.result_analyzer import ResultAnalyzer
from src.clients.ros_client import ROSClient
from src.clients.flow_client import FlowMonitoringClient
from src.clients.gate_client import GateControlClient
from src.clients.gis_client import GISClient
from src.config import get_settings

router = APIRouter()
settings = get_settings()


# Dependency injection
async def get_db():
    """Get database session"""
    # In production, this would use proper session management
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session


async def get_service_clients():
    """Get service clients"""
    return {
        "ros": ROSClient(settings.ros_service_url),
        "flow": FlowMonitoringClient(settings.flow_service_url),
        "gate": GateControlClient(settings.gate_service_url),
        "gis": GISClient(settings.gis_service_url)
    }


# Scenario Management Endpoints
@router.post("/scenarios", response_model=ScenarioResponse)
async def create_scenario(
    scenario_data: ScenarioCreate,
    db: AsyncSession = Depends(get_db)
) -> ScenarioResponse:
    """Create a new simulation scenario"""
    scenario = Scenario(
        name=scenario_data.name,
        description=scenario_data.description,
        base_date=datetime.combine(scenario_data.base_date, datetime.min.time()),
        duration_days=scenario_data.duration_days,
        time_step_minutes=scenario_data.time_step_minutes,
        optimization_objective=scenario_data.optimization_objective.value,
        created_by="api_user",  # Would get from auth context
        metadata=scenario_data.metadata
    )
    
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    
    return ScenarioResponse.from_orm(scenario)


@router.get("/scenarios", response_model=PaginatedResponse)
async def list_scenarios(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> PaginatedResponse:
    """List all scenarios with pagination"""
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Scenario)
    )
    total = count_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Scenario)
        .order_by(Scenario.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    scenarios = result.scalars().all()
    
    return PaginatedResponse(
        items=[ScenarioResponse.from_orm(s) for s in scenarios],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> ScenarioResponse:
    """Get scenario details"""
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    return ScenarioResponse.from_orm(scenario)


@router.put("/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    scenario_update: ScenarioUpdate,
    db: AsyncSession = Depends(get_db)
) -> ScenarioResponse:
    """Update scenario details"""
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Update fields
    for field, value in scenario_update.dict(exclude_unset=True).items():
        setattr(scenario, field, value)
    
    await db.commit()
    await db.refresh(scenario)
    
    return ScenarioResponse.from_orm(scenario)


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a scenario and all related data"""
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    await db.delete(scenario)
    await db.commit()
    
    return {"message": "Scenario deleted successfully"}


# Section Demand Configuration
@router.post("/scenarios/{scenario_id}/demands")
async def configure_section_demands(
    scenario_id: UUID,
    demands: List[SectionDemandCreate],
    db: AsyncSession = Depends(get_db)
):
    """Configure section-specific demands for a scenario"""
    # Verify scenario exists
    result = await db.execute(
        select(Scenario).where(Scenario.scenario_id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Create demand records
    for demand_data in demands:
        demand = SectionDemand(
            scenario_id=scenario_id,
            section_id=demand_data.section_id,
            week_number=demand_data.week_number,
            base_demand_m3=demand_data.base_demand_m3,
            weather_adjustment_factor=demand_data.weather_adjustment_factor,
            priority_override=demand_data.priority_override,
            min_delivery_m3=demand_data.min_delivery_m3,
            max_delivery_m3=demand_data.max_delivery_m3,
            delivery_window_hours=demand_data.delivery_window_hours
        )
        db.add(demand)
    
    await db.commit()
    
    return {"message": f"Configured {len(demands)} section demands"}


# Simulation Execution
@router.post("/simulations", response_model=SimulationRunResponse)
async def start_simulation(
    run_config: SimulationRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    clients: Dict = Depends(get_service_clients)
):
    """Start a new simulation run"""
    # Create simulation engine
    engine = SimulationEngine(
        db_session=db,
        ros_client=clients["ros"],
        flow_client=clients["flow"],
        gate_client=clients["gate"],
        gis_client=clients["gis"]
    )
    
    # Initialize simulation
    run = await engine.initialize_simulation(
        run_config.scenario_id,
        run_config.start_from_time
    )
    
    # Start simulation in background
    background_tasks.add_task(engine.run_simulation)
    
    return SimulationRunResponse.from_orm(run)


@router.get("/simulations", response_model=List[SimulationRunResponse])
async def list_simulation_runs(
    scenario_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> List[SimulationRunResponse]:
    """List simulation runs"""
    query = select(SimulationRun)
    
    if scenario_id:
        query = query.where(SimulationRun.scenario_id == scenario_id)
    
    if status:
        query = query.where(SimulationRun.status == status)
    
    query = query.order_by(SimulationRun.created_at.desc())
    
    result = await db.execute(query)
    runs = result.scalars().all()
    
    return [SimulationRunResponse.from_orm(run) for run in runs]


@router.get("/simulations/{run_id}", response_model=SimulationRunResponse)
async def get_simulation_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> SimulationRunResponse:
    """Get simulation run details"""
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    
    return SimulationRunResponse.from_orm(run)


@router.put("/simulations/{run_id}/cancel")
async def cancel_simulation(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a running simulation"""
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    
    if run.status != "running":
        raise HTTPException(status_code=400, detail="Simulation is not running")
    
    run.status = "cancelled"
    await db.commit()
    
    return {"message": "Simulation cancelled"}


# Simulation Results
@router.get("/simulations/{run_id}/states")
async def get_simulation_states(
    run_id: UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
) -> List[SimulationStateResponse]:
    """Get simulation states for a time range"""
    from src.core.models import SimulationState
    
    query = select(SimulationState).where(SimulationState.run_id == run_id)
    
    if start_time:
        query = query.where(SimulationState.simulation_time >= start_time)
    
    if end_time:
        query = query.where(SimulationState.simulation_time <= end_time)
    
    query = query.order_by(SimulationState.time_step).limit(limit)
    
    result = await db.execute(query)
    states = result.scalars().all()
    
    return [SimulationStateResponse.from_orm(state) for state in states]


@router.get("/simulations/{run_id}/optimization-results")
async def get_optimization_results(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> List[OptimizationResultResponse]:
    """Get optimization results for a simulation run"""
    from src.core.models import OptimizationResult
    
    result = await db.execute(
        select(OptimizationResult)
        .where(OptimizationResult.run_id == run_id)
        .order_by(OptimizationResult.optimization_time)
    )
    results = result.scalars().all()
    
    return [OptimizationResultResponse.from_orm(r) for r in results]


# Analysis
@router.post("/simulations/{run_id}/analyze")
async def analyze_simulation(
    run_id: UUID,
    analysis_type: str = "comprehensive",
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Run analysis on simulation results"""
    analyzer = ResultAnalyzer(db)
    
    # Run analysis in background
    background_tasks.add_task(
        analyzer.analyze_simulation_run,
        run_id,
        analysis_type
    )
    
    return {"message": f"Analysis started for run {run_id}"}


@router.get("/simulations/{run_id}/analysis")
async def get_analysis_results(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> List[AnalysisResultResponse]:
    """Get analysis results for a simulation run"""
    from src.core.models import AnalysisResult
    
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.run_id == run_id)
        .order_by(AnalysisResult.created_at.desc())
    )
    analyses = result.scalars().all()
    
    return [AnalysisResultResponse.from_orm(a) for a in analyses]


@router.get("/simulations/{run_id}/summary", response_model=SimulationSummary)
async def get_simulation_summary(
    run_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> SimulationSummary:
    """Get summary of simulation results"""
    # Get run details
    result = await db.execute(
        select(SimulationRun).where(SimulationRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    
    # Get scenario name
    scenario_result = await db.execute(
        select(Scenario.name).where(Scenario.scenario_id == run.scenario_id)
    )
    scenario_name = scenario_result.scalar()
    
    # Get latest analysis
    from src.core.models import AnalysisResult
    analysis_result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.run_id == run_id)
        .order_by(AnalysisResult.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar()
    
    # Build summary
    duration_hours = 0
    if run.start_time and run.end_time:
        duration_hours = (run.end_time - run.start_time).total_seconds() / 3600
    
    key_findings = []
    if analysis and analysis.recommendations:
        key_findings = analysis.recommendations[:5]
    
    return SimulationSummary(
        run_id=run_id,
        scenario_name=scenario_name,
        status=run.status,
        duration_hours=duration_hours,
        total_water_demand_m3=analysis.unmet_demand_m3 if analysis else 0,
        total_water_delivered_m3=0,  # Would calculate from states
        overall_efficiency=analysis.avg_delivery_efficiency if analysis else 0,
        optimization_score=0.85,  # Placeholder
        key_findings=key_findings
    )


# Utility Endpoints
@router.post("/demand-forecast")
async def forecast_demand(
    section_ids: List[str],
    start_date: date,
    days_ahead: int = Query(7, ge=1, le=30),
    scenario: Optional[Dict[str, Any]] = None,
    clients: Dict = Depends(get_service_clients)
):
    """Forecast water demand for sections"""
    demand_scenario = DemandScenario(**scenario) if scenario else DemandScenario()
    
    simulator = DemandSimulator(
        clients["ros"],
        clients["gis"],
        demand_scenario
    )
    
    # Initialize sections
    await simulator.initialize_sections(section_ids)
    
    # Generate forecasts
    forecasts = {}
    start_datetime = datetime.combine(start_date, datetime.min.time())
    
    for section_id in section_ids:
        profile = await simulator.forecast_demand_profile(
            section_id,
            start_datetime,
            days_ahead
        )
        forecasts[section_id] = profile
    
    return {
        "start_date": start_date.isoformat(),
        "days_ahead": days_ahead,
        "forecasts": forecasts
    }


@router.post("/scenarios/compare")
async def compare_scenarios(
    run_ids: List[UUID],
    db: AsyncSession = Depends(get_db)
):
    """Compare results across multiple simulation runs"""
    if len(run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 runs required for comparison")
    
    analyzer = ResultAnalyzer(db)
    comparison = await analyzer.compare_scenarios([str(rid) for rid in run_ids])
    
    return comparison


@router.get("/gate-schedule/{run_id}")
async def get_gate_schedule(
    run_id: UUID,
    gate_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get gate operation schedule for a simulation run"""
    from src.core.models import GateOperation
    
    query = select(GateOperation).where(GateOperation.run_id == run_id)
    
    if gate_id:
        query = query.where(GateOperation.gate_id == gate_id)
    
    query = query.order_by(GateOperation.scheduled_time)
    
    result = await db.execute(query)
    operations = result.scalars().all()
    
    schedule = []
    for op in operations:
        schedule.append({
            "gate_id": op.gate_id,
            "scheduled_time": op.scheduled_time.isoformat(),
            "target_opening_m": float(op.target_opening_m),
            "operation_type": op.operation_type,
            "status": op.status,
            "executed_time": op.executed_time.isoformat() if op.executed_time else None
        })
    
    return {
        "run_id": run_id,
        "gate_schedule": schedule,
        "total_operations": len(schedule)
    }
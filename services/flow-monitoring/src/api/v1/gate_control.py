#!/usr/bin/env python3
"""
Dual-Mode Gate Control API
Provides unified control interface for both automated and manual gates
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import uuid
import logging

from ...core.gate_registry import ControlMode, EquipmentStatus
from ...core.enhanced_hydraulic_solver import EnhancedHydraulicSolver
from ...core.scada_health_monitor import SCADAHealthMonitor
from ...core.state_preservation import StatePreservationSystem, TransitionType
from ...services.scada_client import SCADAClient
from ...services.field_ops_client import FieldOpsClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/control", tags=["gate_control"])


# Request/Response Models
class GatePositionRequest(BaseModel):
    """Request to change gate position"""
    gate_id: str
    target_position_m: Optional[float] = Field(None, ge=0, description="Target position in meters")
    target_percentage: Optional[float] = Field(None, ge=0, le=100, description="Target position as percentage")
    transition_time_s: float = Field(300, ge=0, description="Time for transition in seconds")
    priority: str = Field("normal", regex="^(low|normal|high|emergency)$")
    reason: str = Field(..., min_length=3, description="Reason for adjustment")
    override_safety: bool = Field(False, description="Override safety checks (requires authorization)")
    
    @validator('target_position_m', 'target_percentage')
    def validate_position(cls, v, values):
        if values.get('target_position_m') is None and values.get('target_percentage') is None:
            raise ValueError("Either target_position_m or target_percentage must be provided")
        return v


class GateControlResponse(BaseModel):
    """Response for gate control command"""
    request_id: str
    gate_id: str
    control_mode: str
    command_accepted: bool
    estimated_completion_time: datetime
    warnings: List[str] = []
    details: Dict[str, any] = {}


class BatchGateControlRequest(BaseModel):
    """Request to control multiple gates"""
    gates: List[GatePositionRequest]
    coordination_mode: str = Field("sequential", regex="^(sequential|parallel|optimized)$")
    max_parallel: int = Field(3, ge=1, le=10, description="Max gates to move in parallel")


class GateStatusResponse(BaseModel):
    """Current gate status"""
    gate_id: str
    control_mode: str
    current_position_m: float
    current_percentage: float
    target_position_m: Optional[float]
    flow_rate_m3s: float
    upstream_level_m: float
    downstream_level_m: float
    equipment_status: str
    last_command_time: Optional[datetime]
    last_update_time: datetime


class ManualOperationRequest(BaseModel):
    """Request for manual gate operation"""
    gate_id: str
    target_position_m: float = Field(..., ge=0)
    priority: str = Field("normal", regex="^(low|normal|high|emergency)$")
    scheduled_time: Optional[datetime] = None
    assigned_team: Optional[str] = None
    estimated_duration_min: int = Field(30, ge=10, le=480)
    safety_notes: Optional[str] = None
    contact_person: str
    contact_phone: str


class WorkOrderResponse(BaseModel):
    """Response for manual operation work order"""
    work_order_id: str
    gate_id: str
    status: str
    scheduled_time: datetime
    assigned_team: str
    estimated_completion: datetime
    qr_code_url: Optional[str] = None


class EmergencyStopRequest(BaseModel):
    """Emergency stop request"""
    scope: str = Field(..., regex="^(single|zone|all)$")
    gate_ids: Optional[List[str]] = None
    zone_id: Optional[str] = None
    reason: str
    authorized_by: str


# Dependency injection
async def get_gate_registry():
    """Get gate registry instance"""
    # This would be properly injected in production
    from ...core.gate_registry import GateRegistry
    return GateRegistry()


async def get_hydraulic_solver():
    """Get hydraulic solver instance"""
    # This would be properly injected in production
    return EnhancedHydraulicSolver({}, await get_gate_registry())


async def get_scada_monitor():
    """Get SCADA health monitor instance"""
    # This would be properly injected in production
    return SCADAHealthMonitor({}, await get_gate_registry())


async def get_state_preservation():
    """Get state preservation system instance"""
    # This would be properly injected in production
    return StatePreservationSystem(None, None)


async def get_scada_client():
    """Get SCADA client instance"""
    return SCADAClient()


async def get_field_ops_client():
    """Get field operations client instance"""
    return FieldOpsClient()


# API Endpoints
@router.post("/gate/position", response_model=GateControlResponse)
async def control_gate_position(
    request: GatePositionRequest,
    background_tasks: BackgroundTasks,
    gate_registry = Depends(get_gate_registry),
    hydraulic_solver = Depends(get_hydraulic_solver),
    scada_monitor = Depends(get_scada_monitor),
    scada_client = Depends(get_scada_client),
    field_ops_client = Depends(get_field_ops_client)
):
    """
    Control gate position - works for both automated and manual gates
    """
    request_id = str(uuid.uuid4())
    warnings = []
    
    # Check if gate exists
    gate_mode = gate_registry.get_gate_mode(request.gate_id)
    if gate_mode is None:
        raise HTTPException(status_code=404, detail=f"Gate {request.gate_id} not found")
    
    # Get gate properties
    is_automated = gate_registry.is_automated(request.gate_id)
    
    # Convert percentage to meters if needed
    if request.target_position_m is None and request.target_percentage is not None:
        gate_props = hydraulic_solver.hydraulics.gate_properties.get(request.gate_id)
        if gate_props:
            request.target_position_m = gate_props.height_m * (request.target_percentage / 100)
        else:
            raise HTTPException(status_code=400, detail="Cannot convert percentage without gate properties")
    
    # Safety checks (unless overridden)
    if not request.override_safety:
        safety_warnings = await _perform_safety_checks(
            request.gate_id, request.target_position_m, hydraulic_solver
        )
        warnings.extend(safety_warnings)
        
        if any("blocked" in w.lower() for w in safety_warnings):
            return GateControlResponse(
                request_id=request_id,
                gate_id=request.gate_id,
                control_mode=gate_mode.value,
                command_accepted=False,
                estimated_completion_time=datetime.now(),
                warnings=warnings,
                details={"reason": "Safety checks failed"}
            )
    
    # Route based on control mode
    if is_automated and gate_mode == ControlMode.AUTO:
        # Send to SCADA
        result = await _control_automated_gate(
            request, request_id, scada_client, scada_monitor, gate_registry
        )
    else:
        # Create work order for manual operation
        result = await _control_manual_gate(
            request, request_id, field_ops_client, gate_registry
        )
    
    # Add any warnings
    result.warnings.extend(warnings)
    
    # Schedule background hydraulic impact analysis
    background_tasks.add_task(
        _analyze_hydraulic_impact,
        request.gate_id, request.target_position_m, hydraulic_solver
    )
    
    return result


@router.post("/gates/batch", response_model=List[GateControlResponse])
async def control_multiple_gates(
    request: BatchGateControlRequest,
    background_tasks: BackgroundTasks,
    gate_registry = Depends(get_gate_registry),
    hydraulic_solver = Depends(get_hydraulic_solver),
    scada_monitor = Depends(get_scada_monitor),
    scada_client = Depends(get_scada_client),
    field_ops_client = Depends(get_field_ops_client)
):
    """
    Control multiple gates with coordination
    """
    responses = []
    
    if request.coordination_mode == "optimized":
        # Run optimization to determine best sequence
        gate_sequence = await _optimize_gate_sequence(
            request.gates, hydraulic_solver
        )
    else:
        gate_sequence = request.gates
    
    # Process gates based on coordination mode
    if request.coordination_mode == "parallel":
        # Process in parallel batches
        for i in range(0, len(gate_sequence), request.max_parallel):
            batch = gate_sequence[i:i + request.max_parallel]
            batch_responses = await asyncio.gather(*[
                control_gate_position(
                    gate_req, background_tasks, gate_registry,
                    hydraulic_solver, scada_monitor, scada_client, field_ops_client
                )
                for gate_req in batch
            ])
            responses.extend(batch_responses)
    else:
        # Process sequentially
        for gate_req in gate_sequence:
            response = await control_gate_position(
                gate_req, background_tasks, gate_registry,
                hydraulic_solver, scada_monitor, scada_client, field_ops_client
            )
            responses.append(response)
    
    return responses


@router.get("/gate/{gate_id}/status", response_model=GateStatusResponse)
async def get_gate_status(
    gate_id: str,
    gate_registry = Depends(get_gate_registry),
    hydraulic_solver = Depends(get_hydraulic_solver),
    scada_client = Depends(get_scada_client)
):
    """
    Get current gate status
    """
    # Check if gate exists
    gate_mode = gate_registry.get_gate_mode(gate_id)
    if gate_mode is None:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    
    # Get status based on gate type
    if gate_registry.is_automated(gate_id):
        gate_data = gate_registry.automated_gates[gate_id]
        
        # Get real-time data from SCADA if available
        if gate_mode == ControlMode.AUTO and await scada_client.is_connected():
            scada_data = await scada_client.get_gate_status(gate_id)
            current_position = scada_data.get("position_m", 0)
            last_update = datetime.fromisoformat(scada_data.get("timestamp", datetime.now().isoformat()))
        else:
            # Use last known values
            current_position = hydraulic_solver.current_state.gate_openings.get(gate_id, 0)
            last_update = gate_data.last_communication or datetime.now()
    else:
        gate_data = gate_registry.manual_gates[gate_id]
        current_position = hydraulic_solver.current_state.gate_openings.get(gate_id, 0)
        last_update = gate_data.last_operation or datetime.now()
    
    # Get hydraulic data
    gate_props = hydraulic_solver.hydraulics.gate_properties.get(gate_id)
    if gate_props:
        current_percentage = (current_position / gate_props.height_m) * 100
    else:
        current_percentage = 0
    
    # Get flow and levels from hydraulic state
    flow_rate = hydraulic_solver.current_state.gate_flows.get(gate_id, 0)
    
    # Get water levels
    if gate_id in hydraulic_solver.gates:
        upstream_node, downstream_node = hydraulic_solver.gates[gate_id]
        upstream_level = hydraulic_solver.current_state.water_levels.get(upstream_node, 0)
        downstream_level = hydraulic_solver.current_state.water_levels.get(downstream_node, 0)
    else:
        upstream_level = downstream_level = 0
    
    return GateStatusResponse(
        gate_id=gate_id,
        control_mode=gate_mode.value,
        current_position_m=current_position,
        current_percentage=current_percentage,
        target_position_m=None,  # Would get from active commands
        flow_rate_m3s=flow_rate,
        upstream_level_m=upstream_level,
        downstream_level_m=downstream_level,
        equipment_status=gate_data.equipment_status.value if hasattr(gate_data, 'equipment_status') else "unknown",
        last_command_time=gate_data.last_command_time if hasattr(gate_data, 'last_command_time') else None,
        last_update_time=last_update
    )


@router.post("/manual/work-order", response_model=WorkOrderResponse)
async def create_manual_work_order(
    request: ManualOperationRequest,
    gate_registry = Depends(get_gate_registry),
    field_ops_client = Depends(get_field_ops_client)
):
    """
    Create work order for manual gate operation
    """
    # Verify gate exists and is manual
    if request.gate_id not in gate_registry.manual_gates:
        if request.gate_id in gate_registry.automated_gates:
            raise HTTPException(
                status_code=400, 
                detail=f"Gate {request.gate_id} is automated. Use /control/gate/position endpoint"
            )
        else:
            raise HTTPException(status_code=404, detail=f"Gate {request.gate_id} not found")
    
    gate = gate_registry.manual_gates[request.gate_id]
    
    # Determine team assignment
    if request.assigned_team is None:
        request.assigned_team = gate.field_team_zone
    
    # Set scheduled time if not provided
    if request.scheduled_time is None:
        if request.priority == "emergency":
            request.scheduled_time = datetime.now()
        else:
            request.scheduled_time = datetime.now() + timedelta(hours=2)
    
    # Create work order
    work_order = await field_ops_client.create_work_order({
        "gate_id": request.gate_id,
        "location": gate.location,
        "current_position": "unknown",  # Would get from state
        "target_position": request.target_position_m,
        "priority": request.priority,
        "scheduled_time": request.scheduled_time,
        "assigned_team": request.assigned_team,
        "estimated_duration_min": request.estimated_duration_min,
        "safety_notes": request.safety_notes,
        "contact_person": request.contact_person,
        "contact_phone": request.contact_phone,
        "operation_details": gate.operation_details.__dict__
    })
    
    return WorkOrderResponse(
        work_order_id=work_order["id"],
        gate_id=request.gate_id,
        status=work_order["status"],
        scheduled_time=request.scheduled_time,
        assigned_team=request.assigned_team,
        estimated_completion=request.scheduled_time + timedelta(minutes=request.estimated_duration_min),
        qr_code_url=work_order.get("qr_code_url")
    )


@router.post("/emergency/stop")
async def emergency_stop(
    request: EmergencyStopRequest,
    background_tasks: BackgroundTasks,
    gate_registry = Depends(get_gate_registry),
    scada_client = Depends(get_scada_client),
    state_preservation = Depends(get_state_preservation)
):
    """
    Emergency stop for gates
    """
    # Preserve current state
    background_tasks.add_task(
        state_preservation.preserve_state,
        TransitionType.NORMAL_TO_EMERGENCY,
        f"Emergency stop: {request.reason}",
        await _get_current_system_state(),
        request.authorized_by
    )
    
    affected_gates = []
    
    # Determine affected gates
    if request.scope == "single" and request.gate_ids:
        affected_gates = request.gate_ids
    elif request.scope == "zone" and request.zone_id:
        # Get all gates in zone (would need zone mapping)
        affected_gates = []  # TODO: Implement zone mapping
    elif request.scope == "all":
        affected_gates = gate_registry.get_automated_gates_list()
    
    # Send emergency stop commands
    results = {}
    for gate_id in affected_gates:
        if gate_registry.is_automated(gate_id):
            try:
                await scada_client.emergency_stop(gate_id)
                results[gate_id] = "stopped"
            except Exception as e:
                results[gate_id] = f"failed: {str(e)}"
        else:
            results[gate_id] = "manual gate - dispatch field team"
    
    # Log emergency action
    logger.critical(f"EMERGENCY STOP executed by {request.authorized_by}: {request.reason}")
    
    return {
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now(),
        "affected_gates": len(affected_gates),
        "results": results
    }


@router.get("/modes/summary")
async def get_control_modes_summary(
    gate_registry = Depends(get_gate_registry)
):
    """
    Get summary of current control modes
    """
    summary = gate_registry.get_gate_summary()
    
    # Add mode-specific counts
    mode_counts = {}
    for mode in ControlMode:
        mode_counts[mode.value] = len(gate_registry.get_gates_by_mode(mode))
    
    summary["mode_distribution"] = mode_counts
    
    return summary


# Helper functions
async def _control_automated_gate(
    request: GatePositionRequest,
    request_id: str,
    scada_client: SCADAClient,
    scada_monitor: SCADAHealthMonitor,
    gate_registry
) -> GateControlResponse:
    """Handle automated gate control"""
    
    # Check SCADA availability
    if not scada_monitor.is_scada_available():
        # Fallback to manual mode
        gate_registry.update_gate_mode(
            request.gate_id, 
            ControlMode.MANUAL,
            "SCADA unavailable"
        )
        return GateControlResponse(
            request_id=request_id,
            gate_id=request.gate_id,
            control_mode=ControlMode.MANUAL.value,
            command_accepted=False,
            estimated_completion_time=datetime.now(),
            warnings=["SCADA unavailable - gate switched to manual mode"],
            details={"fallback": True}
        )
    
    # Send command to SCADA
    try:
        scada_response = await scada_client.send_gate_command({
            "gate_id": request.gate_id,
            "command": "set_position",
            "target_position_m": request.target_position_m,
            "transition_time_s": request.transition_time_s,
            "priority": request.priority
        })
        
        return GateControlResponse(
            request_id=request_id,
            gate_id=request.gate_id,
            control_mode=ControlMode.AUTO.value,
            command_accepted=True,
            estimated_completion_time=datetime.now() + timedelta(seconds=request.transition_time_s),
            warnings=[],
            details={"scada_response": scada_response}
        )
        
    except Exception as e:
        logger.error(f"SCADA command failed for gate {request.gate_id}: {e}")
        gate_registry.record_communication(request.gate_id, success=False)
        
        return GateControlResponse(
            request_id=request_id,
            gate_id=request.gate_id,
            control_mode=ControlMode.AUTO.value,
            command_accepted=False,
            estimated_completion_time=datetime.now(),
            warnings=[f"SCADA command failed: {str(e)}"],
            details={"error": str(e)}
        )


async def _control_manual_gate(
    request: GatePositionRequest,
    request_id: str,
    field_ops_client: FieldOpsClient,
    gate_registry
) -> GateControlResponse:
    """Handle manual gate control"""
    
    gate = gate_registry.manual_gates.get(request.gate_id)
    if not gate:
        gate = gate_registry.automated_gates.get(request.gate_id)
    
    # Create work order
    work_order = await field_ops_client.create_work_order({
        "gate_id": request.gate_id,
        "target_position": request.target_position_m,
        "priority": request.priority,
        "reason": request.reason,
        "requested_by": "Flow Monitoring System",
        "location": gate.location,
        "team_zone": gate.field_team_zone if hasattr(gate, 'field_team_zone') else None
    })
    
    # Estimate completion based on priority
    if request.priority == "emergency":
        estimated_duration = timedelta(hours=1)
    elif request.priority == "high":
        estimated_duration = timedelta(hours=4)
    else:
        estimated_duration = timedelta(hours=24)
    
    return GateControlResponse(
        request_id=request_id,
        gate_id=request.gate_id,
        control_mode=ControlMode.MANUAL.value,
        command_accepted=True,
        estimated_completion_time=datetime.now() + estimated_duration,
        warnings=["Manual operation required"],
        details={
            "work_order_id": work_order["id"],
            "assigned_team": work_order.get("assigned_team")
        }
    )


async def _perform_safety_checks(
    gate_id: str, 
    target_position: float,
    hydraulic_solver
) -> List[str]:
    """Perform safety checks before gate movement"""
    warnings = []
    
    # Check 1: Velocity limits
    # Simulate the change to check velocities
    future_states = await hydraulic_solver.simulate_gate_change(
        gate_id, target_position, 60  # Quick simulation
    )
    
    if future_states:
        final_state = future_states[-1]
        for section_id, velocity in final_state.canal_flows.items():
            if abs(velocity) > 2.0:  # 2 m/s limit
                warnings.append(f"High velocity predicted in {section_id}: {velocity:.1f} m/s")
    
    # Check 2: Water level constraints
    for node_id, level in final_state.water_levels.items():
        node = hydraulic_solver.nodes.get(node_id)
        if node:
            depth = level - node.elevation_m
            if depth > node.max_depth_m * 0.9:
                warnings.append(f"High water level at {node_id}: {depth:.1f}m")
            elif depth < node.min_depth_m * 1.5:
                warnings.append(f"Low water level at {node_id}: {depth:.1f}m")
    
    # Check 3: Downstream impact
    if gate_id in hydraulic_solver.gates:
        _, downstream = hydraulic_solver.gates[gate_id]
        downstream_demand = hydraulic_solver.nodes[downstream].demand_m3s
        if downstream_demand > 0 and target_position < 0.1:
            warnings.append(f"Closing gate may affect downstream demand of {downstream_demand:.1f} m³/s")
    
    return warnings


async def _optimize_gate_sequence(
    gates: List[GatePositionRequest],
    hydraulic_solver
) -> List[GatePositionRequest]:
    """Optimize sequence of gate operations"""
    # Simple optimization: prioritize by location (upstream to downstream)
    # In production, this would use more sophisticated optimization
    
    gate_locations = {}
    for gate_req in gates:
        if gate_req.gate_id in hydraulic_solver.gates:
            upstream, _ = hydraulic_solver.gates[gate_req.gate_id]
            # Assign a simple upstream score (would be more complex in reality)
            gate_locations[gate_req.gate_id] = len(upstream)
    
    # Sort by upstream location (lower score = more upstream)
    sorted_gates = sorted(
        gates,
        key=lambda g: gate_locations.get(g.gate_id, 999)
    )
    
    return sorted_gates


async def _analyze_hydraulic_impact(
    gate_id: str,
    target_position: float,
    hydraulic_solver
):
    """Background task to analyze hydraulic impact"""
    try:
        # Run detailed simulation
        states = await hydraulic_solver.simulate_gate_change(
            gate_id, target_position, 1800  # 30 minute simulation
        )
        
        # Analyze results and store for future reference
        impact_summary = {
            "gate_id": gate_id,
            "target_position": target_position,
            "simulation_time": datetime.now(),
            "predicted_flows": {},
            "predicted_levels": {},
            "warnings": []
        }
        
        # Store analysis results (would go to database)
        logger.info(f"Hydraulic impact analysis completed for gate {gate_id}")
        
    except Exception as e:
        logger.error(f"Failed to analyze hydraulic impact: {e}")


async def _get_current_system_state() -> Dict:
    """Get current system state for preservation"""
    # This would gather complete system state
    # For now, returning a placeholder
    return {
        "timestamp": datetime.now(),
        "gates": {},
        "water_levels": {},
        "flow_targets": {},
        "active_deliveries": []
    }
"""
Gate Control API endpoints for dual-mode operation
Supports both automated (SCADA) and manual gate operations
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import structlog

from ..controllers.dual_mode_gate_controller import DualModeGateController
from ..schemas.gate_control import (
    GateState,
    GateStateResponse,
    ManualGateCommand,
    GateMode,
    GateTransitionRequest
)
from ..db.connections import DatabaseManager
from ..core.metrics import gate_operations_counter

logger = structlog.get_logger()
router = APIRouter()

# Initialize controller (will be properly initialized in lifespan)
gate_controller = None


def get_gate_controller() -> DualModeGateController:
    """Dependency to get gate controller instance"""
    if gate_controller is None:
        raise HTTPException(status_code=503, detail="Gate controller not initialized")
    return gate_controller


@router.get("/state", response_model=Dict[str, GateStateResponse])
async def get_all_gates_state(
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """
    Get current state of all gates in the system.
    Returns operational mode, opening percentage, flow rate, and control status.
    """
    try:
        states = await controller.get_all_gate_states()
        logger.info("Retrieved gate states", count=len(states))
        return states
    except Exception as e:
        logger.error("Failed to get gate states", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve gate states: {str(e)}")


@router.get("/state/{gate_id}", response_model=GateStateResponse)
async def get_gate_state(
    gate_id: str,
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """Get state of a specific gate"""
    try:
        state = await controller.get_gate_state(gate_id)
        if state is None:
            raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get gate state", gate_id=gate_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve gate state: {str(e)}")


@router.put("/manual/{gate_id}/state")
async def update_manual_gate_state(
    gate_id: str,
    command: ManualGateCommand,
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """
    Update state of a manually operated gate.
    Used by field teams to report actual gate positions.
    """
    try:
        # Validate gate is in manual mode
        gate_state = await controller.get_gate_state(gate_id)
        if gate_state is None:
            raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
        
        if gate_state.mode != GateMode.MANUAL:
            raise HTTPException(
                status_code=400, 
                detail=f"Gate {gate_id} is in {gate_state.mode} mode, cannot update manually"
            )
        
        # Update gate state
        success = await controller.update_manual_gate_state(
            gate_id=gate_id,
            opening_percentage=command.opening_percentage,
            operator_id=command.operator_id,
            notes=command.notes
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update gate state")
        
        # Record metric
        gate_operations_counter.labels(
            gate_id=gate_id,
            operation="manual_update",
            mode="manual"
        ).inc()
        
        logger.info(
            "Manual gate state updated",
            gate_id=gate_id,
            opening=command.opening_percentage,
            operator=command.operator_id
        )
        
        return {"status": "success", "message": f"Gate {gate_id} updated to {command.opening_percentage}%"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update manual gate", gate_id=gate_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update gate: {str(e)}")


@router.post("/mode/transition")
async def request_mode_transition(
    request: GateTransitionRequest,
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """
    Request transition between operational modes for a gate.
    Handles validation and safe transition procedures.
    """
    try:
        # Validate transition
        validation = await controller.validate_mode_transition(
            gate_id=request.gate_id,
            target_mode=request.target_mode,
            force=request.force
        )
        
        if not validation.is_valid and not request.force:
            return {
                "status": "blocked",
                "reason": validation.reason,
                "current_mode": validation.current_mode,
                "recommendations": validation.recommendations
            }
        
        # Execute transition
        success = await controller.execute_mode_transition(
            gate_id=request.gate_id,
            target_mode=request.target_mode,
            transition_time=request.transition_time
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Mode transition failed")
        
        logger.info(
            "Gate mode transition completed",
            gate_id=request.gate_id,
            target_mode=request.target_mode
        )
        
        return {
            "status": "success",
            "message": f"Gate {request.gate_id} transitioning to {request.target_mode} mode"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Mode transition failed", gate_id=request.gate_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Mode transition failed: {str(e)}")


@router.get("/manual/instructions")
async def get_manual_instructions(
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """
    Get current manual operation instructions for field teams.
    Considers automated gate states for coordinated control.
    """
    try:
        instructions = await controller.generate_manual_instructions()
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "instructions": instructions,
            "priority_gates": [inst["gate_id"] for inst in instructions if inst.get("priority", False)]
        }
    except Exception as e:
        logger.error("Failed to generate manual instructions", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate instructions: {str(e)}")


@router.get("/synchronization/status")
async def get_synchronization_status(
    controller: DualModeGateController = Depends(get_gate_controller)
):
    """Get synchronization status between automated and manual operations"""
    try:
        status = await controller.get_synchronization_status()
        return status
    except Exception as e:
        logger.error("Failed to get synchronization status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


# Export router
__all__ = ["router"]
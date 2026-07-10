"""
Gate Configuration API
Provides gate type and configuration information to other services
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict
from schemas.gate_control import GateConfigResponse, GateLocation
from services.gate_registry import get_gate_registry

from .gates import get_gate_controller

# Part of the legacy gates surface (Wave 1.5, Decision 2): quarantined behind the
# same flag/controller state as /api/v1/gates/* — 503 while disabled.
router = APIRouter(
    prefix="/gates/config",
    tags=["gate-configuration"],
    dependencies=[Depends(get_gate_controller)],
)


@router.get("/all", response_model=Dict[str, Dict])
async def get_all_gate_configs():
    """Get configuration for all gates in the system"""
    return get_gate_registry().gates


@router.get("/{gate_id}", response_model=GateConfigResponse)
async def get_gate_config(gate_id: str):
    """Get configuration for a specific gate"""
    gate_info = get_gate_registry().get_gate_info(gate_id)
    if not gate_info:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    
    return GateConfigResponse(
        gate_id=gate_id,
        name=gate_info["name"],
        type=gate_info["type"],
        location=GateLocation(**gate_info["location"]),
        zone=gate_info["zone"],
        width_m=gate_info["width_m"],
        max_opening_m=gate_info["max_opening_m"],
        max_flow_m3s=gate_info["max_flow_m3s"],
        calibration=gate_info["calibration"],
        scada_id=gate_info.get("scada_id"),
        physical_markers=gate_info.get("physical_markers"),
        fallback_manual=gate_info.get("fallback_manual", False),
        manual_operation=gate_info.get("manual_operation")
    )


@router.get("/type/{gate_type}", response_model=List[str])
async def get_gates_by_type(gate_type: str):
    """Get all gates of a specific type (automated/manual)"""
    if gate_type.lower() == "automated":
        return get_gate_registry().get_automated_gates()
    elif gate_type.lower() == "manual":
        return get_gate_registry().get_manual_gates()
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid gate type. Use 'automated' or 'manual'"
        )


@router.get("/zone/{zone}", response_model=List[Dict])
async def get_gates_by_zone(zone: int):
    """Get all gates in a specific zone with their types"""
    gate_ids = get_gate_registry().get_gates_by_zone(zone)
    gates = []
    
    for gate_id in gate_ids:
        gate_info = get_gate_registry().get_gate_info(gate_id)
        if gate_info:
            gates.append({
                "gate_id": gate_id,
                "name": gate_info["name"],
                "type": gate_info["type"],
                "location": gate_info["location"]
            })
    
    return gates


@router.get("/near-location", response_model=List[Dict])
async def get_gates_near_location(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(5.0, description="Search radius in kilometers")
):
    """Find gates within a radius of a location"""
    return get_gate_registry().get_gates_near_location(lat, lon, radius_km)


@router.get("/summary", response_model=Dict)
async def get_operational_summary():
    """Get summary of gate types and distribution"""
    return get_gate_registry().get_operational_summary()


@router.get("/physical-markers", response_model=Dict[str, str])
async def get_all_physical_markers():
    """Get physical markers for all gates (for field teams)"""
    markers = {}
    
    for gate_id, gate_info in get_gate_registry().gates.items():
        marker = gate_info.get("physical_markers")
        if marker:
            markers[gate_id] = marker
    
    return markers


@router.get("/scada-mapping", response_model=Dict[str, str])
async def get_scada_to_gate_mapping():
    """Get mapping of SCADA IDs to gate IDs"""
    return get_gate_registry().scada_to_gate


@router.get("/field-team/{team}/schedule/{day}", response_model=List[Dict])
async def get_field_team_gates(team: str, day: str):
    """Get gates assigned to a field team for a specific day"""
    # This integrates with the scheduler service
    # For now, return example based on team
    if team.upper() == "TEAM_A":
        gates = get_gate_registry().get_manual_gates()[:10]  # First 10 manual gates
    else:
        gates = get_gate_registry().get_manual_gates()[10:20]  # Next 10 manual gates
    
    gate_details = []
    for gate_id in gates:
        gate_info = get_gate_registry().get_gate_info(gate_id)
        if gate_info:
            gate_details.append({
                "gate_id": gate_id,
                "name": gate_info["name"],
                "type": gate_info["type"],
                "location": gate_info["location"],
                "physical_markers": gate_info.get("physical_markers", ""),
                "operation_instructions": gate_info.get("manual_operation", {})
            })
    
    return gate_details
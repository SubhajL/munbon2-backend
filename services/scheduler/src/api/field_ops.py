"""
Field Operations API endpoints
Provides instructions and tracking for field teams
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Dict, List, Optional
from datetime import datetime, date
import structlog
import json

from ..schemas.field_ops import (
    FieldInstruction, TeamAssignment, GateOperation,
    OperationReport, TeamLocation, PhotoUpload
)
from ..services.field_ops_service import FieldOpsService
from ..db.connections import DatabaseManager

logger = structlog.get_logger()
router = APIRouter()


def get_field_ops_service() -> FieldOpsService:
    """Dependency to get field ops service instance"""
    from ..main import db_manager
    return FieldOpsService(db_manager)


@router.get("/instructions/{team}", response_model=Dict[str, any])
async def get_field_instructions(
    team: str,
    date: Optional[date] = None,
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """
    Get field operation instructions for a specific team.
    If no date is provided, returns today's instructions.
    """
    try:
        # Default to today if no date provided
        target_date = date or date.today()
        
        # Get instructions
        instructions = await service.get_team_instructions(team, target_date)
        
        if not instructions:
            return {
                "team": team,
                "date": target_date.isoformat(),
                "instructions": [],
                "message": "No operations scheduled for this date"
            }
        
        # Calculate optimal route
        route = await service.calculate_optimal_route(team, instructions)
        
        return {
            "team": team,
            "date": target_date.isoformat(),
            "instructions": instructions,
            "route": route,
            "estimated_duration_hours": route.get("total_duration_hours", 0),
            "total_distance_km": route.get("total_distance_km", 0),
            "weather_advisory": await service.get_weather_advisory(target_date)
        }
        
    except Exception as e:
        logger.error(f"Failed to get field instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve instructions: {str(e)}")


@router.post("/instructions/download/{team}")
async def download_offline_instructions(
    team: str,
    days_ahead: int = 7,
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """
    Download instructions for offline use.
    Returns compressed data package for mobile app.
    """
    try:
        # Generate offline package
        package = await service.generate_offline_package(
            team=team,
            days_ahead=days_ahead
        )
        
        return {
            "team": team,
            "generated_at": datetime.utcnow().isoformat(),
            "days_included": days_ahead,
            "package_size_kb": len(json.dumps(package)) / 1024,
            "data": package,
            "sync_token": package.get("sync_token")
        }
        
    except Exception as e:
        logger.error(f"Failed to generate offline package: {e}")
        raise HTTPException(status_code=500, detail=f"Package generation failed: {str(e)}")


@router.put("/operations/{operation_id}/report")
async def submit_operation_report(
    operation_id: str,
    report: OperationReport,
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """Submit a report for completed gate operation"""
    try:
        # Validate operation exists
        operation = await service.get_operation(operation_id)
        if not operation:
            raise HTTPException(status_code=404, detail=f"Operation {operation_id} not found")
        
        # Store report
        success = await service.submit_operation_report(operation_id, report)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store report")
        
        # Update gate state in flow monitoring service
        if report.actual_opening_m is not None:
            await service.update_gate_state(
                gate_id=operation.gate_id,
                opening_m=report.actual_opening_m,
                operator_id=report.operator_id
            )
        
        return {
            "status": "success",
            "operation_id": operation_id,
            "message": "Operation report submitted successfully",
            "sync_required": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit operation report: {e}")
        raise HTTPException(status_code=500, detail=f"Report submission failed: {str(e)}")


@router.post("/operations/{operation_id}/photo")
async def upload_operation_photo(
    operation_id: str,
    photo: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """Upload photo for gate operation verification"""
    try:
        # Validate file type
        if not photo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Validate file size (max 10MB)
        if photo.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size must be less than 10MB")
        
        # Store photo
        photo_data = PhotoUpload(
            operation_id=operation_id,
            filename=photo.filename,
            content_type=photo.content_type,
            size=photo.size,
            caption=caption,
            latitude=latitude,
            longitude=longitude,
            timestamp=datetime.utcnow()
        )
        
        photo_id = await service.store_operation_photo(
            photo_data,
            await photo.read()
        )
        
        return {
            "status": "success",
            "photo_id": photo_id,
            "operation_id": operation_id,
            "message": "Photo uploaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload photo: {e}")
        raise HTTPException(status_code=500, detail=f"Photo upload failed: {str(e)}")


@router.post("/teams/{team}/location")
async def update_team_location(
    team: str,
    location: TeamLocation,
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """Update current location of field team"""
    try:
        # Store location update
        await service.update_team_location(team, location)
        
        # Check if team is near any assigned gates
        nearby_operations = await service.get_nearby_operations(
            team=team,
            latitude=location.latitude,
            longitude=location.longitude,
            radius_km=1.0
        )
        
        return {
            "status": "success",
            "team": team,
            "location_updated": True,
            "nearby_operations": len(nearby_operations),
            "next_operation": nearby_operations[0] if nearby_operations else None
        }
        
    except Exception as e:
        logger.error(f"Failed to update team location: {e}")
        raise HTTPException(status_code=500, detail=f"Location update failed: {str(e)}")


@router.get("/teams/status")
async def get_all_teams_status(
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """Get current status of all field teams"""
    try:
        teams_status = await service.get_all_teams_status()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "teams": teams_status,
            "active_teams": len([t for t in teams_status if t.get("is_active")]),
            "total_operations_today": sum(t.get("operations_completed", 0) for t in teams_status)
        }
        
    except Exception as e:
        logger.error(f"Failed to get teams status: {e}")
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.post("/sync")
async def sync_field_data(
    sync_data: Dict[str, any],
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """
    Sync offline data from mobile app.
    Handles batch updates from field teams.
    """
    try:
        # Extract sync token
        sync_token = sync_data.get("sync_token")
        if not sync_token:
            raise HTTPException(status_code=400, detail="Sync token required")
        
        # Process sync data
        result = await service.process_sync_data(sync_data)
        
        # Generate new sync token
        new_sync_token = await service.generate_sync_token()
        
        return {
            "status": "success",
            "processed": {
                "reports": result.get("reports_processed", 0),
                "photos": result.get("photos_processed", 0),
                "locations": result.get("locations_processed", 0)
            },
            "conflicts": result.get("conflicts", []),
            "new_sync_token": new_sync_token,
            "server_time": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync field data: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/gates/physical-markers")
async def get_gate_physical_markers(
    service: FieldOpsService = Depends(get_field_ops_service)
):
    """
    Get physical marker mappings for all gates.
    Used by field teams to translate instructions to physical positions.
    """
    try:
        markers = await service.get_all_gate_markers()
        
        return {
            "gates": markers,
            "last_updated": datetime.utcnow().isoformat(),
            "total_gates": len(markers)
        }
        
    except Exception as e:
        logger.error(f"Failed to get gate markers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve markers: {str(e)}")
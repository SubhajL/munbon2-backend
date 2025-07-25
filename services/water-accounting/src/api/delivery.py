"""Delivery completion API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

from ..database import get_db, get_timescale_db
from ..services import WaterAccountingService

router = APIRouter()
accounting_service = WaterAccountingService()

class FlowReading(BaseModel):
    timestamp: str
    flow_rate_m3s: float
    gate_id: Optional[str] = None
    quality: Optional[float] = 1.0

class DeliveryCompletionRequest(BaseModel):
    delivery_id: str
    section_id: str
    scheduled_start: str
    scheduled_end: str
    scheduled_volume_m3: float
    actual_start: str
    actual_end: str
    flow_readings: List[FlowReading]
    consumed_volume_m3: Optional[float] = None
    environmental_conditions: Optional[Dict] = None
    notes: Optional[str] = None

@router.post("/complete")
async def complete_delivery(
    request: DeliveryCompletionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    timescale_db: AsyncSession = Depends(get_timescale_db)
):
    """
    Process a completed water delivery
    
    This endpoint:
    1. Integrates flow readings to calculate delivered volume
    2. Calculates transit losses (seepage, evaporation)
    3. Updates section accounting metrics
    4. Records efficiency data
    5. Triggers deficit tracking if applicable
    """
    try:
        # Convert request to dict for processing
        delivery_data = request.dict()
        
        # Process delivery
        result = await accounting_service.complete_delivery(
            delivery_data,
            db,
            timescale_db
        )
        
        # Schedule background tasks
        background_tasks.add_task(
            notify_delivery_complete,
            result["delivery_id"],
            result["section_id"]
        )
        
        return {
            "status": "success",
            "delivery_id": result["delivery_id"],
            "accounting_summary": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing delivery completion: {str(e)}"
        )

@router.get("/status/{delivery_id}")
async def get_delivery_status(
    delivery_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get status and accounting details for a specific delivery"""
    # Implementation would query delivery record
    return {
        "delivery_id": delivery_id,
        "status": "completed",
        "accounting_complete": True
    }

@router.post("/validate-flow-data")
async def validate_flow_data(flow_readings: List[FlowReading]):
    """
    Validate flow data quality before processing
    
    Checks for:
    - Data completeness
    - Outliers
    - Time gaps
    - Negative values
    """
    try:
        # Convert to dict format
        readings = [r.dict() for r in flow_readings]
        
        # Validate using volume integration service
        validation_result = await accounting_service.volume_service.validate_flow_data(readings)
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating flow data: {str(e)}"
        )

async def notify_delivery_complete(delivery_id: str, section_id: str):
    """Background task to notify other services of delivery completion"""
    # Would integrate with notification service
    # For now, just log
    print(f"Delivery {delivery_id} completed for section {section_id}")
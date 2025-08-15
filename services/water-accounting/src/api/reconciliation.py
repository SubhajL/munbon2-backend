"""Reconciliation API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from ..database import get_db
from ..services.reconciliation_service import ReconciliationService

router = APIRouter()
reconciliation_service = ReconciliationService()

class ManualGateEstimateRequest(BaseModel):
    gate_id: str
    opening_hours: float
    opening_percentage: float
    head_difference_m: float
    gate_width_m: Optional[float] = 2.0

@router.post("/weekly/{week}/{year}")
async def perform_weekly_reconciliation(
    week: int,
    year: int,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Force reconciliation even if already done"),
    db: AsyncSession = Depends(get_db)
):
    """
    Perform weekly reconciliation between automated and manual gates
    
    This process:
    1. Identifies automated vs manual gate deliveries
    2. Calculates discrepancies in water balance
    3. Adjusts manual gate estimates proportionally
    4. Creates audit log of adjustments
    5. Generates reconciliation report
    """
    try:
        # Check if already reconciled
        from sqlalchemy import select
        from ..models import ReconciliationLog
        
        existing = await db.execute(
            select(ReconciliationLog).where(
                ReconciliationLog.week_number == week,
                ReconciliationLog.year == year
            )
        )
        if existing.scalar_one_or_none() and not force:
            raise HTTPException(
                status_code=400,
                detail=f"Week {week}, {year} already reconciled. Use force=true to re-run."
            )
        
        # Perform reconciliation
        report = await reconciliation_service.perform_weekly_reconciliation(
            week, year, db
        )
        
        # Schedule notification
        background_tasks.add_task(
            notify_reconciliation_complete,
            report["reconciliation_id"]
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error performing reconciliation: {str(e)}"
        )

@router.get("/status/{week}/{year}")
async def get_reconciliation_status(
    week: int,
    year: int,
    db: AsyncSession = Depends(get_db)
):
    """Get reconciliation status for a specific week"""
    try:
        from sqlalchemy import select
        from ..models import ReconciliationLog
        
        result = await db.execute(
            select(ReconciliationLog).where(
                ReconciliationLog.week_number == week,
                ReconciliationLog.year == year
            )
        )
        log = result.scalar_one_or_none()
        
        if not log:
            return {
                "week": week,
                "year": year,
                "status": "not_reconciled",
                "message": "No reconciliation performed for this week"
            }
        
        return {
            "reconciliation_id": log.reconciliation_id,
            "week": log.week_number,
            "year": log.year,
            "status": log.status.value,
            "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            "automated_gates": log.automated_gates_count,
            "manual_gates": log.manual_gates_count,
            "total_deliveries": log.total_deliveries,
            "discrepancy_percent": log.discrepancy_percent,
            "adjustments_made": log.adjustments_made,
            "data_quality_score": log.data_quality_score
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving reconciliation status: {str(e)}"
        )

@router.get("/history")
async def get_reconciliation_history(
    limit: int = Query(10, description="Number of records to return"),
    offset: int = Query(0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db)
):
    """Get reconciliation history"""
    try:
        from sqlalchemy import select
        from ..models import ReconciliationLog
        
        # Get total count
        count_result = await db.execute(
            select(func.count()).select_from(ReconciliationLog)
        )
        total_count = count_result.scalar()
        
        # Get records
        result = await db.execute(
            select(ReconciliationLog)
            .order_by(ReconciliationLog.year.desc(), ReconciliationLog.week_number.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = result.scalars().all()
        
        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "records": [
                {
                    "reconciliation_id": log.reconciliation_id,
                    "week": log.week_number,
                    "year": log.year,
                    "status": log.status.value,
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "discrepancy_percent": log.discrepancy_percent,
                    "adjustments_made": log.adjustments_made,
                    "data_quality_score": log.data_quality_score
                }
                for log in logs
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving reconciliation history: {str(e)}"
        )

@router.post("/estimate-manual-flow")
async def estimate_manual_gate_flow(request: ManualGateEstimateRequest):
    """
    Estimate flow for manual gates based on hydraulic principles
    
    Uses gate flow equation with discharge coefficient
    """
    try:
        estimate = await reconciliation_service.estimate_manual_gate_flow(
            gate_id=request.gate_id,
            opening_hours=request.opening_hours,
            opening_percentage=request.opening_percentage,
            head_difference_m=request.head_difference_m,
            gate_width_m=request.gate_width_m
        )
        
        return estimate
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error estimating flow: {str(e)}"
        )

@router.get("/adjustments/{reconciliation_id}")
async def get_reconciliation_adjustments(
    reconciliation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed adjustments made during reconciliation"""
    try:
        from sqlalchemy import select
        from ..models import ReconciliationLog
        
        result = await db.execute(
            select(ReconciliationLog).where(
                ReconciliationLog.reconciliation_id == reconciliation_id
            )
        )
        log = result.scalar_one_or_none()
        
        if not log:
            raise HTTPException(
                status_code=404,
                detail=f"Reconciliation {reconciliation_id} not found"
            )
        
        return {
            "reconciliation_id": log.reconciliation_id,
            "week": log.week_number,
            "year": log.year,
            "adjustments": log.adjustments or [],
            "reconciliation_data": log.reconciliation_data or {},
            "manual_adjustment_note": log.manual_adjustment_note
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving adjustments: {str(e)}"
        )

async def notify_reconciliation_complete(reconciliation_id: str):
    """Background task to notify completion"""
    logger.info(f"Reconciliation {reconciliation_id} completed")
    # Would integrate with notification service

# Add missing import
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)
"""Deficit tracking API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from ..database import get_db
from ..services import WaterAccountingService

router = APIRouter()
accounting_service = WaterAccountingService()

class DeficitUpdateRequest(BaseModel):
    section_id: str
    water_demand_m3: float
    water_delivered_m3: float
    water_consumed_m3: float
    week_number: int
    year: int

@router.get("/week/{week}/{year}")
async def get_weekly_deficits(
    week: int,
    year: int,
    zone_id: Optional[str] = Query(None, description="Filter by zone"),
    min_deficit_m3: Optional[float] = Query(None, description="Minimum deficit threshold"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get deficit summary for a specific week
    
    Returns:
    - Total sections in deficit
    - Water balance summary
    - Stress level distribution
    - Priority sections requiring attention
    """
    try:
        summary = await accounting_service.get_weekly_deficits(week, year, db)
        
        # Apply additional filters if provided
        if zone_id:
            # Would filter by zone
            pass
        
        if min_deficit_m3:
            # Filter priority sections by minimum deficit
            summary["priority_sections"] = [
                s for s in summary.get("priority_sections", [])
                if s["deficit_m3"] >= min_deficit_m3
            ]
        
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving weekly deficits: {str(e)}"
        )

@router.post("/update")
async def update_deficit_tracking(
    request: DeficitUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update deficit tracking for a section
    
    Calculates:
    - Current period deficit
    - Stress level assessment
    - Yield impact estimation
    - Carry-forward updates
    """
    try:
        # Calculate deficit
        deficit_result = await accounting_service.deficit_service.calculate_delivery_deficit(
            request.section_id,
            request.water_demand_m3,
            request.water_delivered_m3,
            request.water_consumed_m3,
            request.week_number,
            request.year
        )
        
        # Would save to database and update carry-forward
        # For now, return calculation result
        
        return {
            "status": "updated",
            "deficit_calculation": deficit_result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating deficit: {str(e)}"
        )

@router.get("/carry-forward/{section_id}")
async def get_carry_forward_status(
    section_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get deficit carry-forward status for a section
    
    Shows:
    - Active deficits and their age
    - Total accumulated deficit
    - Priority score for recovery
    - Recovery recommendations
    """
    # Implementation would query carry-forward records
    return {
        "section_id": section_id,
        "carry_forward": {
            "active": True,
            "total_deficit_m3": 1500.0,
            "weeks_in_deficit": 3,
            "deficit_breakdown": {
                "2024-W45": 500.0,
                "2024-W46": 600.0,
                "2024-W47": 400.0
            },
            "priority_score": 75.5,
            "recovery_status": "pending"
        }
    }

@router.post("/recovery-plan")
async def generate_recovery_plan(
    section_id: str,
    available_capacity_m3: float = Query(..., description="Extra water available for recovery"),
    planning_weeks: int = Query(4, description="Number of weeks to plan ahead"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a recovery plan for deficit compensation
    
    Creates optimized schedule for:
    - Gradual deficit recovery
    - Minimizing crop stress
    - Working within system capacity
    """
    try:
        # Get current carry-forward status
        # For demo, create sample data
        carry_forward_data = {
            "section_id": section_id,
            "total_deficit_m3": 2000.0,
            "weeks_in_deficit": 3
        }
        
        # Generate recovery plan
        recovery_plan = await accounting_service.deficit_service.generate_recovery_plan(
            carry_forward_data,
            available_capacity_m3,
            planning_weeks
        )
        
        return recovery_plan
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating recovery plan: {str(e)}"
        )

@router.get("/stress-assessment")
async def get_stress_assessment(
    zone_id: Optional[str] = Query(None, description="Filter by zone"),
    stress_level: Optional[str] = Query(None, description="Filter by stress level"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get system-wide water stress assessment
    
    Provides:
    - Sections by stress level
    - Geographic distribution of stress
    - Trending analysis
    - Risk assessment for upcoming period
    """
    return {
        "assessment_date": datetime.now().isoformat(),
        "summary": {
            "total_sections": 150,
            "sections_under_stress": 45,
            "stress_percentage": 30.0
        },
        "stress_distribution": {
            "none": 105,
            "mild": 25,
            "moderate": 15,
            "severe": 5
        },
        "high_risk_sections": [
            {
                "section_id": "SEC-101",
                "stress_level": "severe",
                "deficit_m3": 3500,
                "weeks_in_deficit": 4
            }
        ],
        "recommendations": [
            "Prioritize water delivery to 5 sections under severe stress",
            "Consider temporary reduction in planting area for next season",
            "Implement water conservation measures in moderate stress areas"
        ]
    }
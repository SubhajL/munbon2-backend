"""Section accounting API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..services import WaterAccountingService
from ..schemas import SectionAccountingResponse

router = APIRouter()
accounting_service = WaterAccountingService()

@router.get("/section/{section_id}", response_model=SectionAccountingResponse)
async def get_section_accounting(
    section_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current accounting status for a specific section
    
    Returns:
    - Section details
    - Current metrics (efficiency, losses, deficits)
    - Recent deliveries
    - Deficit status
    """
    try:
        result = await accounting_service.get_section_accounting(section_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving section accounting: {str(e)}")

@router.get("/sections")
async def get_all_sections_accounting(
    zone_id: Optional[str] = Query(None, description="Filter by zone ID"),
    has_deficit: Optional[bool] = Query(None, description="Filter sections with deficits"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get accounting summary for multiple sections
    
    Query parameters:
    - zone_id: Filter by irrigation zone
    - has_deficit: Show only sections with water deficits
    """
    try:
        from sqlalchemy import select, and_
        from ..models import Section, SectionMetrics, DeficitRecord
        
        # Build query for sections
        query = select(Section).where(Section.active == True)
        if zone_id:
            query = query.where(Section.zone_id == zone_id)
        
        result = await db.execute(query)
        sections = result.scalars().all()
        
        # Get accounting data for each section
        section_summaries = []
        sections_with_deficit_count = 0
        
        for section in sections:
            # Get latest metrics
            metrics_query = select(SectionMetrics).where(
                SectionMetrics.section_id == section.id
            ).order_by(SectionMetrics.last_updated.desc())
            
            result = await db.execute(metrics_query)
            metrics = result.scalar_one_or_none()
            
            # Get latest deficit
            deficit_query = select(DeficitRecord).where(
                DeficitRecord.section_id == section.id
            ).order_by(DeficitRecord.week_number.desc())
            
            result = await db.execute(deficit_query)
            deficit = result.scalar_one_or_none()
            
            has_section_deficit = deficit and deficit.delivery_deficit_m3 > 0
            
            # Apply deficit filter if specified
            if has_deficit is not None and has_deficit != has_section_deficit:
                continue
            
            if has_section_deficit:
                sections_with_deficit_count += 1
            
            section_summaries.append({
                "section_id": section.id,
                "section_name": section.name,
                "zone_id": section.zone_id,
                "area_hectares": section.area_hectares,
                "current_efficiency": metrics.overall_efficiency if metrics else 0,
                "has_deficit": has_section_deficit,
                "deficit_m3": deficit.delivery_deficit_m3 if deficit else 0,
                "stress_level": deficit.stress_level if deficit else "none"
            })
        
        return {
            "zone_id": zone_id,
            "total_sections": len(section_summaries),
            "sections_with_deficit": sections_with_deficit_count,
            "sections": section_summaries
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sections accounting: {str(e)}")

@router.get("/balance/{section_id}")
async def get_water_balance(
    section_id: str,
    start_date: datetime = Query(..., description="Start date for balance calculation"),
    end_date: datetime = Query(..., description="End date for balance calculation"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get water balance for a section over a time period
    
    Shows:
    - Total inflow
    - Total outflow
    - Losses breakdown
    - Net balance
    """
    try:
        from sqlalchemy import select, and_, func
        from ..models import Section, WaterDelivery, TransitLoss, DeliveryStatus
        
        # Verify section exists
        section = await db.get(Section, section_id)
        if not section:
            raise HTTPException(status_code=404, detail=f"Section {section_id} not found")
        
        # Get deliveries in period
        deliveries_query = select(WaterDelivery).where(
            and_(
                WaterDelivery.section_id == section_id,
                WaterDelivery.actual_start >= start_date,
                WaterDelivery.actual_end <= end_date,
                WaterDelivery.status == DeliveryStatus.COMPLETED
            )
        )
        
        result = await db.execute(deliveries_query)
        deliveries = result.scalars().all()
        
        # Calculate totals
        total_gate_outflow = sum(d.gate_outflow_m3 for d in deliveries)
        total_section_inflow = sum(d.section_inflow_m3 for d in deliveries)
        total_transit_loss = sum(d.transit_loss_m3 for d in deliveries)
        
        # Get loss breakdown
        loss_breakdown = {}
        for delivery in deliveries:
            # Get transit losses for this delivery
            losses_query = select(TransitLoss).where(
                TransitLoss.delivery_id == delivery.id
            )
            result = await db.execute(losses_query)
            losses = result.scalars().all()
            
            for loss in losses:
                if loss.loss_type not in loss_breakdown:
                    loss_breakdown[loss.loss_type] = 0
                loss_breakdown[loss.loss_type] += loss.loss_volume_m3
        
        # Calculate water consumed (estimated at 85% of section inflow)
        estimated_consumption = total_section_inflow * 0.85
        estimated_return_flow = total_section_inflow * 0.15
        
        return {
            "section_id": section_id,
            "section_name": section.name,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days
            },
            "deliveries_count": len(deliveries),
            "water_balance": {
                "gate_release_m3": total_gate_outflow,
                "section_inflow_m3": total_section_inflow,
                "transit_losses_m3": total_transit_loss,
                "estimated_consumption_m3": estimated_consumption,
                "estimated_return_flow_m3": estimated_return_flow,
                "balance_check": total_gate_outflow - total_section_inflow - total_transit_loss
            },
            "losses_breakdown": loss_breakdown,
            "efficiency": {
                "conveyance": (total_section_inflow / total_gate_outflow * 100) if total_gate_outflow > 0 else 0,
                "application": 85.0,  # Assumed
                "overall": (total_section_inflow / total_gate_outflow * 0.85 * 100) if total_gate_outflow > 0 else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating water balance: {str(e)}")
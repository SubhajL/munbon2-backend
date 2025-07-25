"""Main water accounting service orchestrator"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging
import httpx

from ..models import (
    Section, SectionMetrics, WaterDelivery, DeliveryStatus,
    EfficiencyRecord, DeficitRecord, TransitLoss
)
from .volume_integration import VolumeIntegrationService
from .loss_calculation import LossCalculationService
from .efficiency_calculator import EfficiencyCalculator
from .deficit_tracker import DeficitTracker
from ..config import get_settings

logger = logging.getLogger(__name__)

class WaterAccountingService:
    """Main service for water accounting operations"""
    
    def __init__(self):
        self.settings = get_settings()
        self.volume_service = VolumeIntegrationService()
        self.loss_service = LossCalculationService()
        self.efficiency_service = EfficiencyCalculator()
        self.deficit_service = DeficitTracker(
            carry_forward_weeks=self.settings.DEFICIT_CARRY_FORWARD_WEEKS
        )
    
    async def get_section_accounting(
        self,
        section_id: str,
        db: AsyncSession
    ) -> Dict:
        """
        Get current accounting status for a section
        
        Args:
            section_id: Section identifier
            db: Database session
            
        Returns:
            Dict with section accounting data
        """
        # Get section data
        section = await db.get(Section, section_id)
        if not section:
            raise ValueError(f"Section {section_id} not found")
        
        # Get current metrics
        metrics_query = select(SectionMetrics).where(
            SectionMetrics.section_id == section_id
        ).order_by(SectionMetrics.last_updated.desc())
        
        result = await db.execute(metrics_query)
        current_metrics = result.scalar_one_or_none()
        
        # Get recent deliveries
        deliveries_query = select(WaterDelivery).where(
            and_(
                WaterDelivery.section_id == section_id,
                WaterDelivery.actual_start >= datetime.now() - timedelta(days=7)
            )
        ).order_by(WaterDelivery.actual_start.desc())
        
        result = await db.execute(deliveries_query)
        recent_deliveries = result.scalars().all()
        
        # Get active deficit
        deficit_query = select(DeficitRecord).where(
            DeficitRecord.section_id == section_id
        ).order_by(DeficitRecord.week_number.desc())
        
        result = await db.execute(deficit_query)
        latest_deficit = result.scalar_one_or_none()
        
        return {
            "section": {
                "id": section.id,
                "name": section.name,
                "area_hectares": section.area_hectares,
                "primary_crop": section.primary_crop,
                "crop_stage": section.crop_stage
            },
            "current_metrics": {
                "total_delivered_m3": current_metrics.total_delivered_m3 if current_metrics else 0,
                "total_losses_m3": current_metrics.total_losses_m3 if current_metrics else 0,
                "delivery_efficiency": current_metrics.delivery_efficiency if current_metrics else 0,
                "application_efficiency": current_metrics.application_efficiency if current_metrics else 0,
                "overall_efficiency": current_metrics.overall_efficiency if current_metrics else 0,
                "current_deficit_m3": current_metrics.current_deficit_m3 if current_metrics else 0
            } if current_metrics else None,
            "recent_deliveries": [
                {
                    "delivery_id": d.delivery_id,
                    "scheduled_start": d.scheduled_start.isoformat(),
                    "actual_start": d.actual_start.isoformat() if d.actual_start else None,
                    "status": d.status.value,
                    "gate_outflow_m3": d.gate_outflow_m3,
                    "section_inflow_m3": d.section_inflow_m3,
                    "transit_loss_m3": d.transit_loss_m3
                }
                for d in recent_deliveries
            ],
            "deficit_status": {
                "has_deficit": latest_deficit and latest_deficit.delivery_deficit_m3 > 0,
                "deficit_m3": latest_deficit.delivery_deficit_m3 if latest_deficit else 0,
                "stress_level": latest_deficit.stress_level if latest_deficit else "none",
                "weeks_in_deficit": latest_deficit.deficit_age_weeks if latest_deficit else 0
            } if latest_deficit else None
        }
    
    async def complete_delivery(
        self,
        delivery_data: Dict,
        db: AsyncSession,
        timescale_db: AsyncSession
    ) -> Dict:
        """
        Process a completed water delivery
        
        Args:
            delivery_data: Delivery completion data
            db: Main database session
            timescale_db: TimescaleDB session
            
        Returns:
            Dict with processing results
        """
        delivery_id = delivery_data["delivery_id"]
        section_id = delivery_data["section_id"]
        
        # Get or create delivery record
        delivery = await db.execute(
            select(WaterDelivery).where(WaterDelivery.delivery_id == delivery_id)
        )
        delivery = delivery.scalar_one_or_none()
        
        if not delivery:
            # Create new delivery record
            delivery = WaterDelivery(
                delivery_id=delivery_id,
                section_id=section_id,
                scheduled_start=datetime.fromisoformat(delivery_data["scheduled_start"]),
                scheduled_end=datetime.fromisoformat(delivery_data["scheduled_end"]),
                scheduled_volume_m3=delivery_data["scheduled_volume_m3"]
            )
            db.add(delivery)
        
        # Update with actual data
        delivery.actual_start = datetime.fromisoformat(delivery_data["actual_start"])
        delivery.actual_end = datetime.fromisoformat(delivery_data["actual_end"])
        delivery.flow_readings = delivery_data["flow_readings"]
        delivery.status = DeliveryStatus.COMPLETED
        
        # Calculate volumes using integration
        volume_result = await self.volume_service.integrate_flow_to_volume(
            delivery_data["flow_readings"],
            method="trapezoidal"
        )
        
        delivery.gate_outflow_m3 = volume_result["total_volume_m3"]
        
        # Get canal characteristics
        section = await db.get(Section, section_id)
        canal_characteristics = {
            "length_km": section.canal_length_km,
            "type": section.canal_type,
            "width_m": 5.0,  # Default, should come from actual data
            "water_depth_m": 1.0  # Default
        }
        
        # Calculate losses
        flow_data = {
            "flow_rate_m3s": volume_result["integration_details"]["avg_flow_rate_m3s"],
            "transit_time_hours": volume_result["integration_details"]["duration_hours"],
            "volume_m3": volume_result["total_volume_m3"]
        }
        
        environmental_conditions = delivery_data.get("environmental_conditions", {
            "temperature_c": 30,
            "humidity_percent": 60,
            "wind_speed_ms": 2
        })
        
        loss_result = await self.loss_service.calculate_transit_losses(
            flow_data, canal_characteristics, environmental_conditions
        )
        
        delivery.transit_loss_m3 = loss_result["total_loss_m3"]
        delivery.section_inflow_m3 = delivery.gate_outflow_m3 - delivery.transit_loss_m3
        
        # Create loss records
        for loss_type, loss_m3 in loss_result["breakdown"].items():
            if loss_m3 > 0:
                transit_loss = TransitLoss(
                    delivery_id=delivery.id,
                    loss_type=loss_type,
                    loss_volume_m3=loss_m3,
                    loss_percentage=(loss_m3 / delivery.gate_outflow_m3 * 100) if delivery.gate_outflow_m3 > 0 else 0,
                    calculation_method="model",
                    confidence_level=0.8
                )
                db.add(transit_loss)
        
        # Calculate efficiency
        efficiency_result = await self.efficiency_service.calculate_delivery_efficiency(
            delivery.gate_outflow_m3,
            delivery.section_inflow_m3,
            delivery.transit_loss_m3
        )
        
        # Create efficiency record
        efficiency_record = EfficiencyRecord(
            section_id=section_id,
            delivery_id=delivery_id,
            delivered_volume_m3=delivery.gate_outflow_m3,
            applied_volume_m3=delivery.section_inflow_m3,
            consumed_volume_m3=delivery_data.get("consumed_volume_m3", delivery.section_inflow_m3 * 0.85),
            conveyance_efficiency=efficiency_result["delivery_efficiency"],
            period_start=delivery.actual_start,
            period_end=delivery.actual_end
        )
        db.add(efficiency_record)
        
        # Update section metrics
        await self._update_section_metrics(section_id, delivery, efficiency_result, db)
        
        # Store time-series data in TimescaleDB
        await self._store_flow_measurements(
            section_id, delivery_data["flow_readings"], timescale_db
        )
        
        await db.commit()
        
        return {
            "delivery_id": delivery_id,
            "section_id": section_id,
            "status": "completed",
            "volumes": {
                "gate_outflow_m3": delivery.gate_outflow_m3,
                "section_inflow_m3": delivery.section_inflow_m3,
                "transit_loss_m3": delivery.transit_loss_m3
            },
            "efficiency": efficiency_result,
            "integration_details": volume_result["integration_details"]
        }
    
    async def generate_efficiency_report(
        self,
        zone_id: Optional[str],
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> Dict:
        """
        Generate efficiency report for a zone or all sections
        
        Args:
            zone_id: Optional zone filter
            start_date: Report start date
            end_date: Report end date
            db: Database session
            
        Returns:
            Dict with efficiency report
        """
        # Get sections
        query = select(Section).where(Section.active == True)
        if zone_id:
            query = query.where(Section.zone_id == zone_id)
        
        result = await db.execute(query)
        sections = result.scalars().all()
        
        # Collect metrics for each section
        sections_metrics = []
        
        for section in sections:
            # Get deliveries in period
            deliveries_query = select(WaterDelivery).where(
                and_(
                    WaterDelivery.section_id == section.id,
                    WaterDelivery.actual_start >= start_date,
                    WaterDelivery.actual_end <= end_date,
                    WaterDelivery.status == DeliveryStatus.COMPLETED
                )
            )
            
            result = await db.execute(deliveries_query)
            deliveries = result.scalars().all()
            
            if deliveries:
                delivery_data = [
                    {
                        "gate_outflow_m3": d.gate_outflow_m3,
                        "section_inflow_m3": d.section_inflow_m3,
                        "transit_loss_m3": d.transit_loss_m3,
                        "water_consumed_m3": d.section_inflow_m3 * 0.85  # Estimate
                    }
                    for d in deliveries
                ]
                
                section_metrics = await self.efficiency_service.calculate_section_efficiency_metrics(
                    {"id": section.id, "name": section.name},
                    delivery_data,
                    (start_date, end_date)
                )
                
                sections_metrics.append(section_metrics)
        
        # Generate report
        report = await self.efficiency_service.generate_efficiency_report(
            sections_metrics,
            (start_date, end_date),
            zone_id
        )
        
        return report
    
    async def get_weekly_deficits(
        self,
        week_number: int,
        year: int,
        db: AsyncSession
    ) -> Dict:
        """
        Get deficit summary for a specific week
        
        Args:
            week_number: Week of year
            year: Year
            db: Database session
            
        Returns:
            Dict with weekly deficit summary
        """
        # Get all deficit records for the week
        query = select(DeficitRecord).where(
            and_(
                DeficitRecord.week_number == week_number,
                DeficitRecord.year == year
            )
        )
        
        result = await db.execute(query)
        deficits = result.scalars().all()
        
        # Convert to dicts for processing
        deficit_dicts = [
            {
                "section_id": d.section_id,
                "week_number": d.week_number,
                "year": d.year,
                "water_demand_m3": d.water_demand_m3,
                "water_delivered_m3": d.water_delivered_m3,
                "delivery_deficit_m3": d.delivery_deficit_m3,
                "deficit_percentage": d.deficit_percentage,
                "stress_level": d.stress_level,
                "estimated_yield_impact": d.estimated_yield_impact
            }
            for d in deficits
        ]
        
        # Generate summary
        summary = await self.deficit_service.get_deficit_summary_by_week(
            week_number, year, deficit_dicts
        )
        
        return summary
    
    async def _update_section_metrics(
        self,
        section_id: str,
        delivery: WaterDelivery,
        efficiency_result: Dict,
        db: AsyncSession
    ):
        """Update section metrics with new delivery data"""
        
        # Get or create metrics
        metrics = await db.execute(
            select(SectionMetrics).where(
                SectionMetrics.section_id == section_id
            ).order_by(SectionMetrics.last_updated.desc())
        )
        metrics = metrics.scalar_one_or_none()
        
        if not metrics or metrics.period_end < datetime.now() - timedelta(days=7):
            # Create new metrics period
            metrics = SectionMetrics(
                section_id=section_id,
                period_start=datetime.now().replace(hour=0, minute=0, second=0),
                period_end=datetime.now().replace(hour=23, minute=59, second=59) + timedelta(days=6)
            )
            db.add(metrics)
        
        # Update cumulative values
        metrics.total_delivered_m3 += delivery.gate_outflow_m3
        metrics.total_losses_m3 += delivery.transit_loss_m3
        metrics.total_applied_m3 += delivery.section_inflow_m3
        
        # Recalculate efficiencies
        if metrics.total_delivered_m3 > 0:
            metrics.delivery_efficiency = (
                metrics.total_applied_m3 / metrics.total_delivered_m3
            )
            metrics.overall_efficiency = metrics.delivery_efficiency * 0.85  # Assumed application efficiency
        
        metrics.last_updated = datetime.now()
    
    async def _store_flow_measurements(
        self,
        section_id: str,
        flow_readings: List[Dict],
        timescale_db: AsyncSession
    ):
        """Store flow measurements in TimescaleDB"""
        
        for reading in flow_readings:
            await timescale_db.execute(
                """
                INSERT INTO flow_measurements 
                (time, gate_id, section_id, flow_rate_m3s, measurement_quality)
                VALUES (:time, :gate_id, :section_id, :flow_rate, :quality)
                """,
                {
                    "time": reading["timestamp"],
                    "gate_id": reading.get("gate_id", "unknown"),
                    "section_id": section_id,
                    "flow_rate": reading["flow_rate_m3s"],
                    "quality": reading.get("quality", 1.0)
                }
            )
        
        await timescale_db.commit()
"""Weekly reconciliation service for automated and manual gates"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import asyncio
from enum import Enum

from ..models import (
    WaterDelivery, Section, ReconciliationLog, ReconciliationStatus,
    DeliveryStatus, TransitLoss
)
from .external_clients import ServiceClientManager
from ..config import get_settings

logger = logging.getLogger(__name__)

class DataSource(Enum):
    """Data source types for reconciliation"""
    AUTOMATED = "automated"
    MANUAL = "manual"
    ESTIMATED = "estimated"

class ReconciliationService:
    """Service for reconciling water accounting data between automated and manual gates"""
    
    def __init__(self):
        self.settings = get_settings()
        self.service_clients = ServiceClientManager()
        self.automated_gate_threshold = 0.95  # 95% confidence for automated gates
        self.manual_gate_threshold = 0.70     # 70% confidence for manual gates
    
    async def perform_weekly_reconciliation(
        self,
        week_number: int,
        year: int,
        db: AsyncSession
    ) -> Dict:
        """
        Perform weekly reconciliation of water deliveries
        
        Process:
        1. Identify automated vs manual gates
        2. Calculate total outflows and inflows
        3. Identify discrepancies
        4. Adjust manual gate estimates
        5. Generate reconciliation report
        """
        logger.info(f"Starting reconciliation for Week {week_number}, {year}")
        
        # Get automated gates list
        automated_gates = await self.service_clients.scada_client.get_automated_gates_list()
        
        # Get week date range
        week_start, week_end = self._get_week_dates(year, week_number)
        
        # Get all deliveries for the week
        deliveries = await self._get_week_deliveries(week_start, week_end, db)
        
        # Separate automated and manual gate deliveries
        automated_deliveries = []
        manual_deliveries = []
        
        for delivery in deliveries:
            if delivery.gate_id in automated_gates:
                automated_deliveries.append(delivery)
            else:
                manual_deliveries.append(delivery)
        
        # Calculate totals and identify discrepancies
        reconciliation_data = await self._calculate_reconciliation(
            automated_deliveries,
            manual_deliveries,
            db
        )
        
        # Adjust manual gate estimates if needed
        adjustments = await self._calculate_adjustments(
            reconciliation_data,
            manual_deliveries
        )
        
        # Apply adjustments
        if adjustments:
            await self._apply_adjustments(adjustments, db)
        
        # Create reconciliation log
        reconciliation_log = await self._create_reconciliation_log(
            week_number,
            year,
            reconciliation_data,
            adjustments,
            db
        )
        
        # Generate report
        report = await self._generate_reconciliation_report(
            reconciliation_log,
            reconciliation_data,
            adjustments
        )
        
        await db.commit()
        
        return report
    
    async def estimate_manual_gate_flow(
        self,
        gate_id: str,
        opening_hours: float,
        opening_percentage: float,
        head_difference_m: float,
        gate_width_m: float = 2.0
    ) -> Dict:
        """
        Estimate flow for manual gates based on hydraulic principles
        
        Uses simplified gate flow equation:
        Q = Cd * A * sqrt(2 * g * h)
        """
        # Discharge coefficient (depends on gate type)
        Cd = 0.6  # Typical for sluice gates
        
        # Gate opening area
        opening_height_m = gate_width_m * (opening_percentage / 100)
        area_m2 = gate_width_m * opening_height_m
        
        # Flow rate calculation
        g = 9.81  # gravity
        flow_rate_m3s = Cd * area_m2 * (2 * g * head_difference_m) ** 0.5
        
        # Total volume
        total_volume_m3 = flow_rate_m3s * opening_hours * 3600
        
        # Uncertainty based on estimation method
        uncertainty_percent = 25  # ±25% for manual estimates
        
        return {
            "gate_id": gate_id,
            "estimated_flow_rate_m3s": flow_rate_m3s,
            "estimated_volume_m3": total_volume_m3,
            "confidence_level": 0.75,
            "uncertainty_percent": uncertainty_percent,
            "calculation_method": "hydraulic_equation",
            "parameters": {
                "discharge_coefficient": Cd,
                "gate_width_m": gate_width_m,
                "opening_percentage": opening_percentage,
                "head_difference_m": head_difference_m,
                "duration_hours": opening_hours
            }
        }
    
    async def validate_delivery_data(
        self,
        delivery: WaterDelivery,
        data_source: DataSource
    ) -> Dict:
        """Validate delivery data quality and assign confidence level"""
        
        issues = []
        confidence = 1.0
        
        # Check data completeness
        if not delivery.flow_readings:
            issues.append("No flow readings")
            confidence *= 0.5
        else:
            # Check for data gaps
            readings = sorted(delivery.flow_readings, key=lambda x: x["timestamp"])
            for i in range(1, len(readings)):
                time_gap = (
                    datetime.fromisoformat(readings[i]["timestamp"]) -
                    datetime.fromisoformat(readings[i-1]["timestamp"])
                ).total_seconds() / 60  # minutes
                
                if time_gap > 30:  # More than 30 minutes gap
                    issues.append(f"Data gap of {time_gap:.0f} minutes")
                    confidence *= 0.9
        
        # Check volume consistency
        if delivery.gate_outflow_m3 and delivery.scheduled_volume_m3:
            variance = abs(delivery.gate_outflow_m3 - delivery.scheduled_volume_m3) / delivery.scheduled_volume_m3
            if variance > 0.2:  # More than 20% variance
                issues.append(f"Volume variance: {variance:.1%}")
                confidence *= 0.8
        
        # Apply data source confidence
        if data_source == DataSource.AUTOMATED:
            confidence *= self.automated_gate_threshold
        elif data_source == DataSource.MANUAL:
            confidence *= self.manual_gate_threshold
        else:
            confidence *= 0.5
        
        return {
            "delivery_id": delivery.delivery_id,
            "data_source": data_source.value,
            "confidence_level": confidence,
            "validation_issues": issues,
            "is_valid": confidence > 0.6
        }
    
    async def _calculate_reconciliation(
        self,
        automated_deliveries: List[WaterDelivery],
        manual_deliveries: List[WaterDelivery],
        db: AsyncSession
    ) -> Dict:
        """Calculate reconciliation between total outflows and inflows"""
        
        # Calculate automated totals (high confidence)
        automated_outflow = sum(d.gate_outflow_m3 for d in automated_deliveries)
        automated_inflow = sum(d.section_inflow_m3 for d in automated_deliveries)
        automated_losses = sum(d.transit_loss_m3 for d in automated_deliveries)
        
        # Calculate manual totals (lower confidence)
        manual_outflow = sum(d.gate_outflow_m3 for d in manual_deliveries)
        manual_inflow = sum(d.section_inflow_m3 for d in manual_deliveries)
        manual_losses = sum(d.transit_loss_m3 for d in manual_deliveries)
        
        # Total system values
        total_outflow = automated_outflow + manual_outflow
        total_inflow = automated_inflow + manual_inflow
        total_losses = automated_losses + manual_losses
        
        # Calculate expected vs actual
        expected_losses = total_outflow - total_inflow
        loss_discrepancy = expected_losses - total_losses
        discrepancy_percent = (loss_discrepancy / total_outflow * 100) if total_outflow > 0 else 0
        
        # Determine if adjustment needed (>5% discrepancy)
        needs_adjustment = abs(discrepancy_percent) > 5
        
        return {
            "automated": {
                "gate_count": len(set(d.gate_id for d in automated_deliveries)),
                "delivery_count": len(automated_deliveries),
                "total_outflow_m3": automated_outflow,
                "total_inflow_m3": automated_inflow,
                "total_losses_m3": automated_losses,
                "avg_efficiency": (automated_inflow / automated_outflow) if automated_outflow > 0 else 0
            },
            "manual": {
                "gate_count": len(set(d.gate_id for d in manual_deliveries)),
                "delivery_count": len(manual_deliveries),
                "total_outflow_m3": manual_outflow,
                "total_inflow_m3": manual_inflow,
                "total_losses_m3": manual_losses,
                "avg_efficiency": (manual_inflow / manual_outflow) if manual_outflow > 0 else 0
            },
            "system_total": {
                "total_outflow_m3": total_outflow,
                "total_inflow_m3": total_inflow,
                "total_losses_m3": total_losses,
                "expected_losses_m3": expected_losses,
                "loss_discrepancy_m3": loss_discrepancy,
                "discrepancy_percent": discrepancy_percent,
                "needs_adjustment": needs_adjustment
            }
        }
    
    async def _calculate_adjustments(
        self,
        reconciliation_data: Dict,
        manual_deliveries: List[WaterDelivery]
    ) -> List[Dict]:
        """Calculate adjustments for manual gate estimates"""
        
        if not reconciliation_data["system_total"]["needs_adjustment"]:
            return []
        
        adjustments = []
        discrepancy = reconciliation_data["system_total"]["loss_discrepancy_m3"]
        
        # Distribute discrepancy proportionally among manual gates
        manual_total = reconciliation_data["manual"]["total_outflow_m3"]
        
        if manual_total > 0:
            for delivery in manual_deliveries:
                # Calculate proportional adjustment
                proportion = delivery.gate_outflow_m3 / manual_total
                adjustment_m3 = discrepancy * proportion
                
                # Calculate adjusted values
                adjusted_outflow = delivery.gate_outflow_m3 + adjustment_m3
                adjusted_losses = delivery.transit_loss_m3 + (adjustment_m3 * 0.2)  # Assume 20% is losses
                adjusted_inflow = adjusted_outflow - adjusted_losses
                
                adjustments.append({
                    "delivery_id": delivery.delivery_id,
                    "original_outflow_m3": delivery.gate_outflow_m3,
                    "adjusted_outflow_m3": adjusted_outflow,
                    "adjustment_m3": adjustment_m3,
                    "adjustment_percent": (adjustment_m3 / delivery.gate_outflow_m3 * 100) if delivery.gate_outflow_m3 > 0 else 0,
                    "adjusted_losses_m3": adjusted_losses,
                    "adjusted_inflow_m3": adjusted_inflow,
                    "reason": "Weekly reconciliation adjustment"
                })
        
        return adjustments
    
    async def _apply_adjustments(
        self,
        adjustments: List[Dict],
        db: AsyncSession
    ):
        """Apply reconciliation adjustments to deliveries"""
        
        for adjustment in adjustments:
            # Get delivery
            result = await db.execute(
                select(WaterDelivery).where(
                    WaterDelivery.delivery_id == adjustment["delivery_id"]
                )
            )
            delivery = result.scalar_one_or_none()
            
            if delivery:
                # Store original values
                delivery.pre_reconciliation_outflow = delivery.gate_outflow_m3
                delivery.pre_reconciliation_inflow = delivery.section_inflow_m3
                
                # Apply adjustments
                delivery.gate_outflow_m3 = adjustment["adjusted_outflow_m3"]
                delivery.section_inflow_m3 = adjustment["adjusted_inflow_m3"]
                delivery.transit_loss_m3 = adjustment["adjusted_losses_m3"]
                delivery.reconciliation_adjusted = True
                delivery.reconciliation_note = adjustment["reason"]
    
    async def _create_reconciliation_log(
        self,
        week_number: int,
        year: int,
        reconciliation_data: Dict,
        adjustments: List[Dict],
        db: AsyncSession
    ) -> ReconciliationLog:
        """Create reconciliation log entry"""
        
        log = ReconciliationLog(
            reconciliation_id=f"REC-{year}-W{week_number:02d}",
            week_number=week_number,
            year=year,
            status=ReconciliationStatus.COMPLETED if not adjustments else ReconciliationStatus.ADJUSTED,
            automated_gates_count=reconciliation_data["automated"]["gate_count"],
            manual_gates_count=reconciliation_data["manual"]["gate_count"],
            total_deliveries=reconciliation_data["automated"]["delivery_count"] + reconciliation_data["manual"]["delivery_count"],
            automated_confidence=self.automated_gate_threshold,
            manual_confidence=self.manual_gate_threshold,
            discrepancy_m3=reconciliation_data["system_total"]["loss_discrepancy_m3"],
            discrepancy_percent=reconciliation_data["system_total"]["discrepancy_percent"],
            adjustments_made=len(adjustments),
            data_quality_score=self._calculate_data_quality_score(reconciliation_data),
            reconciliation_data=reconciliation_data,
            adjustments=adjustments
        )
        
        db.add(log)
        return log
    
    async def _generate_reconciliation_report(
        self,
        log: ReconciliationLog,
        reconciliation_data: Dict,
        adjustments: List[Dict]
    ) -> Dict:
        """Generate comprehensive reconciliation report"""
        
        return {
            "reconciliation_id": log.reconciliation_id,
            "week": log.week_number,
            "year": log.year,
            "status": log.status.value,
            "summary": {
                "automated_gates": reconciliation_data["automated"]["gate_count"],
                "manual_gates": reconciliation_data["manual"]["gate_count"],
                "total_deliveries": log.total_deliveries,
                "data_quality_score": log.data_quality_score
            },
            "water_balance": {
                "total_outflow_m3": reconciliation_data["system_total"]["total_outflow_m3"],
                "total_inflow_m3": reconciliation_data["system_total"]["total_inflow_m3"],
                "total_losses_m3": reconciliation_data["system_total"]["total_losses_m3"],
                "discrepancy_m3": reconciliation_data["system_total"]["loss_discrepancy_m3"],
                "discrepancy_percent": reconciliation_data["system_total"]["discrepancy_percent"]
            },
            "automated_gates_summary": reconciliation_data["automated"],
            "manual_gates_summary": reconciliation_data["manual"],
            "adjustments": {
                "required": len(adjustments) > 0,
                "count": len(adjustments),
                "total_adjustment_m3": sum(a["adjustment_m3"] for a in adjustments),
                "details": adjustments[:10]  # Top 10 adjustments
            },
            "recommendations": self._generate_recommendations(reconciliation_data, adjustments),
            "generated_at": datetime.now().isoformat()
        }
    
    def _get_week_dates(self, year: int, week: int) -> Tuple[datetime, datetime]:
        """Get start and end dates for a week"""
        jan1 = datetime(year, 1, 1)
        week_start = jan1 + timedelta(weeks=week - 1)
        week_start -= timedelta(days=week_start.weekday())  # Monday
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return week_start, week_end
    
    async def _get_week_deliveries(
        self,
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession
    ) -> List[WaterDelivery]:
        """Get all completed deliveries for the week"""
        
        result = await db.execute(
            select(WaterDelivery).where(
                and_(
                    WaterDelivery.actual_start >= start_date,
                    WaterDelivery.actual_end <= end_date,
                    WaterDelivery.status == DeliveryStatus.COMPLETED
                )
            )
        )
        return result.scalars().all()
    
    def _calculate_data_quality_score(self, reconciliation_data: Dict) -> float:
        """Calculate overall data quality score"""
        
        # Weighted scoring
        automated_weight = 0.7
        manual_weight = 0.3
        
        # Automated gates score (based on efficiency consistency)
        automated_score = min(reconciliation_data["automated"]["avg_efficiency"] / 0.8, 1.0)
        
        # Manual gates score (based on discrepancy)
        discrepancy_impact = abs(reconciliation_data["system_total"]["discrepancy_percent"]) / 100
        manual_score = max(1 - discrepancy_impact, 0)
        
        # Combined score
        quality_score = (automated_score * automated_weight + manual_score * manual_weight) * 100
        
        return round(quality_score, 1)
    
    def _generate_recommendations(
        self,
        reconciliation_data: Dict,
        adjustments: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on reconciliation results"""
        
        recommendations = []
        
        # Check discrepancy level
        discrepancy = abs(reconciliation_data["system_total"]["discrepancy_percent"])
        if discrepancy > 10:
            recommendations.append(
                f"High discrepancy ({discrepancy:.1f}%) detected. "
                "Consider installing flow meters at high-volume manual gates."
            )
        
        # Check manual gate efficiency
        manual_efficiency = reconciliation_data["manual"]["avg_efficiency"]
        if manual_efficiency < 0.7:
            recommendations.append(
                f"Manual gates showing low efficiency ({manual_efficiency:.1%}). "
                "Review canal maintenance and gate operation procedures."
            )
        
        # Check adjustment patterns
        if adjustments:
            avg_adjustment = sum(abs(a["adjustment_percent"]) for a in adjustments) / len(adjustments)
            if avg_adjustment > 15:
                recommendations.append(
                    "Large adjustments required for manual gates. "
                    "Consider more frequent manual flow measurements."
                )
        
        # Data quality recommendations
        if reconciliation_data["manual"]["delivery_count"] > reconciliation_data["automated"]["delivery_count"] * 2:
            recommendations.append(
                "Majority of deliveries through manual gates. "
                "Prioritize automation of high-usage gates for better accuracy."
            )
        
        return recommendations
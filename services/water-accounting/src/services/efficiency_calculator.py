"""Efficiency calculation service for water delivery and application"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import statistics

logger = logging.getLogger(__name__)

class EfficiencyCalculator:
    """Service for calculating water delivery and application efficiencies"""
    
    def __init__(self):
        self.efficiency_thresholds = {
            "excellent": 0.85,
            "good": 0.75,
            "fair": 0.65,
            "poor": 0.55
        }
    
    async def calculate_delivery_efficiency(
        self,
        gate_outflow_m3: float,
        section_inflow_m3: float,
        transit_losses_m3: Optional[float] = None
    ) -> Dict:
        """
        Calculate conveyance/delivery efficiency
        
        Efficiency = Water delivered to section / Water released from gate
        
        Args:
            gate_outflow_m3: Volume released at gate
            section_inflow_m3: Volume reaching section
            transit_losses_m3: Optional pre-calculated losses
            
        Returns:
            Dict with efficiency metrics
        """
        if gate_outflow_m3 <= 0:
            return {
                "delivery_efficiency": 0.0,
                "classification": "no_delivery",
                "losses_m3": 0.0,
                "loss_percentage": 0.0
            }
        
        # Calculate efficiency
        efficiency = section_inflow_m3 / gate_outflow_m3
        efficiency = min(1.0, max(0.0, efficiency))  # Bound between 0 and 1
        
        # Calculate losses
        if transit_losses_m3 is not None:
            losses_m3 = transit_losses_m3
        else:
            losses_m3 = gate_outflow_m3 - section_inflow_m3
        
        loss_percentage = (losses_m3 / gate_outflow_m3 * 100) if gate_outflow_m3 > 0 else 0
        
        # Classify efficiency
        classification = self._classify_efficiency(efficiency)
        
        return {
            "delivery_efficiency": efficiency,
            "classification": classification,
            "losses_m3": losses_m3,
            "loss_percentage": loss_percentage,
            "gate_outflow_m3": gate_outflow_m3,
            "section_inflow_m3": section_inflow_m3
        }
    
    async def calculate_application_efficiency(
        self,
        water_applied_m3: float,
        water_consumed_m3: float,
        return_flow_m3: float = 0.0
    ) -> Dict:
        """
        Calculate field application efficiency
        
        Efficiency = Water consumed by crop / Water applied to field
        
        Args:
            water_applied_m3: Water applied to field
            water_consumed_m3: Water actually used by crop
            return_flow_m3: Return flow/runoff
            
        Returns:
            Dict with efficiency metrics
        """
        if water_applied_m3 <= 0:
            return {
                "application_efficiency": 0.0,
                "classification": "no_application",
                "wastage_m3": 0.0,
                "return_flow_percentage": 0.0
            }
        
        # Calculate efficiency
        efficiency = water_consumed_m3 / water_applied_m3
        efficiency = min(1.0, max(0.0, efficiency))
        
        # Calculate wastage
        wastage_m3 = water_applied_m3 - water_consumed_m3 - return_flow_m3
        return_flow_percentage = (return_flow_m3 / water_applied_m3 * 100) if water_applied_m3 > 0 else 0
        
        # Classify efficiency
        classification = self._classify_efficiency(efficiency)
        
        return {
            "application_efficiency": efficiency,
            "classification": classification,
            "wastage_m3": wastage_m3,
            "return_flow_m3": return_flow_m3,
            "return_flow_percentage": return_flow_percentage,
            "water_applied_m3": water_applied_m3,
            "water_consumed_m3": water_consumed_m3
        }
    
    async def calculate_overall_efficiency(
        self,
        delivery_efficiency: float,
        application_efficiency: float
    ) -> Dict:
        """
        Calculate overall system efficiency
        
        Overall = Delivery efficiency × Application efficiency
        """
        overall = delivery_efficiency * application_efficiency
        classification = self._classify_efficiency(overall)
        
        # Identify limiting factor
        if delivery_efficiency < application_efficiency:
            limiting_factor = "delivery"
            improvement_potential = application_efficiency - delivery_efficiency
        else:
            limiting_factor = "application"
            improvement_potential = delivery_efficiency - application_efficiency
        
        return {
            "overall_efficiency": overall,
            "classification": classification,
            "delivery_efficiency": delivery_efficiency,
            "application_efficiency": application_efficiency,
            "limiting_factor": limiting_factor,
            "improvement_potential": improvement_potential
        }
    
    async def calculate_section_efficiency_metrics(
        self,
        section_data: Dict,
        delivery_data: List[Dict],
        time_period: Tuple[datetime, datetime]
    ) -> Dict:
        """
        Calculate comprehensive efficiency metrics for a section
        
        Args:
            section_data: Section information
            delivery_data: List of deliveries in period
            time_period: Start and end dates
            
        Returns:
            Dict with comprehensive metrics
        """
        if not delivery_data:
            return {
                "section_id": section_data["id"],
                "period": {
                    "start": time_period[0].isoformat(),
                    "end": time_period[1].isoformat()
                },
                "no_deliveries": True,
                "metrics": {}
            }
        
        # Aggregate volumes
        total_gate_outflow = sum(d.get("gate_outflow_m3", 0) for d in delivery_data)
        total_section_inflow = sum(d.get("section_inflow_m3", 0) for d in delivery_data)
        total_consumed = sum(d.get("water_consumed_m3", 0) for d in delivery_data)
        total_losses = sum(d.get("transit_loss_m3", 0) for d in delivery_data)
        
        # Calculate efficiencies
        delivery_eff = await self.calculate_delivery_efficiency(
            total_gate_outflow, total_section_inflow, total_losses
        )
        
        application_eff = await self.calculate_application_efficiency(
            total_section_inflow, total_consumed
        )
        
        overall_eff = await self.calculate_overall_efficiency(
            delivery_eff["delivery_efficiency"],
            application_eff["application_efficiency"]
        )
        
        # Calculate uniformity (coefficient of variation)
        if len(delivery_data) > 1:
            volumes = [d.get("section_inflow_m3", 0) for d in delivery_data]
            mean_volume = statistics.mean(volumes)
            if mean_volume > 0:
                std_dev = statistics.stdev(volumes)
                uniformity_coefficient = 1 - (std_dev / mean_volume)
            else:
                uniformity_coefficient = 0.0
        else:
            uniformity_coefficient = 1.0
        
        # Performance score (weighted average)
        performance_score = (
            0.4 * delivery_eff["delivery_efficiency"] +
            0.4 * application_eff["application_efficiency"] +
            0.2 * uniformity_coefficient
        )
        
        return {
            "section_id": section_data["id"],
            "section_name": section_data.get("name", ""),
            "period": {
                "start": time_period[0].isoformat(),
                "end": time_period[1].isoformat()
            },
            "deliveries_count": len(delivery_data),
            "volumes": {
                "total_gate_outflow_m3": total_gate_outflow,
                "total_section_inflow_m3": total_section_inflow,
                "total_consumed_m3": total_consumed,
                "total_losses_m3": total_losses
            },
            "efficiencies": {
                "delivery": delivery_eff,
                "application": application_eff,
                "overall": overall_eff
            },
            "uniformity_coefficient": uniformity_coefficient,
            "performance_score": performance_score,
            "performance_classification": self._classify_efficiency(performance_score)
        }
    
    async def generate_efficiency_report(
        self,
        sections_metrics: List[Dict],
        report_period: Tuple[datetime, datetime],
        zone_id: Optional[str] = None
    ) -> Dict:
        """
        Generate efficiency report for multiple sections
        
        Args:
            sections_metrics: List of section efficiency metrics
            report_period: Report time period
            zone_id: Optional zone filter
            
        Returns:
            Dict with aggregated report
        """
        if not sections_metrics:
            return {
                "report_period": {
                    "start": report_period[0].isoformat(),
                    "end": report_period[1].isoformat()
                },
                "zone_id": zone_id,
                "total_sections": 0,
                "summary": "No data available"
            }
        
        # Calculate aggregates
        total_sections = len(sections_metrics)
        
        # Average efficiencies
        avg_delivery_eff = statistics.mean(
            [s["efficiencies"]["delivery"]["delivery_efficiency"] for s in sections_metrics]
        )
        avg_application_eff = statistics.mean(
            [s["efficiencies"]["application"]["application_efficiency"] for s in sections_metrics]
        )
        avg_overall_eff = statistics.mean(
            [s["efficiencies"]["overall"]["overall_efficiency"] for s in sections_metrics]
        )
        
        # Performance distribution
        performance_dist = self._calculate_performance_distribution(sections_metrics)
        
        # Best and worst performers
        sorted_by_performance = sorted(
            sections_metrics,
            key=lambda x: x["performance_score"],
            reverse=True
        )
        
        best_performers = [
            {
                "section_id": s["section_id"],
                "section_name": s["section_name"],
                "performance_score": s["performance_score"],
                "overall_efficiency": s["efficiencies"]["overall"]["overall_efficiency"]
            }
            for s in sorted_by_performance[:5]
        ]
        
        worst_performers = [
            {
                "section_id": s["section_id"],
                "section_name": s["section_name"],
                "performance_score": s["performance_score"],
                "overall_efficiency": s["efficiencies"]["overall"]["overall_efficiency"],
                "limiting_factor": s["efficiencies"]["overall"]["limiting_factor"]
            }
            for s in sorted_by_performance[-5:]
        ]
        
        # Recommendations
        recommendations = await self._generate_recommendations(
            sections_metrics, avg_delivery_eff, avg_application_eff
        )
        
        return {
            "report_id": f"EFF-{zone_id or 'ALL'}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "report_period": {
                "start": report_period[0].isoformat(),
                "end": report_period[1].isoformat()
            },
            "zone_id": zone_id,
            "total_sections": total_sections,
            "summary_statistics": {
                "avg_delivery_efficiency": avg_delivery_eff,
                "avg_application_efficiency": avg_application_eff,
                "avg_overall_efficiency": avg_overall_eff,
                "total_water_delivered_m3": sum(
                    s["volumes"]["total_gate_outflow_m3"] for s in sections_metrics
                ),
                "total_water_consumed_m3": sum(
                    s["volumes"]["total_consumed_m3"] for s in sections_metrics
                ),
                "total_losses_m3": sum(
                    s["volumes"]["total_losses_m3"] for s in sections_metrics
                )
            },
            "performance_distribution": performance_dist,
            "best_performers": best_performers,
            "worst_performers": worst_performers,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }
    
    def _classify_efficiency(self, efficiency: float) -> str:
        """Classify efficiency level"""
        if efficiency >= self.efficiency_thresholds["excellent"]:
            return "excellent"
        elif efficiency >= self.efficiency_thresholds["good"]:
            return "good"
        elif efficiency >= self.efficiency_thresholds["fair"]:
            return "fair"
        elif efficiency >= self.efficiency_thresholds["poor"]:
            return "poor"
        else:
            return "very_poor"
    
    def _calculate_performance_distribution(self, sections_metrics: List[Dict]) -> Dict:
        """Calculate distribution of performance levels"""
        distribution = {
            "excellent": 0,
            "good": 0,
            "fair": 0,
            "poor": 0,
            "very_poor": 0
        }
        
        for section in sections_metrics:
            classification = section["performance_classification"]
            distribution[classification] += 1
        
        # Convert to percentages
        total = len(sections_metrics)
        for key in distribution:
            distribution[key] = {
                "count": distribution[key],
                "percentage": (distribution[key] / total * 100) if total > 0 else 0
            }
        
        return distribution
    
    async def _generate_recommendations(
        self,
        sections_metrics: List[Dict],
        avg_delivery_eff: float,
        avg_application_eff: float
    ) -> List[Dict]:
        """Generate improvement recommendations based on efficiency analysis"""
        recommendations = []
        
        # System-wide recommendations
        if avg_delivery_eff < 0.70:
            recommendations.append({
                "type": "system",
                "priority": "high",
                "area": "delivery",
                "recommendation": "Improve canal maintenance to reduce seepage losses",
                "potential_improvement": f"{(0.75 - avg_delivery_eff) * 100:.1f}%"
            })
        
        if avg_application_eff < 0.65:
            recommendations.append({
                "type": "system",
                "priority": "high",
                "area": "application",
                "recommendation": "Implement improved irrigation scheduling and methods",
                "potential_improvement": f"{(0.70 - avg_application_eff) * 100:.1f}%"
            })
        
        # Section-specific recommendations
        poor_sections = [s for s in sections_metrics 
                        if s["performance_classification"] in ["poor", "very_poor"]]
        
        if len(poor_sections) > 0.3 * len(sections_metrics):
            recommendations.append({
                "type": "urgent",
                "priority": "critical",
                "area": "sections",
                "recommendation": f"Immediate intervention needed for {len(poor_sections)} underperforming sections",
                "sections": [s["section_id"] for s in poor_sections[:10]]
            })
        
        return recommendations
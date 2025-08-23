from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from core import get_logger
from config import settings
from db import DatabaseManager
from services.integration_client import IntegrationClient

logger = get_logger(__name__)


class FeedbackService:
    """Manages delivery performance feedback and updates crop models"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.client = IntegrationClient()
        self.logger = logger.bind(service="feedback_manager")
        
        # In-memory storage for development
        self._performance_data = defaultdict(list)
        self._weekly_summaries = {}
    
    async def get_section_performance(
        self,
        section_id: str,
        weeks: int = 4
    ) -> List[Dict]:
        """Get historical performance data for a section"""
        performances = []
        
        # Generate mock historical data
        current_week = int(datetime.utcnow().strftime("%V"))
        current_year = datetime.utcnow().year
        
        for i in range(weeks):
            week_num = current_week - i
            if week_num <= 0:
                week_num += 52
                year = current_year - 1
            else:
                year = current_year
            
            week_str = f"{year}-W{week_num:02d}"
            
            # Mock performance data
            planned = 15000 + (i * 1000)  # Varying demand
            efficiency = 0.95 - (i * 0.02)  # Decreasing efficiency
            delivered = planned * efficiency
            
            performances.append({
                "section_id": section_id,
                "week": week_str,
                "planned_m3": planned,
                "delivered_m3": delivered,
                "efficiency": efficiency,
                "deficit_m3": planned - delivered,
                "delivery_times": [
                    datetime.utcnow() - timedelta(days=7*i, hours=8),
                    datetime.utcnow() - timedelta(days=7*i-2, hours=14)
                ],
                "average_flow_m3s": 2.5
            })
        
        return performances
    
    async def update_section_delivery(
        self,
        week: str,
        section_id: str,
        delivered_m3: float,
        efficiency: float
    ) -> bool:
        """Update delivery performance for a section"""
        try:
            # Store performance data
            performance = {
                "section_id": section_id,
                "week": week,
                "delivered_m3": delivered_m3,
                "efficiency": efficiency,
                "timestamp": datetime.utcnow()
            }
            
            self._performance_data[section_id].append(performance)
            
            # Update ROS with actual delivery
            await self._update_ros_delivery(section_id, delivered_m3, week)
            
            # Update water accounting
            await self._update_water_accounting(section_id, delivered_m3, efficiency)
            
            self.logger.info(
                "Delivery feedback updated",
                section_id=section_id,
                week=week,
                delivered_m3=delivered_m3,
                efficiency=efficiency
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to update delivery feedback", error=str(e))
            return False
    
    async def get_weekly_summary(self, week: str) -> Optional[Dict]:
        """Get aggregated performance summary for a week"""
        if week in self._weekly_summaries:
            return self._weekly_summaries[week]
        
        # Generate mock summary
        sections_data = []
        total_planned = 0
        total_delivered = 0
        
        # Mock data for different zones
        for zone in [2, 3, 5, 6]:
            for section in ["A", "B", "C", "D"]:
                section_id = f"Zone_{zone}_Section_{section}"
                planned = 15000 + (zone * 500)
                efficiency = 0.90 + (zone * 0.01)
                delivered = planned * efficiency
                
                sections_data.append({
                    "section_id": section_id,
                    "planned": planned,
                    "delivered": delivered,
                    "efficiency": efficiency
                })
                
                total_planned += planned
                total_delivered += delivered
        
        summary = {
            "week": week,
            "total_planned_m3": total_planned,
            "total_delivered_m3": total_delivered,
            "overall_efficiency": total_delivered / total_planned if total_planned > 0 else 0,
            "sections_served": len(sections_data),
            "sections_with_deficit": sum(1 for s in sections_data if s["delivered"] < s["planned"])
        }
        
        self._weekly_summaries[week] = summary
        return summary
    
    async def process_delivery_feedback(self, feedback: Dict) -> Dict:
        """Process comprehensive delivery feedback from field operations"""
        week = feedback["week"]
        sections = feedback["sections"]
        gate_performances = feedback.get("gate_performances", {})
        
        results = {
            "processed_sections": 0,
            "failed_sections": [],
            "average_efficiency": 0,
            "total_deficit_m3": 0
        }
        
        total_efficiency = 0
        
        for section_data in sections:
            for section_id, delivered_m3 in section_data.items():
                # Get planned amount (mock)
                planned_m3 = delivered_m3 / 0.9  # Assume 90% efficiency
                efficiency = delivered_m3 / planned_m3
                
                success = await self.update_section_delivery(
                    week, section_id, delivered_m3, efficiency
                )
                
                if success:
                    results["processed_sections"] += 1
                    total_efficiency += efficiency
                    results["total_deficit_m3"] += (planned_m3 - delivered_m3)
                else:
                    results["failed_sections"].append(section_id)
        
        if results["processed_sections"] > 0:
            results["average_efficiency"] = total_efficiency / results["processed_sections"]
        
        # Update gate performance metrics
        for gate_id, gate_efficiency in gate_performances.items():
            await self._update_gate_performance(gate_id, gate_efficiency, week)
        
        self.logger.info(
            "Delivery feedback processed",
            week=week,
            sections_processed=results["processed_sections"],
            average_efficiency=results["average_efficiency"]
        )
        
        return results
    
    async def _update_ros_delivery(
        self,
        section_id: str,
        delivered_m3: float,
        week: str
    ) -> None:
        """Update ROS service with actual water delivered"""
        # In production, would call ROS API
        # For now, log the update
        self.logger.info(
            "ROS delivery update",
            section_id=section_id,
            delivered_m3=delivered_m3,
            week=week
        )
    
    async def _update_water_accounting(
        self,
        section_id: str,
        delivered_m3: float,
        efficiency: float
    ) -> None:
        """Update water accounting service with delivery data"""
        # Calculate losses
        losses_m3 = delivered_m3 * (1 - efficiency)
        
        accounting_data = {
            "section_id": section_id,
            "delivered_m3": delivered_m3,
            "losses_m3": losses_m3,
            "efficiency": efficiency,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # In production, would call water accounting API
        self.logger.info(
            "Water accounting update",
            **accounting_data
        )
    
    async def _update_gate_performance(
        self,
        gate_id: str,
        efficiency: float,
        week: str
    ) -> None:
        """Update gate performance metrics"""
        # Store gate performance
        gate_performance = {
            "gate_id": gate_id,
            "efficiency": efficiency,
            "week": week,
            "timestamp": datetime.utcnow()
        }
        
        # In production, would update database
        self.logger.info(
            "Gate performance update",
            **gate_performance
        )
    
    async def generate_performance_report(
        self,
        start_week: str,
        end_week: str
    ) -> Dict:
        """Generate comprehensive performance report for a date range"""
        report = {
            "period": f"{start_week} to {end_week}",
            "total_sections": 0,
            "total_delivered_m3": 0,
            "total_planned_m3": 0,
            "overall_efficiency": 0,
            "sections_by_efficiency": {
                "excellent": 0,  # > 95%
                "good": 0,       # 85-95%
                "fair": 0,       # 75-85%
                "poor": 0        # < 75%
            },
            "deficit_sections": []
        }
        
        # Mock report generation
        # In production, would aggregate from database
        
        return report
    
    async def calculate_deficit_carryforward(
        self,
        section_id: str,
        current_week: str
    ) -> float:
        """Calculate accumulated deficit to carry forward"""
        # Get last 4 weeks of performance
        performances = await self.get_section_performance(section_id, weeks=4)
        
        total_deficit = sum(p["deficit_m3"] for p in performances)
        
        # Apply decay factor (older deficits matter less)
        weighted_deficit = 0
        for i, perf in enumerate(performances):
            age_factor = 1 - (i * 0.2)  # 20% reduction per week
            weighted_deficit += perf["deficit_m3"] * age_factor
        
        return weighted_deficit
from typing import List, Dict, Optional
from datetime import datetime
from clients.awd_client import AWDControlClient
from core import get_logger

logger = get_logger(__name__)


class AWDIntegrationService:
    """Service for integrating AWD data with water planning"""
    
    def __init__(self):
        self.client = AWDControlClient()
        self.logger = logger.bind(service="awd_integration")
    
    async def get_section_awd_status(self, section_id: str) -> Dict:
        """Get aggregated AWD status for all plots in a section"""
        # First get all plots in the section (would query from database)
        plot_ids = await self._get_plots_in_section(section_id)
        
        if not plot_ids:
            return {
                "section_id": section_id,
                "awd_active": False,
                "total_plots": 0,
                "awd_plots": 0,
                "average_moisture": None,
                "water_savings_m3": 0
            }
        
        # Get AWD status for all plots
        awd_statuses = await self.client.get_batch_status(plot_ids)
        
        # Calculate aggregated metrics
        awd_active_count = 0
        total_moisture = 0
        moisture_readings = 0
        estimated_savings = 0
        
        for plot_id, status in awd_statuses.items():
            if status.get("is_active"):
                awd_active_count += 1
                if status.get("moisture_level") is not None:
                    total_moisture += status["moisture_level"]
                    moisture_readings += 1
                estimated_savings += status.get("expected_savings", 0)
        
        return {
            "section_id": section_id,
            "awd_active": awd_active_count > 0,
            "total_plots": len(plot_ids),
            "awd_plots": awd_active_count,
            "awd_percentage": (awd_active_count / len(plot_ids) * 100) if plot_ids else 0,
            "average_moisture": (total_moisture / moisture_readings) if moisture_readings > 0 else None,
            "water_savings_m3": estimated_savings,
            "last_updated": datetime.utcnow()
        }
    
    async def get_zone_awd_summary(self, zone_id: str) -> Dict:
        """Get AWD summary for an entire zone"""
        summary = await self.client.get_zone_summary(zone_id)
        
        if not summary:
            # Return default if AWD service is unavailable
            return {
                "zone_id": zone_id,
                "awd_enabled": False,
                "total_sections": 0,
                "awd_sections": 0,
                "total_savings_m3": 0,
                "co2_reduction_kg": 0,
                "recommendations": []
            }
        
        return summary
    
    async def get_awd_recommendations_for_demand(
        self,
        section_id: str,
        current_demand_m3: float
    ) -> Dict:
        """Get AWD-adjusted demand recommendations"""
        plot_ids = await self._get_plots_in_section(section_id)
        
        if not plot_ids:
            return {
                "section_id": section_id,
                "original_demand_m3": current_demand_m3,
                "adjusted_demand_m3": current_demand_m3,
                "potential_savings_m3": 0,
                "recommendations": []
            }
        
        # Get AWD recommendations
        recommendations = await self.client.get_recommendations(plot_ids)
        
        # Calculate potential savings
        total_savings = 0
        awd_recommendations = []
        
        for rec in recommendations:
            if rec.get("recommendation") == "activate_awd":
                # AWD typically saves 15-30% of water
                plot_savings = current_demand_m3 * 0.2 * (1 / len(plot_ids))
                total_savings += plot_savings
                awd_recommendations.append({
                    "plot_id": rec["plot_id"],
                    "action": "activate_awd",
                    "expected_savings_m3": plot_savings,
                    "reason": rec.get("reason", "Conditions suitable for AWD")
                })
        
        adjusted_demand = max(0, current_demand_m3 - total_savings)
        
        return {
            "section_id": section_id,
            "original_demand_m3": current_demand_m3,
            "adjusted_demand_m3": adjusted_demand,
            "potential_savings_m3": total_savings,
            "savings_percentage": (total_savings / current_demand_m3 * 100) if current_demand_m3 > 0 else 0,
            "recommendations": awd_recommendations
        }
    
    async def update_awd_monitoring_data(
        self,
        plot_id: str,
        moisture_level: float
    ) -> bool:
        """Update AWD monitoring data from sensors"""
        success = await self.client.update_moisture_reading(
            plot_id=plot_id,
            moisture_level=moisture_level,
            timestamp=datetime.utcnow()
        )
        
        if success:
            self.logger.info(
                "AWD moisture updated",
                plot_id=plot_id,
                moisture_level=moisture_level
            )
        
        return success
    
    async def calculate_awd_impact_on_demands(
        self,
        demands: List[Dict]
    ) -> List[Dict]:
        """Calculate AWD impact on water demands"""
        adjusted_demands = []
        
        for demand in demands:
            section_id = demand["section_id"]
            
            # Get AWD recommendations
            awd_rec = await self.get_awd_recommendations_for_demand(
                section_id,
                demand["volume_m3"]
            )
            
            # Create adjusted demand
            adjusted_demand = demand.copy()
            adjusted_demand["original_volume_m3"] = demand["volume_m3"]
            adjusted_demand["volume_m3"] = awd_rec["adjusted_demand_m3"]
            adjusted_demand["awd_savings_m3"] = awd_rec["potential_savings_m3"]
            adjusted_demand["awd_applied"] = awd_rec["potential_savings_m3"] > 0
            
            adjusted_demands.append(adjusted_demand)
        
        total_original = sum(d["original_volume_m3"] for d in adjusted_demands)
        total_adjusted = sum(d["volume_m3"] for d in adjusted_demands)
        total_savings = total_original - total_adjusted
        
        self.logger.info(
            "AWD impact calculated",
            original_demand_m3=total_original,
            adjusted_demand_m3=total_adjusted,
            savings_m3=total_savings,
            savings_percent=round(total_savings / total_original * 100, 2) if total_original > 0 else 0
        )
        
        return adjusted_demands
    
    async def _get_plots_in_section(self, section_id: str) -> List[str]:
        """Get all plot IDs in a section"""
        # In production, would query from database
        # Mock implementation
        return [
            f"{section_id}_plot_{i:03d}"
            for i in range(1, 11)  # Assume 10 plots per section
        ]
    
    async def close(self):
        """Close the AWD client"""
        await self.client.close()
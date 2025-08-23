from typing import List, Dict, Any, Optional
from datetime import datetime
from core import get_logger
from config import settings
from schemas.demand import DemandPriority, DemandPriorityEnum

logger = get_logger(__name__)


class PriorityEngine:
    """Calculates and manages demand priorities based on multiple factors"""
    
    def __init__(self):
        self.logger = logger.bind(service="priority_engine")
        
        # Priority weights from settings
        self.crop_stage_weight = settings.crop_stage_weight
        self.moisture_deficit_weight = settings.moisture_deficit_weight
        self.economic_value_weight = settings.economic_value_weight
        self.stress_indicator_weight = settings.stress_indicator_weight
        
        # Crop stage priority mappings
        self.crop_stage_priorities = {
            "germination": 0.9,
            "vegetative": 0.7,
            "flowering": 1.0,  # Critical stage
            "grain_filling": 0.95,
            "maturity": 0.5,
            "tillering": 0.85,  # For sugarcane
            "grand_growth": 0.9,  # For sugarcane
            "ripening": 0.6
        }
        
        # Economic value by crop type (relative)
        self.crop_economic_values = {
            "rice": 0.8,
            "sugarcane": 0.9,
            "cassava": 0.6,
            "maize": 0.7,
            "vegetables": 0.85
        }
    
    async def prioritize_demands(self, demands: List[Dict]) -> List[Dict]:
        """
        Calculate priority scores for all demands
        
        Args:
            demands: List of demand dictionaries
        
        Returns:
            List of demands with calculated priorities
        """
        prioritized = []
        
        for demand in demands:
            priority = await self._calculate_priority(demand)
            demand["priority_details"] = priority
            demand["final_priority"] = priority.final_priority
            demand["priority_class"] = priority.priority_class
            prioritized.append(demand)
        
        # Sort by final priority (highest first)
        prioritized.sort(key=lambda x: x["final_priority"], reverse=True)
        
        self.logger.info(
            "Demands prioritized",
            total_demands=len(prioritized),
            critical_count=sum(1 for d in prioritized if d["priority_class"] == "critical")
        )
        
        return prioritized
    
    async def _calculate_priority(self, demand: Dict) -> DemandPriority:
        """Calculate priority score for a single demand"""
        section_id = demand.get("section_id", "unknown")
        
        # Get base priority (1-10 scale)
        base_priority = self._get_base_priority(demand.get("priority"))
        
        # Calculate factor scores (0-1 scale)
        crop_stage_factor = self._calculate_crop_stage_factor(
            demand.get("growth_stage", "vegetative")
        )
        
        moisture_deficit_factor = self._calculate_moisture_deficit_factor(
            demand.get("moisture_deficit_percent", 20)
        )
        
        economic_value_factor = self._calculate_economic_value_factor(
            demand.get("crop_type", "rice")
        )
        
        stress_indicator_factor = self._calculate_stress_indicator_factor(
            demand.get("stress_level", "none")
        )
        
        # Calculate weighted final priority
        final_priority = (
            base_priority * (
                self.crop_stage_weight * crop_stage_factor +
                self.moisture_deficit_weight * moisture_deficit_factor +
                self.economic_value_weight * economic_value_factor +
                self.stress_indicator_weight * stress_indicator_factor
            )
        )
        
        # Ensure priority is within bounds
        final_priority = max(1, min(10, final_priority))
        
        # Determine priority class
        priority_class = self._get_priority_class(final_priority)
        
        return DemandPriority(
            section_id=section_id,
            base_priority=base_priority,
            crop_stage_factor=crop_stage_factor,
            moisture_deficit_factor=moisture_deficit_factor,
            economic_value_factor=economic_value_factor,
            stress_indicator_factor=stress_indicator_factor,
            final_priority=final_priority,
            priority_class=priority_class
        )
    
    def _get_base_priority(self, priority: Any) -> int:
        """Convert various priority formats to base score"""
        if isinstance(priority, (int, float)):
            return int(max(1, min(10, priority)))
        
        if isinstance(priority, str):
            priority_map = {
                "critical": 9,
                "high": 7,
                "medium": 5,
                "low": 3
            }
            return priority_map.get(priority.lower(), 5)
        
        return 5  # Default medium
    
    def _calculate_crop_stage_factor(self, growth_stage: str) -> float:
        """Calculate priority factor based on crop growth stage"""
        return self.crop_stage_priorities.get(growth_stage.lower(), 0.7)
    
    def _calculate_moisture_deficit_factor(self, deficit_percent: float) -> float:
        """Calculate priority factor based on soil moisture deficit"""
        # Higher deficit = higher priority
        # Normalize to 0-1 scale with thresholds
        if deficit_percent >= 50:
            return 1.0  # Critical deficit
        elif deficit_percent >= 35:
            return 0.85
        elif deficit_percent >= 20:
            return 0.7
        elif deficit_percent >= 10:
            return 0.5
        else:
            return 0.3  # Adequate moisture
    
    def _calculate_economic_value_factor(self, crop_type: str) -> float:
        """Calculate priority factor based on crop economic value"""
        return self.crop_economic_values.get(crop_type.lower(), 0.7)
    
    def _calculate_stress_indicator_factor(self, stress_level: str) -> float:
        """Calculate priority factor based on crop stress indicators"""
        stress_map = {
            "critical": 1.0,
            "severe": 0.9,
            "moderate": 0.7,
            "mild": 0.5,
            "none": 0.3
        }
        return stress_map.get(stress_level.lower(), 0.5)
    
    def _get_priority_class(self, final_priority: float) -> DemandPriorityEnum:
        """Classify priority into categories"""
        if final_priority >= 8:
            return DemandPriorityEnum.CRITICAL
        elif final_priority >= 6:
            return DemandPriorityEnum.HIGH
        elif final_priority >= 4:
            return DemandPriorityEnum.MEDIUM
        else:
            return DemandPriorityEnum.LOW
    
    async def recalculate_week(self, week: str) -> List[str]:
        """
        Recalculate priorities for all demands in a week
        
        Args:
            week: Week identifier (e.g., "2024-W03")
        
        Returns:
            List of section IDs that were updated
        """
        # In production, this would:
        # 1. Fetch all demands for the week from database
        # 2. Get latest sensor data (moisture, stress indicators)
        # 3. Recalculate priorities
        # 4. Update database
        # 5. Notify scheduler of changes
        
        # Mock implementation
        updated_sections = [
            "Zone_2_Section_A",
            "Zone_2_Section_B",
            "Zone_5_Section_A"
        ]
        
        self.logger.info(
            "Priorities recalculated",
            week=week,
            sections_updated=len(updated_sections)
        )
        
        return updated_sections
    
    async def adjust_for_weather(
        self,
        demands: List[Dict],
        weather_forecast: Dict
    ) -> List[Dict]:
        """
        Adjust priorities based on weather forecast
        
        Args:
            demands: List of prioritized demands
            weather_forecast: Weather data including rainfall, temperature, ET
        
        Returns:
            Weather-adjusted demands
        """
        rainfall_mm = weather_forecast.get("rainfall_mm", 0)
        temperature_c = weather_forecast.get("temperature_c", 30)
        humidity_percent = weather_forecast.get("humidity_percent", 70)
        
        for demand in demands:
            # Reduce priority if significant rainfall expected
            if rainfall_mm > 20:
                demand["final_priority"] *= 0.8
            elif rainfall_mm > 10:
                demand["final_priority"] *= 0.9
            
            # Increase priority if high temperature and low humidity
            if temperature_c > 35 and humidity_percent < 50:
                demand["final_priority"] *= 1.1
            
            # Recalculate priority class
            demand["priority_class"] = self._get_priority_class(
                demand["final_priority"]
            )
        
        return demands
    
    def get_priority_explanation(self, priority: DemandPriority) -> str:
        """Generate human-readable explanation of priority calculation"""
        factors = []
        
        if priority.crop_stage_factor >= 0.9:
            factors.append("critical growth stage")
        
        if priority.moisture_deficit_factor >= 0.85:
            factors.append("severe moisture deficit")
        
        if priority.economic_value_factor >= 0.85:
            factors.append("high economic value crop")
        
        if priority.stress_indicator_factor >= 0.9:
            factors.append("severe crop stress")
        
        if not factors:
            factors.append("standard conditions")
        
        explanation = f"Priority {priority.final_priority:.1f} due to: {', '.join(factors)}"
        return explanation
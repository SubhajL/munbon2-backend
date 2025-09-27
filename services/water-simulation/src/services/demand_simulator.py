"""
Demand simulation service for water requirement calculations
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

from src.clients.ros_client import ROSClient
from src.clients.gis_client import GISClient

logger = logging.getLogger(__name__)


@dataclass
class DemandScenario:
    """Demand scenario configuration"""
    base_multiplier: float = 1.0
    weather_variation: float = 0.1  # ±10% random variation
    growth_rate: float = 0.0  # Annual growth rate
    seasonal_factors: Dict[int, float] = None  # Month -> multiplier
    drought_factor: float = 1.0
    efficiency_improvement: float = 0.0  # Annual efficiency gain
    

class DemandSimulator:
    """Simulates water demand for irrigation sections"""
    
    def __init__(
        self,
        ros_client: ROSClient,
        gis_client: GISClient,
        scenario: Optional[DemandScenario] = None
    ):
        self.ros = ros_client
        self.gis = gis_client
        self.scenario = scenario or DemandScenario()
        
        # Cache for section properties
        self._section_cache: Dict[str, Dict] = {}
        self._crop_patterns: Dict[str, List[Tuple[int, str]]] = {}  # section -> [(week, crop)]
        
    async def initialize_sections(self, section_ids: List[str]) -> None:
        """Initialize section data cache"""
        for section_id in section_ids:
            if section_id not in self._section_cache:
                section_data = await self.gis.get_section_details(section_id)
                self._section_cache[section_id] = section_data
                
                # Initialize crop pattern
                self._initialize_crop_pattern(section_id, section_data)
    
    def _initialize_crop_pattern(self, section_id: str, section_data: Dict) -> None:
        """Initialize crop planting pattern for a section"""
        crop_type = section_data.get("crop_type", "rice")
        
        if crop_type == "rice":
            # Two rice crops per year
            self._crop_patterns[section_id] = [
                (1, "rice"),    # First crop: weeks 1-16
                (17, "fallow"), # Fallow: weeks 17-26
                (27, "rice"),   # Second crop: weeks 27-42
                (43, "fallow")  # Fallow: weeks 43-52
            ]
        elif crop_type == "sugarcane":
            # Single sugarcane crop (perennial)
            self._crop_patterns[section_id] = [(1, "sugarcane")]
        else:
            # Default single crop
            self._crop_patterns[section_id] = [(1, crop_type)]
    
    async def calculate_section_demand(
        self,
        section_id: str,
        simulation_time: datetime,
        use_forecast: bool = False
    ) -> Dict[str, float]:
        """Calculate water demand for a section"""
        week = simulation_time.isocalendar()[1]
        year = simulation_time.year
        
        # Get base demand from ROS
        base_demand_data = await self.ros.get_water_demand(
            section_id, "section", week, year
        )
        
        base_demand = base_demand_data["demand_m3"]
        
        # Apply scenario modifiers
        adjusted_demand = self._apply_scenario_adjustments(
            base_demand,
            simulation_time,
            section_id
        )
        
        # Apply weather forecast if requested
        if use_forecast:
            weather_factor = await self._get_weather_forecast_factor(simulation_time)
            adjusted_demand *= weather_factor
        
        # Apply water level adjustments
        water_level = await self._get_current_water_level(section_id, simulation_time)
        if water_level is not None:
            level_adjustment = self._calculate_water_level_adjustment(
                water_level,
                self._get_current_crop(section_id, week),
                self._get_crop_week(section_id, week)
            )
            adjusted_demand *= level_adjustment
        
        return {
            "section_id": section_id,
            "base_demand_m3": base_demand,
            "adjusted_demand_m3": adjusted_demand,
            "eto_mm": base_demand_data["eto_mm"],
            "kc": base_demand_data["kc"],
            "percolation_mm": base_demand_data["percolation_mm"],
            "area_hectares": base_demand_data["area_hectares"],
            "crop_type": self._get_current_crop(section_id, week),
            "crop_week": self._get_crop_week(section_id, week),
            "water_level_m": water_level,
            "adjustment_factors": {
                "scenario": self.scenario.base_multiplier,
                "weather": weather_factor if use_forecast else 1.0,
                "water_level": level_adjustment if water_level else 1.0,
                "drought": self.scenario.drought_factor
            }
        }
    
    async def calculate_zone_demand(
        self,
        zone: int,
        simulation_time: datetime
    ) -> Dict[str, Any]:
        """Calculate aggregated demand for an entire zone"""
        sections = await self.gis.get_sections_in_zone(zone)
        
        total_demand = 0
        section_demands = []
        
        for section in sections:
            demand_data = await self.calculate_section_demand(
                section["section_id"],
                simulation_time
            )
            total_demand += demand_data["adjusted_demand_m3"]
            section_demands.append(demand_data)
        
        return {
            "zone": zone,
            "simulation_time": simulation_time.isoformat(),
            "total_demand_m3": total_demand,
            "section_count": len(sections),
            "average_demand_m3": total_demand / len(sections) if sections else 0,
            "section_demands": section_demands
        }
    
    async def forecast_demand_profile(
        self,
        section_id: str,
        start_time: datetime,
        days_ahead: int = 7
    ) -> List[Dict[str, float]]:
        """Forecast demand profile for coming days"""
        profile = []
        
        current_time = start_time
        for day in range(days_ahead):
            daily_demands = []
            
            # Calculate hourly demands for the day
            for hour in range(24):
                hour_time = current_time + timedelta(hours=hour)
                demand = await self.calculate_section_demand(
                    section_id,
                    hour_time,
                    use_forecast=True
                )
                daily_demands.append(demand["adjusted_demand_m3"])
            
            profile.append({
                "date": current_time.date().isoformat(),
                "total_demand_m3": sum(daily_demands),
                "peak_hour_demand_m3": max(daily_demands),
                "avg_hour_demand_m3": sum(daily_demands) / 24
            })
            
            current_time += timedelta(days=1)
        
        return profile
    
    def _apply_scenario_adjustments(
        self,
        base_demand: float,
        simulation_time: datetime,
        section_id: str
    ) -> float:
        """Apply scenario-based demand adjustments"""
        adjusted = base_demand * self.scenario.base_multiplier
        
        # Apply growth rate
        if self.scenario.growth_rate > 0:
            years_from_start = (simulation_time.year - 2024)  # Assuming 2024 as base
            growth_factor = (1 + self.scenario.growth_rate) ** years_from_start
            adjusted *= growth_factor
        
        # Apply seasonal factors
        if self.scenario.seasonal_factors:
            month = simulation_time.month
            seasonal_factor = self.scenario.seasonal_factors.get(month, 1.0)
            adjusted *= seasonal_factor
        
        # Apply drought factor
        adjusted *= self.scenario.drought_factor
        
        # Apply efficiency improvements
        if self.scenario.efficiency_improvement > 0:
            years_from_start = (simulation_time.year - 2024)
            efficiency_factor = 1 - (self.scenario.efficiency_improvement * years_from_start)
            adjusted *= max(0.5, efficiency_factor)  # Cap at 50% reduction
        
        # Add random weather variation
        if self.scenario.weather_variation > 0:
            random_factor = 1 + np.random.uniform(
                -self.scenario.weather_variation,
                self.scenario.weather_variation
            )
            adjusted *= random_factor
        
        return max(0, adjusted)  # Ensure non-negative
    
    async def _get_weather_forecast_factor(self, simulation_time: datetime) -> float:
        """Get weather-based demand adjustment factor"""
        # In real implementation, this would integrate with weather service
        # For simulation, use simple model
        
        # Seasonal pattern
        day_of_year = simulation_time.timetuple().tm_yday
        seasonal_component = 1 + 0.2 * np.sin(2 * np.pi * day_of_year / 365)
        
        # Random daily variation
        daily_variation = np.random.normal(1.0, 0.05)
        
        return seasonal_component * daily_variation
    
    async def _get_current_water_level(
        self,
        section_id: str,
        simulation_time: datetime
    ) -> Optional[float]:
        """Get current water level for the section"""
        week = simulation_time.isocalendar()[1]
        year = simulation_time.year
        
        return await self.ros.get_weekly_water_levels(
            section_id, "section", week, year
        )
    
    def _calculate_water_level_adjustment(
        self,
        water_level_m: float,
        crop_type: str,
        crop_week: int
    ) -> float:
        """Calculate demand adjustment based on water level"""
        # Default adjustment factors by crop stage
        adjustments = {
            "rice": {
                "early": (0.03, 0.07, 1.0),      # (min_level, opt_level, factor)
                "vegetative": (0.05, 0.10, 1.0),
                "reproductive": (0.05, 0.10, 1.0),
                "maturity": (0.02, 0.05, 1.0)
            },
            "sugarcane": {
                "all": (0.05, 0.15, 1.0)
            }
        }
        
        # Determine crop stage
        if crop_type == "rice":
            if crop_week <= 4:
                stage = "early"
            elif crop_week <= 8:
                stage = "vegetative"
            elif crop_week <= 12:
                stage = "reproductive"
            else:
                stage = "maturity"
        else:
            stage = "all"
        
        # Get adjustment parameters
        params = adjustments.get(crop_type, {}).get(stage, (0.05, 0.10, 1.0))
        min_level, opt_level, base_factor = params
        
        # Calculate adjustment
        if water_level_m < min_level:
            # Increase demand when water is low
            return base_factor * (1 + 0.3 * (min_level - water_level_m) / min_level)
        elif water_level_m > opt_level:
            # Reduce demand when water is abundant
            return base_factor * (1 - 0.1 * min(1, (water_level_m - opt_level) / opt_level))
        else:
            # Optimal range
            return base_factor
    
    def _get_current_crop(self, section_id: str, week: int) -> str:
        """Get current crop type for a section"""
        pattern = self._crop_patterns.get(section_id, [(1, "rice")])
        
        for i, (start_week, crop) in enumerate(pattern):
            if i + 1 < len(pattern):
                next_week = pattern[i + 1][0]
                if start_week <= week < next_week:
                    return crop
            else:
                # Last entry in pattern
                if week >= start_week:
                    return crop
        
        return pattern[0][1]  # Default to first crop
    
    def _get_crop_week(self, section_id: str, week: int) -> int:
        """Get week number within current crop cycle"""
        pattern = self._crop_patterns.get(section_id, [(1, "rice")])
        
        for i, (start_week, crop) in enumerate(pattern):
            if i + 1 < len(pattern):
                next_week = pattern[i + 1][0]
                if start_week <= week < next_week:
                    return week - start_week + 1
            else:
                if week >= start_week:
                    return week - start_week + 1
        
        return 1
    
    async def analyze_demand_patterns(
        self,
        section_ids: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze demand patterns over time period"""
        total_days = (end_date - start_date).days
        
        daily_totals = []
        peak_demands = []
        
        current_date = start_date
        while current_date < end_date:
            day_total = 0
            day_peak = 0
            
            for section_id in section_ids:
                demand = await self.calculate_section_demand(
                    section_id,
                    current_date
                )
                day_total += demand["adjusted_demand_m3"]
                day_peak = max(day_peak, demand["adjusted_demand_m3"])
            
            daily_totals.append(day_total)
            peak_demands.append(day_peak)
            current_date += timedelta(days=1)
        
        return {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_demand_m3": sum(daily_totals),
            "avg_daily_demand_m3": sum(daily_totals) / len(daily_totals),
            "peak_daily_demand_m3": max(daily_totals),
            "min_daily_demand_m3": min(daily_totals),
            "demand_variability": np.std(daily_totals) / np.mean(daily_totals),
            "section_count": len(section_ids)
        }
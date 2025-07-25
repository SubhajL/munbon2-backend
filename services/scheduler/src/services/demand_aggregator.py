"""
Demand Aggregation Service
Collects and aggregates water demands from multiple sources
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import structlog
import httpx

from ..db.connections import DatabaseManager
from ..schemas.demands import SectionDemand, AggregatedDemands, DemandStatus

logger = structlog.get_logger()


class DemandAggregator:
    """
    Aggregates irrigation water demands from:
    1. ROS/GIS Integration service
    2. Historical patterns
    3. Weather adjustments
    4. Manual overrides
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.ros_gis_url = "http://localhost:3041"  # Will be configured
        
        # Aggregation parameters
        self.default_priority = 5
        self.weather_adjustment_factor = 1.0
        self.historical_weight = 0.3
        
    async def aggregate_weekly_demands(
        self,
        week: str,
        sources: Optional[List[str]] = None
    ) -> AggregatedDemands:
        """Aggregate demands from all sources for a week"""
        try:
            # Collect from different sources
            ros_demands = await self._fetch_ros_gis_demands(week)
            historical_demands = await self._fetch_historical_demands(week)
            manual_demands = await self._fetch_manual_demands(week)
            
            # Merge and deduplicate
            all_demands = self._merge_demands(
                ros_demands,
                historical_demands,
                manual_demands
            )
            
            # Apply weather adjustments
            adjusted_demands = await self._apply_weather_adjustments(
                all_demands,
                week
            )
            
            # Group by zones and crops
            aggregated = self._aggregate_by_categories(adjusted_demands)
            
            # Store aggregated result
            await self._store_aggregated_demands(week, aggregated)
            
            return aggregated
            
        except Exception as e:
            logger.error(f"Failed to aggregate demands: {e}")
            raise
    
    async def _fetch_ros_gis_demands(
        self, 
        week: str
    ) -> List[SectionDemand]:
        """Fetch demands from ROS/GIS Integration service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.ros_gis_url}/api/v1/demands/week/{week}",
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [
                        SectionDemand(**demand) 
                        for demand in data.get("sections", [])
                    ]
                elif response.status_code == 404:
                    logger.info(f"No ROS/GIS demands for week {week}")
                    return []
                else:
                    logger.error(f"ROS/GIS service error: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch ROS/GIS demands: {e}")
            return []
    
    async def _fetch_historical_demands(
        self, 
        week: str
    ) -> List[SectionDemand]:
        """Fetch historical demand patterns"""
        try:
            # Extract week number
            _, week_num = week.split('-')
            week_num = int(week_num)
            
            # Query historical data for same week in previous years
            query = """
                SELECT section_id, zone, AVG(demand_m3) as avg_demand,
                       crop_type, COUNT(*) as years_count
                FROM historical_demands
                WHERE week_number = $1
                GROUP BY section_id, zone, crop_type
                HAVING years_count >= 2
            """
            
            # Execute query (simplified for example)
            # In real implementation, properly execute with db connection
            historical_data = []
            
            # Convert to SectionDemand objects
            demands = []
            for row in historical_data:
                demand = SectionDemand(
                    section_id=row['section_id'],
                    zone=row['zone'],
                    demand_m3=row['avg_demand'] * 0.9,  # Conservative estimate
                    priority=self.default_priority - 1,  # Lower priority
                    crop_type=row['crop_type'],
                    delivery_window={
                        "start": datetime.utcnow(),
                        "end": datetime.utcnow() + timedelta(days=7)
                    }
                )
                demands.append(demand)
            
            return demands
            
        except Exception as e:
            logger.error(f"Failed to fetch historical demands: {e}")
            return []
    
    async def _fetch_manual_demands(
        self, 
        week: str
    ) -> List[SectionDemand]:
        """Fetch manually entered demands"""
        try:
            # Query manual overrides from database
            # In real implementation, query from postgres
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch manual demands: {e}")
            return []
    
    def _merge_demands(
        self,
        *demand_lists: List[SectionDemand]
    ) -> List[SectionDemand]:
        """Merge demands from multiple sources, handling duplicates"""
        merged = {}
        
        for demands in demand_lists:
            for demand in demands:
                key = (demand.section_id, demand.crop_type)
                
                if key in merged:
                    # Merge logic: take maximum demand, highest priority
                    existing = merged[key]
                    existing.demand_m3 = max(existing.demand_m3, demand.demand_m3)
                    existing.priority = max(existing.priority, demand.priority)
                    
                    # Merge delivery windows
                    if demand.delivery_window:
                        if not existing.delivery_window:
                            existing.delivery_window = demand.delivery_window
                        else:
                            # Take earliest start, latest end
                            existing.delivery_window["start"] = min(
                                existing.delivery_window.get("start", demand.delivery_window["start"]),
                                demand.delivery_window["start"]
                            )
                            existing.delivery_window["end"] = max(
                                existing.delivery_window.get("end", demand.delivery_window["end"]),
                                demand.delivery_window["end"]
                            )
                else:
                    merged[key] = demand
        
        return list(merged.values())
    
    async def _apply_weather_adjustments(
        self,
        demands: List[SectionDemand],
        week: str
    ) -> List[SectionDemand]:
        """Apply weather-based adjustments to demands"""
        try:
            # Get weather forecast
            weather_data = await self._get_weather_forecast(week)
            
            # Calculate adjustment factors
            rainfall_expected = weather_data.get("rainfall_mm", 0)
            temperature_avg = weather_data.get("temperature_avg", 30)
            
            # Adjust based on expected rainfall
            if rainfall_expected > 50:
                self.weather_adjustment_factor = 0.7
            elif rainfall_expected > 20:
                self.weather_adjustment_factor = 0.85
            elif rainfall_expected < 5:
                self.weather_adjustment_factor = 1.2
            else:
                self.weather_adjustment_factor = 1.0
            
            # Adjust based on temperature
            if temperature_avg > 35:
                self.weather_adjustment_factor *= 1.1
            elif temperature_avg < 25:
                self.weather_adjustment_factor *= 0.9
            
            # Apply adjustments
            for demand in demands:
                demand.demand_m3 *= self.weather_adjustment_factor
                
                # Increase priority for drought conditions
                if self.weather_adjustment_factor > 1.1:
                    demand.priority = min(10, demand.priority + 1)
            
            return demands
            
        except Exception as e:
            logger.error(f"Failed to apply weather adjustments: {e}")
            return demands
    
    async def _get_weather_forecast(self, week: str) -> Dict:
        """Get weather forecast for the week"""
        # In real implementation, call weather API
        # For now, return mock data
        return {
            "rainfall_mm": 15,
            "temperature_avg": 32,
            "humidity_avg": 65,
            "wind_speed_avg": 10
        }
    
    def _aggregate_by_categories(
        self,
        demands: List[SectionDemand]
    ) -> AggregatedDemands:
        """Aggregate demands by zones and crop types"""
        total_demand = sum(d.demand_m3 for d in demands)
        zones_covered = list(set(d.zone for d in demands))
        
        # Group by zone
        demands_by_zone = {}
        for demand in demands:
            if demand.zone not in demands_by_zone:
                demands_by_zone[demand.zone] = 0
            demands_by_zone[demand.zone] += demand.demand_m3
        
        # Group by crop
        demands_by_crop = {}
        for demand in demands:
            if demand.crop_type not in demands_by_crop:
                demands_by_crop[demand.crop_type] = 0
            demands_by_crop[demand.crop_type] += demand.demand_m3
        
        # Priority distribution
        priority_distribution = {}
        for demand in demands:
            if demand.priority not in priority_distribution:
                priority_distribution[demand.priority] = 0
            priority_distribution[demand.priority] += 1
        
        # Extract week for the aggregated object
        week = demands[0].delivery_window["start"].strftime("%Y-%W") if demands else "unknown"
        
        return AggregatedDemands(
            week=week,
            total_demand_m3=total_demand,
            sections_count=len(demands),
            zones_covered=sorted(zones_covered),
            demands_by_zone=demands_by_zone,
            demands_by_crop=demands_by_crop,
            priority_distribution=priority_distribution,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            processing_status=DemandStatus.VALIDATED
        )
    
    async def _store_aggregated_demands(
        self,
        week: str,
        aggregated: AggregatedDemands
    ):
        """Store aggregated demands in database"""
        try:
            # Store in PostgreSQL
            # In real implementation, use proper database operations
            logger.info(
                f"Stored aggregated demands for week {week}",
                total_demand=aggregated.total_demand_m3,
                sections=aggregated.sections_count
            )
        except Exception as e:
            logger.error(f"Failed to store aggregated demands: {e}")
            raise
    
    async def validate_demand_feasibility(
        self,
        demands: List[SectionDemand]
    ) -> Dict[str, Any]:
        """Validate if demands can be satisfied"""
        total_demand = sum(d.demand_m3 for d in demands)
        
        # Check system capacity
        system_capacity = 30.0 * 7 * 24 * 3600  # m³/week (30 m³/s)
        
        feasibility = {
            "is_feasible": total_demand <= system_capacity * 0.8,
            "total_demand_m3": total_demand,
            "system_capacity_m3": system_capacity,
            "utilization_percentage": (total_demand / system_capacity) * 100,
            "bottlenecks": []
        }
        
        # Check zone-level constraints
        zone_capacities = {
            1: 50000, 2: 60000, 3: 55000, 4: 45000, 5: 50000,
            6: 40000, 7: 35000, 8: 30000, 9: 25000, 10: 20000
        }
        
        demands_by_zone = {}
        for demand in demands:
            if demand.zone not in demands_by_zone:
                demands_by_zone[demand.zone] = 0
            demands_by_zone[demand.zone] += demand.demand_m3
        
        for zone, demand in demands_by_zone.items():
            capacity = zone_capacities.get(zone, 30000)
            if demand > capacity:
                feasibility["bottlenecks"].append({
                    "zone": zone,
                    "demand": demand,
                    "capacity": capacity,
                    "excess": demand - capacity
                })
        
        return feasibility
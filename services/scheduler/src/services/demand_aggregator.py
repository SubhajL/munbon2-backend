from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from collections import defaultdict
import asyncio

from .clients import ROSClient, GISClient, FlowMonitoringClient
from ..core.logger import get_logger
from ..core.redis import get_redis, RedisClient
from ..core.config import settings

logger = get_logger(__name__)


class DemandAggregator:
    """Aggregate water demands from multiple sources"""
    
    def __init__(
        self,
        ros_client: ROSClient,
        gis_client: GISClient,
        flow_client: FlowMonitoringClient,
        redis_client: RedisClient
    ):
        self.ros_client = ros_client
        self.gis_client = gis_client
        self.flow_client = flow_client
        self.redis_client = redis_client
        self.cache_prefix = "demand_aggregation"
    
    async def aggregate_weekly_demands(
        self,
        week_number: int,
        year: int,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Aggregate water demands for a specific week"""
        cache_key = f"{self.cache_prefix}:{year}:week_{week_number}"
        
        # Check cache
        if use_cache and settings.enable_cache:
            cached_data = await self.redis_client.get_json(cache_key)
            if cached_data:
                logger.info(f"Using cached demand data for week {week_number}, {year}")
                return cached_data
        
        logger.info(f"Aggregating demands for week {week_number}, {year}")
        
        # Get current week demand from ROS
        current_week_data = await self.ros_client.get_current_week_demand(week_number, year)
        
        # Get network topology from GIS
        network_topology = await self.gis_client.get_canal_network_topology()
        
        # Aggregate by delivery paths
        aggregated_data = await self._aggregate_by_delivery_paths(
            current_week_data,
            network_topology
        )
        
        # Apply weather adjustments
        weather_adjusted = await self._apply_weather_adjustments(aggregated_data)
        
        # Group by time windows
        time_grouped = self._group_by_time_windows(weather_adjusted)
        
        result = {
            "week": week_number,
            "year": year,
            "totalDemandM3": sum(d["totalDemandM3"] for d in time_grouped.values()),
            "totalNetDemandM3": sum(d["totalNetDemandM3"] for d in time_grouped.values()),
            "byZone": self._aggregate_by_zone(current_week_data),
            "byDeliveryPath": aggregated_data,
            "byTimeWindow": time_grouped,
            "plotCount": current_week_data.get("summary", {}).get("totalPlots", 0),
            "aggregatedAt": datetime.utcnow().isoformat(),
        }
        
        # Cache the result
        if settings.enable_cache:
            await self.redis_client.set_json(cache_key, result, settings.cache_ttl_seconds)
        
        return result
    
    async def _aggregate_by_delivery_paths(
        self,
        demand_data: Dict[str, Any],
        network_topology: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate demands by delivery paths through the network"""
        path_demands = defaultdict(lambda: {
            "totalDemandM3": 0,
            "totalNetDemandM3": 0,
            "plots": [],
            "gates": [],
        })
        
        # Process each plot demand
        plot_demands = demand_data.get("data", [])
        
        for plot in plot_demands:
            zone_id = plot.get("parentZoneId")
            
            # Find delivery path for this zone
            delivery_path = self._find_delivery_path(zone_id, network_topology)
            
            if delivery_path:
                path_key = "->".join(delivery_path)
                path_demands[path_key]["totalDemandM3"] += plot.get("cropWaterDemandM3", 0)
                path_demands[path_key]["totalNetDemandM3"] += plot.get("netWaterDemandM3", 0)
                path_demands[path_key]["plots"].append(plot.get("plotId"))
                path_demands[path_key]["gates"] = delivery_path
        
        return dict(path_demands)
    
    def _find_delivery_path(
        self,
        zone_id: str,
        network_topology: Dict[str, Any]
    ) -> List[str]:
        """Find the delivery path from reservoir to zone"""
        # This is a simplified version - actual implementation would
        # traverse the network graph to find the path
        zone_to_gates = {
            "Z1": ["M(0,0)", "M(0,2)", "M(1,0)"],
            "Z2": ["M(0,0)", "M(0,2)", "M(2,0)"],
            "Z3": ["M(0,0)", "M(0,3)", "M(3,0)"],
            "Z4": ["M(0,0)", "M(0,3)", "M(4,0)"],
            "Z5": ["M(0,0)", "M(0,4)", "M(5,0)"],
            "Z6": ["M(0,0)", "M(0,4)", "M(6,0)"],
        }
        
        return zone_to_gates.get(zone_id, [])
    
    async def _apply_weather_adjustments(
        self,
        aggregated_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply weather-based adjustments to demands"""
        # In a real implementation, this would fetch weather forecasts
        # and adjust demands based on expected rainfall, temperature, etc.
        
        adjusted_data = aggregated_data.copy()
        
        # Simplified adjustment: reduce demand by 10% if rain is expected
        weather_factor = 0.9  # Assume some rain
        
        for path, data in adjusted_data.items():
            data["weatherAdjustedDemandM3"] = data["totalNetDemandM3"] * weather_factor
            data["weatherFactor"] = weather_factor
        
        return adjusted_data
    
    def _group_by_time_windows(
        self,
        demand_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Group demands by operational time windows"""
        # Define time windows for different crop types
        time_windows = {
            "morning": {"start": "06:00", "end": "12:00", "crops": ["rice"]},
            "afternoon": {"start": "12:00", "end": "18:00", "crops": ["corn"]},
            "evening": {"start": "18:00", "end": "22:00", "crops": ["sugarcane"]},
        }
        
        grouped = defaultdict(lambda: {
            "totalDemandM3": 0,
            "totalNetDemandM3": 0,
            "paths": [],
        })
        
        # For simplicity, distribute demands across time windows
        for path, data in demand_data.items():
            # Assign to morning window by default
            window = "morning"
            grouped[window]["totalDemandM3"] += data.get("weatherAdjustedDemandM3", 0)
            grouped[window]["totalNetDemandM3"] += data.get("totalNetDemandM3", 0)
            grouped[window]["paths"].append(path)
        
        return dict(grouped)
    
    def _aggregate_by_zone(self, demand_data: Dict[str, Any]) -> Dict[str, float]:
        """Aggregate demands by zone"""
        zone_summary = demand_data.get("summary", {}).get("byZone", {})
        return zone_summary
    
    async def get_section_demands(
        self,
        section_ids: List[str],
        week_number: int,
        year: int
    ) -> Dict[str, float]:
        """Get aggregated demands for specific sections"""
        section_demands = {}
        
        # Fetch demands for each section in parallel
        tasks = []
        for section_id in section_ids:
            tasks.append(self._get_section_demand(section_id, week_number, year))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for section_id, result in zip(section_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get demand for section {section_id}: {str(result)}")
                section_demands[section_id] = 0.0
            else:
                section_demands[section_id] = result
        
        return section_demands
    
    async def _get_section_demand(
        self,
        section_id: str,
        week_number: int,
        year: int
    ) -> float:
        """Get total demand for a section"""
        # Get plots in section
        plots = await self.ros_client.get_section_plots(section_id)
        
        # Sum up demands
        total_demand = 0.0
        for plot in plots:
            # Simplified - in reality would calculate for specific week
            total_demand += plot.get("averageWeeklyDemandM3", 0.0)
        
        return total_demand
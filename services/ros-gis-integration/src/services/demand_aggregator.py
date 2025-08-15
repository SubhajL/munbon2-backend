from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from core import get_logger
from config import settings
from services.integration_client import IntegrationClient
from services.cache_manager import get_cache_manager, cached
from services.query_optimizer import QueryOptimizer
from schemas.demand import AggregatedDemand, DemandPriorityEnum

logger = get_logger(__name__)


class DemandAggregatorService:
    """Aggregates section-level demands by delivery points"""
    
    def __init__(self):
        self.client = IntegrationClient()
        self.logger = logger.bind(service="demand_aggregator")
        self.cache = None
        self.query_optimizer = QueryOptimizer()
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache and query optimizer"""
        if not self._initialized:
            self.cache = await get_cache_manager()
            await self.query_optimizer.initialize()
            self._initialized = True
    
    async def aggregate_demands(
        self,
        week: str,
        demands: List[Dict],
        weather_adjustment: float = 1.0,
        rainfall_mm: float = 0
    ) -> List[AggregatedDemand]:
        """
        Aggregate section demands by delivery gate
        
        Args:
            week: Week identifier (e.g., "2024-W03")
            demands: List of section demands with priorities
            weather_adjustment: Weather-based adjustment factor
            rainfall_mm: Expected rainfall in mm
        
        Returns:
            List of aggregated demands by delivery gate
        """
        await self.initialize()
        
        # Check cache first
        cache_key = f"{week}_{weather_adjustment}_{rainfall_mm}_{len(demands)}"
        cached_result = await self.cache.get("aggregated_demands", cache_key)
        if cached_result:
            self.logger.info("Using cached aggregated demands", week=week)
            return cached_result
        
        self.logger.info(
            "Aggregating demands",
            week=week,
            demand_count=len(demands),
            weather_adjustment=weather_adjustment
        )
        
        # Get section-to-gate mappings using optimized query
        section_ids = [d["section_id"] for d in demands]
        mappings = await self._get_section_mappings_optimized(section_ids)
        
        # Group demands by delivery gate
        gate_demands = defaultdict(list)
        for demand in demands:
            section_id = demand["section_id"]
            if section_id in mappings:
                gate_id = mappings[section_id]["delivery_gate"]
                gate_demands[gate_id].append(demand)
        
        # Aggregate demands for each gate
        aggregated = []
        for gate_id, section_demands in gate_demands.items():
            agg_demand = await self._aggregate_gate_demands(
                gate_id,
                section_demands,
                weather_adjustment,
                rainfall_mm
            )
            aggregated.append(agg_demand)
        
        # Sort by priority (highest first)
        aggregated.sort(key=lambda x: x.weighted_priority, reverse=True)
        
        self.logger.info(
            "Demands aggregated",
            gate_count=len(aggregated),
            total_volume_m3=sum(d.total_demand_m3 for d in aggregated)
        )
        
        # Cache the result
        await self.cache.set("aggregated_demands", cache_key, aggregated, ttl=900)
        
        return aggregated
    
    async def _get_section_mappings_optimized(self, section_ids: List[str]) -> Dict[str, Dict]:
        """Get delivery gate mappings for sections using optimized queries"""
        # Use query optimizer for batch fetch
        sections = await self.query_optimizer.get_sections_batch(section_ids)
        
        mappings = {}
        for section_id, section_data in sections.items():
            mappings[section_id] = {
                "delivery_gate": section_data.get("delivery_gate", "M(0,0)"),
                "distance_km": 2.5,  # Would calculate from spatial data
                "travel_time_hours": 0.75
            }
        
        # Fallback for sections not in database
        for section_id in section_ids:
            if section_id not in mappings:
                zone = int(section_id.split("_")[1]) if "_" in section_id else 1
                if zone in [2, 3]:
                    gate = "M(0,2)->Zone_2"
                elif zone in [5, 6]:
                    gate = "M(0,5)->Zone_5"
                else:
                    gate = "M(0,0)->M(0,2)"
                
                mappings[section_id] = {
                    "delivery_gate": gate,
                    "distance_km": 2.5,
                    "travel_time_hours": 0.75
                }
        
        return mappings
    
    async def _get_section_mappings(self, section_ids: List[str]) -> Dict[str, Dict]:
        """Legacy method - redirects to optimized version"""
        return await self._get_section_mappings_optimized(section_ids)
    
    async def _aggregate_gate_demands(
        self,
        gate_id: str,
        section_demands: List[Dict],
        weather_adjustment: float,
        rainfall_mm: float
    ) -> AggregatedDemand:
        """Aggregate multiple section demands for a single gate"""
        
        # Calculate total demand with adjustments
        total_demand = 0
        total_weight = 0
        weighted_priority = 0
        sections = []
        
        # Rainfall adjustment (1mm rain ≈ 1.6m³/rai saved)
        # Note: 1 hectare = 6.25 rai, so 10m³/hectare = 1.6m³/rai
        rainfall_reduction = rainfall_mm * 1.6  # m³ per rai
        
        for demand in section_demands:
            # Apply weather and rainfall adjustments
            area_rai = demand.get("area_rai", 937.5)  # Default 937.5 rai (150 hectares)
            adjusted_demand = demand["volume_m3"] * weather_adjustment
            adjusted_demand -= (rainfall_reduction * area_rai)
            adjusted_demand = max(adjusted_demand, settings.min_demand_m3)
            
            total_demand += adjusted_demand
            sections.append(demand["section_id"])
            
            # Weight priority by demand volume
            priority_value = self._get_priority_value(demand.get("priority", "medium"))
            weighted_priority += priority_value * adjusted_demand
            total_weight += adjusted_demand
        
        # Calculate weighted average priority
        if total_weight > 0:
            weighted_priority /= total_weight
        else:
            weighted_priority = 5  # Default medium priority
        
        # Determine delivery window (union of all windows)
        start_time = datetime.utcnow() + timedelta(hours=settings.demand_advance_hours)
        end_time = start_time + timedelta(days=3)
        
        return AggregatedDemand(
            delivery_gate=gate_id,
            total_demand_m3=round(total_demand, 2),
            sections=sections,
            weighted_priority=round(weighted_priority, 2),
            delivery_window={
                "start": start_time,
                "end": end_time
            },
            aggregation_method="weighted_average"
        )
    
    def _get_priority_value(self, priority: Any) -> float:
        """Convert priority to numeric value"""
        if isinstance(priority, (int, float)):
            return float(priority)
        
        priority_map = {
            "critical": 9,
            "high": 7,
            "medium": 5,
            "low": 3
        }
        
        if isinstance(priority, str):
            return priority_map.get(priority.lower(), 5)
        
        return 5  # Default medium
    
    async def submit_to_scheduler(self, aggregated_demands: List[AggregatedDemand]) -> Dict:
        """Submit aggregated demands to the scheduler service"""
        
        # Format demands for scheduler API
        scheduler_demands = {
            "week": aggregated_demands[0].delivery_window["start"].strftime("%Y-W%V"),
            "demands": [
                {
                    "gate_id": d.delivery_gate,
                    "volume_m3": d.total_demand_m3,
                    "priority": d.weighted_priority,
                    "sections": d.sections,
                    "window_start": d.delivery_window["start"].isoformat(),
                    "window_end": d.delivery_window["end"].isoformat()
                }
                for d in aggregated_demands
            ],
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        # Submit to scheduler
        result = await self.client.post_scheduler_demands(scheduler_demands)
        
        self.logger.info(
            "Demands submitted to scheduler",
            schedule_id=result.get("schedule_id"),
            status=result.get("status")
        )
        
        return result
    
    async def check_conflicts(self, week: str) -> List[str]:
        """Check for demand conflicts in a given week"""
        conflicts = []
        
        # Get current demands
        demands = await self.client.get_weekly_demands(week)
        
        # Check for over-allocation
        gate_allocations = defaultdict(float)
        for demand in demands.get("sections", []):
            gate = demand.get("delivery_point")
            if gate:
                gate_allocations[gate] += demand.get("demand_m3", 0)
        
        # Get gate capacities
        gate_states = await self.client.get_gate_states()
        
        for gate_id, allocated_m3 in gate_allocations.items():
            if gate_id in gate_states:
                # Assume 24 hour delivery window
                required_flow = allocated_m3 / (24 * 3600)  # m³/s
                max_flow = gate_states[gate_id].get("max_flow_m3s", 5.0)
                
                if required_flow > max_flow:
                    conflicts.append(
                        f"Gate {gate_id} over-allocated: {required_flow:.2f} > {max_flow:.2f} m³/s"
                    )
        
        # Check for timing conflicts
        # (In production, would check for overlapping delivery windows)
        
        return conflicts
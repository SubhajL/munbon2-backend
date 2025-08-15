"""
Priority Resolution Service
Resolves competing water demands using multi-factor prioritization
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from core import get_logger
from config import settings
from db import DatabaseManager
from services.delivery_optimizer import DeliveryOptimizer

logger = get_logger(__name__)


class PriorityFactor(Enum):
    """Priority factors for water allocation"""
    CROP_STAGE = "crop_stage"
    STRESS_LEVEL = "stress_level"
    DELIVERY_EFFICIENCY = "delivery_efficiency"
    HISTORICAL_PERFORMANCE = "historical_performance"
    AREA_SIZE = "area_size"
    CROP_VALUE = "crop_value"
    SOCIAL_EQUITY = "social_equity"


class PriorityResolutionService:
    """Resolves competing demands using multi-factor prioritization"""
    
    def __init__(self):
        self.logger = logger.bind(service="priority_resolution")
        self.db = DatabaseManager()
        self.optimizer = DeliveryOptimizer()
        
        # Weight configuration for priority factors
        self.factor_weights = {
            PriorityFactor.CROP_STAGE: 0.25,
            PriorityFactor.STRESS_LEVEL: 0.20,
            PriorityFactor.DELIVERY_EFFICIENCY: 0.15,
            PriorityFactor.HISTORICAL_PERFORMANCE: 0.10,
            PriorityFactor.AREA_SIZE: 0.10,
            PriorityFactor.CROP_VALUE: 0.15,
            PriorityFactor.SOCIAL_EQUITY: 0.05
        }
        
        # Critical growth stages by crop
        self.critical_stages = {
            "rice": ["flowering", "grain_filling"],
            "corn": ["flowering", "grain_filling"],
            "sugarcane": ["grand_growth", "ripening"]
        }
    
    async def resolve_competing_demands(
        self,
        demands: List[Dict],
        available_water_m3: float,
        time_window: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """Resolve competing demands when water is limited"""
        
        # Calculate total demand
        total_demand = sum(d.get("net_demand_m3", 0) for d in demands)
        
        if total_demand <= available_water_m3:
            # No competition - all demands can be met
            return self._allocate_full_demands(demands)
        
        # Calculate priorities
        prioritized_demands = await self._calculate_priorities(demands)
        
        # Sort by priority score
        prioritized_demands.sort(key=lambda x: x["priority_score"], reverse=True)
        
        # Allocate water based on priorities
        allocations = await self._allocate_by_priority(
            prioritized_demands,
            available_water_m3,
            time_window
        )
        
        # Generate allocation report
        report = self._generate_allocation_report(
            demands,
            allocations,
            available_water_m3
        )
        
        return {
            "allocations": allocations,
            "report": report,
            "optimization_timestamp": datetime.utcnow().isoformat()
        }
    
    async def _calculate_priorities(self, demands: List[Dict]) -> List[Dict]:
        """Calculate priority scores for each demand"""
        prioritized = []
        
        # Load delivery network for efficiency calculations
        await self.optimizer.load_network()
        
        for demand in demands:
            scores = {}
            
            # 1. Crop stage priority
            scores[PriorityFactor.CROP_STAGE] = self._score_crop_stage(
                demand.get("crop_type", "unknown"),
                demand.get("growth_stage", "unknown")
            )
            
            # 2. Stress level priority
            scores[PriorityFactor.STRESS_LEVEL] = self._score_stress_level(
                demand.get("stress_level", "none"),
                demand.get("moisture_deficit_percent", 0)
            )
            
            # 3. Delivery efficiency
            efficiency_score = await self._score_delivery_efficiency(
                demand.get("section_id", ""),
                demand.get("net_demand_m3", 0)
            )
            scores[PriorityFactor.DELIVERY_EFFICIENCY] = efficiency_score
            
            # 4. Historical performance
            scores[PriorityFactor.HISTORICAL_PERFORMANCE] = await self._score_historical_performance(
                demand.get("section_id", "")
            )
            
            # 5. Area size (favor smaller areas for equity)
            scores[PriorityFactor.AREA_SIZE] = self._score_area_size(
                demand.get("area_rai", 0)
            )
            
            # 6. Crop value
            scores[PriorityFactor.CROP_VALUE] = self._score_crop_value(
                demand.get("crop_type", "unknown")
            )
            
            # 7. Social equity
            scores[PriorityFactor.SOCIAL_EQUITY] = self._score_social_equity(
                demand.get("section_id", ""),
                demand.get("farmer_count", 1)
            )
            
            # Calculate weighted total score
            total_score = sum(
                score * self.factor_weights[factor]
                for factor, score in scores.items()
            )
            
            prioritized_demand = demand.copy()
            prioritized_demand.update({
                "priority_scores": scores,
                "priority_score": total_score,
                "priority_rank": 0  # Will be set after sorting
            })
            
            prioritized.append(prioritized_demand)
        
        # Set ranks after sorting
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)
        for i, demand in enumerate(prioritized):
            demand["priority_rank"] = i + 1
        
        return prioritized
    
    def _score_crop_stage(self, crop_type: str, growth_stage: str) -> float:
        """Score based on crop growth stage criticality (0-1)"""
        if crop_type in self.critical_stages:
            if growth_stage in self.critical_stages[crop_type]:
                return 1.0  # Critical stage
            elif growth_stage == "maturity":
                return 0.3  # Low priority at maturity
            else:
                return 0.6  # Medium priority
        return 0.5  # Unknown crop
    
    def _score_stress_level(self, stress_level: str, moisture_deficit: float) -> float:
        """Score based on water stress level (0-1)"""
        stress_scores = {
            "critical": 1.0,
            "high": 0.8,
            "moderate": 0.6,
            "low": 0.4,
            "none": 0.2
        }
        
        base_score = stress_scores.get(stress_level, 0.5)
        
        # Adjust based on moisture deficit
        if moisture_deficit > 50:
            base_score = min(1.0, base_score + 0.2)
        elif moisture_deficit > 30:
            base_score = min(1.0, base_score + 0.1)
        
        return base_score
    
    async def _score_delivery_efficiency(self, section_id: str, demand_m3: float) -> float:
        """Score based on delivery efficiency (0-1)"""
        try:
            # Find optimal path
            path_result = await self.optimizer.find_optimal_path(
                "M(0,0)",  # Source
                section_id,
                demand_m3
            )
            
            if not path_result:
                return 0.3  # Low score if no path
            
            # Score based on loss percentage (lower loss = higher score)
            loss_percent = path_result.get("loss_percent", 10)
            
            if loss_percent < 5:
                return 1.0
            elif loss_percent < 10:
                return 0.8
            elif loss_percent < 15:
                return 0.6
            elif loss_percent < 20:
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            self.logger.error("Failed to calculate delivery efficiency", error=str(e))
            return 0.5  # Default middle score
    
    async def _score_historical_performance(self, section_id: str) -> float:
        """Score based on historical water use efficiency (0-1)"""
        try:
            # Get historical performance from database
            async with self.db.get_section_performance_repository() as repo:
                performances = await repo.get_recent_performances(
                    section_id,
                    days=30
                )
            
            if not performances:
                return 0.5  # No history - neutral score
            
            # Calculate average efficiency
            efficiencies = [p.actual_m3 / p.allocated_m3 for p in performances if p.allocated_m3 > 0]
            
            if not efficiencies:
                return 0.5
            
            avg_efficiency = sum(efficiencies) / len(efficiencies)
            
            # Score based on efficiency (closer to 1.0 is better)
            if avg_efficiency > 0.95:
                return 1.0
            elif avg_efficiency > 0.85:
                return 0.8
            elif avg_efficiency > 0.75:
                return 0.6
            elif avg_efficiency > 0.65:
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            self.logger.error("Failed to get historical performance", error=str(e))
            return 0.5
    
    def _score_area_size(self, area_rai: float) -> float:
        """Score based on area size - favor smaller areas for equity (0-1)"""
        if area_rai <= 10:
            return 1.0  # Small farms get highest priority
        elif area_rai <= 25:
            return 0.8
        elif area_rai <= 50:
            return 0.6
        elif area_rai <= 100:
            return 0.4
        else:
            return 0.2  # Large farms get lower priority
    
    def _score_crop_value(self, crop_type: str) -> float:
        """Score based on economic value of crop (0-1)"""
        crop_values = {
            "rice": 0.7,  # Staple food - high priority
            "corn": 0.6,
            "sugarcane": 0.5,
            "vegetables": 0.8,  # High value, perishable
            "fruits": 0.9,  # Highest value
            "unknown": 0.5
        }
        return crop_values.get(crop_type, 0.5)
    
    def _score_social_equity(self, section_id: str, farmer_count: int) -> float:
        """Score based on social factors (0-1)"""
        # More farmers = higher social impact
        if farmer_count >= 50:
            return 1.0
        elif farmer_count >= 20:
            return 0.8
        elif farmer_count >= 10:
            return 0.6
        elif farmer_count >= 5:
            return 0.4
        else:
            return 0.2
    
    async def _allocate_by_priority(
        self,
        prioritized_demands: List[Dict],
        available_water_m3: float,
        time_window: Optional[Dict] = None
    ) -> Dict[str, Dict]:
        """Allocate water based on priorities"""
        allocations = {}
        remaining_water = available_water_m3
        
        for demand in prioritized_demands:
            section_id = demand["section_id"]
            requested = demand["net_demand_m3"]
            
            if remaining_water <= 0:
                # No water left
                allocations[section_id] = {
                    "allocated_m3": 0,
                    "requested_m3": requested,
                    "satisfaction_percent": 0,
                    "priority_rank": demand["priority_rank"],
                    "reason": "water_exhausted"
                }
                continue
            
            # Check delivery feasibility
            path_result = await self.optimizer.find_optimal_path(
                "M(0,0)",
                section_id,
                min(requested, remaining_water)
            )
            
            if not path_result or not path_result.get("feasible", False):
                # Cannot deliver to this section
                allocations[section_id] = {
                    "allocated_m3": 0,
                    "requested_m3": requested,
                    "satisfaction_percent": 0,
                    "priority_rank": demand["priority_rank"],
                    "reason": "delivery_infeasible"
                }
                continue
            
            # Calculate allocation with losses
            gross_needed = requested + path_result["expected_loss_m3"]
            
            if gross_needed <= remaining_water:
                # Full allocation possible
                allocated = requested
                remaining_water -= gross_needed
            else:
                # Partial allocation
                # Account for losses proportionally
                net_available = remaining_water * (1 - path_result["loss_percent"] / 100)
                allocated = min(requested, net_available)
                remaining_water = 0
            
            allocations[section_id] = {
                "allocated_m3": allocated,
                "requested_m3": requested,
                "satisfaction_percent": (allocated / requested * 100) if requested > 0 else 0,
                "priority_rank": demand["priority_rank"],
                "priority_score": demand["priority_score"],
                "delivery_path": path_result["path"],
                "delivery_time_hours": path_result["delivery_time_hours"],
                "expected_loss_m3": path_result["expected_loss_m3"]
            }
        
        return allocations
    
    def _allocate_full_demands(self, demands: List[Dict]) -> Dict[str, Dict]:
        """Allocate full demands when no competition exists"""
        allocations = {}
        
        for demand in demands:
            section_id = demand.get("section_id", "")
            requested = demand.get("net_demand_m3", 0)
            
            allocations[section_id] = {
                "allocated_m3": requested,
                "requested_m3": requested,
                "satisfaction_percent": 100,
                "priority_rank": 1,
                "reason": "sufficient_water"
            }
        
        return {
            "allocations": allocations,
            "report": {
                "total_requested_m3": sum(d.get("net_demand_m3", 0) for d in demands),
                "total_allocated_m3": sum(a["allocated_m3"] for a in allocations.values()),
                "satisfaction_rate": 100,
                "sections_fully_satisfied": len(allocations),
                "sections_partially_satisfied": 0,
                "sections_not_satisfied": 0
            },
            "optimization_timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_allocation_report(
        self,
        demands: List[Dict],
        allocations: Dict[str, Dict],
        available_water_m3: float
    ) -> Dict:
        """Generate detailed allocation report"""
        total_requested = sum(d.get("net_demand_m3", 0) for d in demands)
        total_allocated = sum(a["allocated_m3"] for a in allocations.values())
        
        fully_satisfied = sum(
            1 for a in allocations.values()
            if a["satisfaction_percent"] >= 95
        )
        
        partially_satisfied = sum(
            1 for a in allocations.values()
            if 0 < a["satisfaction_percent"] < 95
        )
        
        not_satisfied = sum(
            1 for a in allocations.values()
            if a["satisfaction_percent"] == 0
        )
        
        return {
            "total_requested_m3": total_requested,
            "total_allocated_m3": total_allocated,
            "available_water_m3": available_water_m3,
            "utilization_percent": (total_allocated / available_water_m3 * 100) if available_water_m3 > 0 else 0,
            "satisfaction_rate": (total_allocated / total_requested * 100) if total_requested > 0 else 100,
            "sections_fully_satisfied": fully_satisfied,
            "sections_partially_satisfied": partially_satisfied,
            "sections_not_satisfied": not_satisfied,
            "priority_factors_used": list(self.factor_weights.keys()),
            "allocation_method": "multi_factor_priority"
        }
    
    async def simulate_scenarios(
        self,
        demands: List[Dict],
        scenarios: List[Dict]
    ) -> Dict[str, Dict]:
        """Simulate different allocation scenarios"""
        results = {}
        
        for scenario in scenarios:
            scenario_name = scenario.get("name", "unnamed")
            available_water = scenario.get("available_water_m3", 0)
            custom_weights = scenario.get("factor_weights", {})
            
            # Temporarily update weights if custom ones provided
            original_weights = self.factor_weights.copy()
            if custom_weights:
                self.factor_weights.update(custom_weights)
            
            # Run allocation
            result = await self.resolve_competing_demands(
                demands,
                available_water
            )
            
            results[scenario_name] = result
            
            # Restore original weights
            self.factor_weights = original_weights
        
        return results
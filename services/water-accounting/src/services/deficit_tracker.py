"""Deficit tracking and carry-forward service"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class DeficitTracker:
    """Service for tracking water deficits and managing carry-forward"""
    
    def __init__(self, carry_forward_weeks: int = 4):
        self.carry_forward_weeks = carry_forward_weeks
        self.stress_thresholds = {
            "none": 0.0,      # 0% deficit
            "mild": 0.10,     # 10% deficit
            "moderate": 0.20, # 20% deficit
            "severe": 0.30    # 30%+ deficit
        }
    
    async def calculate_delivery_deficit(
        self,
        section_id: str,
        water_demand_m3: float,
        water_delivered_m3: float,
        water_consumed_m3: float,
        week_number: int,
        year: int
    ) -> Dict:
        """
        Calculate water deficit for a section
        
        Args:
            section_id: Section identifier
            water_demand_m3: Required water volume
            water_delivered_m3: Actually delivered volume
            water_consumed_m3: Volume consumed by crops
            week_number: Week of year
            year: Year
            
        Returns:
            Dict with deficit calculations
        """
        # Calculate deficits
        delivery_deficit = max(0, water_demand_m3 - water_delivered_m3)
        consumption_deficit = max(0, water_demand_m3 - water_consumed_m3)
        
        # Calculate percentage
        deficit_percentage = (delivery_deficit / water_demand_m3 * 100) if water_demand_m3 > 0 else 0
        
        # Determine stress level
        stress_level = self._calculate_stress_level(deficit_percentage / 100)
        
        # Estimate yield impact (simplified model)
        yield_impact = await self._estimate_yield_impact(
            deficit_percentage, stress_level, week_number
        )
        
        return {
            "section_id": section_id,
            "week_number": week_number,
            "year": year,
            "water_demand_m3": water_demand_m3,
            "water_delivered_m3": water_delivered_m3,
            "water_consumed_m3": water_consumed_m3,
            "delivery_deficit_m3": delivery_deficit,
            "consumption_deficit_m3": consumption_deficit,
            "deficit_percentage": deficit_percentage,
            "stress_level": stress_level,
            "estimated_yield_impact": yield_impact
        }
    
    async def update_carry_forward(
        self,
        section_id: str,
        current_deficit: Dict,
        previous_deficits: List[Dict]
    ) -> Dict:
        """
        Update deficit carry-forward tracking
        
        Args:
            section_id: Section identifier
            current_deficit: Current week's deficit
            previous_deficits: Historical deficits
            
        Returns:
            Dict with updated carry-forward status
        """
        # Filter active deficits (within carry-forward window)
        active_deficits = []
        current_week = current_deficit["week_number"]
        current_year = current_deficit["year"]
        
        for deficit in previous_deficits:
            weeks_old = self._calculate_weeks_difference(
                deficit["year"], deficit["week_number"],
                current_year, current_week
            )
            
            if weeks_old < self.carry_forward_weeks and deficit["delivery_deficit_m3"] > 0:
                active_deficits.append({
                    "week": deficit["week_number"],
                    "year": deficit["year"],
                    "deficit_m3": deficit["delivery_deficit_m3"],
                    "age_weeks": weeks_old
                })
        
        # Add current deficit if applicable
        if current_deficit["delivery_deficit_m3"] > 0:
            active_deficits.append({
                "week": current_week,
                "year": current_year,
                "deficit_m3": current_deficit["delivery_deficit_m3"],
                "age_weeks": 0
            })
        
        # Calculate totals
        total_deficit = sum(d["deficit_m3"] for d in active_deficits)
        
        # Create deficit breakdown
        deficit_breakdown = {
            f"{d['year']}-W{d['week']}": d["deficit_m3"]
            for d in active_deficits
        }
        
        # Calculate priority score
        priority_score = await self._calculate_priority_score(
            total_deficit, active_deficits, current_deficit["stress_level"]
        )
        
        # Determine recovery status
        recovery_status = "pending" if total_deficit > 0 else "none_needed"
        
        return {
            "section_id": section_id,
            "active": total_deficit > 0,
            "total_deficit_m3": total_deficit,
            "weeks_in_deficit": len(active_deficits),
            "oldest_deficit_week": min((d["week"] for d in active_deficits), default=None),
            "newest_deficit_week": max((d["week"] for d in active_deficits), default=None),
            "deficit_breakdown": deficit_breakdown,
            "priority_score": priority_score,
            "recovery_status": recovery_status,
            "cumulative_stress_index": self._calculate_cumulative_stress(active_deficits)
        }
    
    async def generate_recovery_plan(
        self,
        carry_forward_data: Dict,
        available_capacity_m3: float,
        upcoming_weeks: int = 4
    ) -> Dict:
        """
        Generate a recovery plan for deficit compensation
        
        Args:
            carry_forward_data: Current carry-forward status
            available_capacity_m3: Extra capacity available
            upcoming_weeks: Number of weeks to plan ahead
            
        Returns:
            Dict with recovery plan
        """
        total_deficit = carry_forward_data["total_deficit_m3"]
        
        if total_deficit == 0:
            return {
                "section_id": carry_forward_data["section_id"],
                "recovery_needed": False,
                "message": "No deficit to recover"
            }
        
        # Calculate weekly compensation
        weekly_compensation = min(
            total_deficit / upcoming_weeks,
            available_capacity_m3
        )
        
        # Create compensation schedule
        compensation_schedule = []
        remaining_deficit = total_deficit
        
        for week in range(1, upcoming_weeks + 1):
            if remaining_deficit <= 0:
                break
                
            compensation = min(weekly_compensation, remaining_deficit)
            compensation_schedule.append({
                "week_offset": week,
                "compensation_m3": compensation,
                "cumulative_recovery_m3": total_deficit - remaining_deficit + compensation
            })
            remaining_deficit -= compensation
        
        # Calculate recovery completion
        recovery_weeks = len(compensation_schedule)
        full_recovery_possible = remaining_deficit <= 0
        
        return {
            "section_id": carry_forward_data["section_id"],
            "recovery_needed": True,
            "total_deficit_m3": total_deficit,
            "recovery_plan": {
                "weekly_compensation_m3": weekly_compensation,
                "recovery_weeks": recovery_weeks,
                "full_recovery_possible": full_recovery_possible,
                "remaining_deficit_m3": remaining_deficit,
                "compensation_schedule": compensation_schedule
            },
            "recovery_start_date": datetime.now() + timedelta(weeks=1),
            "recovery_target_date": datetime.now() + timedelta(weeks=recovery_weeks)
        }
    
    async def get_deficit_summary_by_week(
        self,
        week_number: int,
        year: int,
        section_deficits: List[Dict]
    ) -> Dict:
        """
        Generate deficit summary for a specific week
        
        Args:
            week_number: Week of year
            year: Year
            section_deficits: List of section deficit records
            
        Returns:
            Dict with weekly summary
        """
        week_deficits = [d for d in section_deficits 
                        if d["week_number"] == week_number and d["year"] == year]
        
        if not week_deficits:
            return {
                "week_number": week_number,
                "year": year,
                "total_sections": 0,
                "summary": "No data available"
            }
        
        # Calculate statistics
        total_sections = len(week_deficits)
        sections_in_deficit = len([d for d in week_deficits if d["delivery_deficit_m3"] > 0])
        
        total_demand = sum(d["water_demand_m3"] for d in week_deficits)
        total_delivered = sum(d["water_delivered_m3"] for d in week_deficits)
        total_deficit = sum(d["delivery_deficit_m3"] for d in week_deficits)
        
        # Stress level distribution
        stress_distribution = defaultdict(int)
        for deficit in week_deficits:
            stress_distribution[deficit["stress_level"]] += 1
        
        # Priority sections (severe stress or high deficit)
        priority_sections = sorted(
            [d for d in week_deficits if d["stress_level"] == "severe"],
            key=lambda x: x["delivery_deficit_m3"],
            reverse=True
        )[:10]
        
        return {
            "week_number": week_number,
            "year": year,
            "period": {
                "start": self._get_week_start_date(year, week_number).isoformat(),
                "end": self._get_week_end_date(year, week_number).isoformat()
            },
            "summary_statistics": {
                "total_sections": total_sections,
                "sections_in_deficit": sections_in_deficit,
                "deficit_percentage": (sections_in_deficit / total_sections * 100) if total_sections > 0 else 0
            },
            "water_balance": {
                "total_demand_m3": total_demand,
                "total_delivered_m3": total_delivered,
                "total_deficit_m3": total_deficit,
                "overall_deficit_percentage": (total_deficit / total_demand * 100) if total_demand > 0 else 0
            },
            "stress_distribution": dict(stress_distribution),
            "priority_sections": [
                {
                    "section_id": s["section_id"],
                    "deficit_m3": s["delivery_deficit_m3"],
                    "deficit_percentage": s["deficit_percentage"],
                    "estimated_yield_impact": s["estimated_yield_impact"]
                }
                for s in priority_sections
            ]
        }
    
    def _calculate_stress_level(self, deficit_ratio: float) -> str:
        """Determine stress level based on deficit ratio"""
        if deficit_ratio <= self.stress_thresholds["none"]:
            return "none"
        elif deficit_ratio <= self.stress_thresholds["mild"]:
            return "mild"
        elif deficit_ratio <= self.stress_thresholds["moderate"]:
            return "moderate"
        else:
            return "severe"
    
    async def _estimate_yield_impact(
        self,
        deficit_percentage: float,
        stress_level: str,
        week_number: int
    ) -> float:
        """
        Estimate yield impact based on deficit and timing
        
        Simplified model - actual impact depends on crop type and growth stage
        """
        # Base impact from deficit percentage
        base_impact = deficit_percentage * 0.5  # 50% of deficit translates to yield loss
        
        # Adjust for stress level
        stress_multipliers = {
            "none": 0.0,
            "mild": 0.8,
            "moderate": 1.2,
            "severe": 1.5
        }
        
        # Adjust for timing (critical growth periods)
        # Weeks 10-20 and 30-40 assumed critical (example)
        timing_multiplier = 1.0
        if 10 <= week_number <= 20 or 30 <= week_number <= 40:
            timing_multiplier = 1.3
        
        yield_impact = base_impact * stress_multipliers.get(stress_level, 1.0) * timing_multiplier
        
        # Cap at reasonable maximum
        return min(yield_impact, 50.0)  # Max 50% yield loss
    
    async def _calculate_priority_score(
        self,
        total_deficit: float,
        active_deficits: List[Dict],
        current_stress: str
    ) -> float:
        """Calculate priority score for recovery scheduling"""
        
        # Base score from total deficit (normalized to 0-100 scale)
        base_score = min(total_deficit / 1000, 100)  # Assumes 1000 m³ is high deficit
        
        # Age factor (older deficits get higher priority)
        age_factor = 0
        if active_deficits:
            max_age = max(d["age_weeks"] for d in active_deficits)
            age_factor = (max_age / self.carry_forward_weeks) * 30  # Up to 30 points
        
        # Stress factor
        stress_scores = {"none": 0, "mild": 10, "moderate": 20, "severe": 30}
        stress_factor = stress_scores.get(current_stress, 0)
        
        # Combined score
        priority_score = base_score * 0.4 + age_factor + stress_factor
        
        return min(priority_score, 100)  # Cap at 100
    
    def _calculate_cumulative_stress(self, active_deficits: List[Dict]) -> float:
        """Calculate cumulative stress index"""
        if not active_deficits:
            return 0.0
        
        # Weight deficits by age (older = more stress)
        weighted_sum = 0
        total_weight = 0
        
        for deficit in active_deficits:
            age_weight = 1 + (deficit["age_weeks"] / self.carry_forward_weeks)
            weighted_sum += deficit["deficit_m3"] * age_weight
            total_weight += age_weight
        
        if total_weight > 0:
            return weighted_sum / total_weight / 100  # Normalize
        return 0.0
    
    def _calculate_weeks_difference(
        self,
        year1: int, week1: int,
        year2: int, week2: int
    ) -> int:
        """Calculate difference in weeks between two week/year pairs"""
        date1 = self._get_week_start_date(year1, week1)
        date2 = self._get_week_start_date(year2, week2)
        diff = date2 - date1
        return int(diff.days / 7)
    
    def _get_week_start_date(self, year: int, week: int) -> datetime:
        """Get start date of a week"""
        jan1 = datetime(year, 1, 1)
        week_start = jan1 + timedelta(weeks=week - 1)
        # Adjust to Monday
        week_start -= timedelta(days=week_start.weekday())
        return week_start
    
    def _get_week_end_date(self, year: int, week: int) -> datetime:
        """Get end date of a week"""
        return self._get_week_start_date(year, week) + timedelta(days=6)
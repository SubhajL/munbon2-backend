"""
Weekly Adjustment Accumulator Service.

This service accumulates weather-based adjustments during the current week
to be applied when generating the next week's irrigation schedule.
These adjustments are NOT real-time changes but cumulative factors
that affect water demand calculations for the upcoming week.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from uuid import UUID
import asyncio
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from ..core.logger import get_logger
from ..core.redis import RedisClient
from ..models.weather_adjustments import WeeklyWeatherAdjustment
from ..services.clients import ROSClient, WeatherClient


logger = get_logger(__name__)


class AdjustmentType(str, Enum):
    """Types of weekly adjustments"""
    RAINFALL_REDUCTION = "rainfall_reduction"
    OPERATION_CANCELLATION = "operation_cancellation" 
    ET_ADJUSTMENT = "et_adjustment"
    APPLICATION_TIME_INCREASE = "application_time_increase"


class WeeklyAdjustmentAccumulator:
    """
    Accumulates weather-based adjustments throughout the week
    to be applied to next week's schedule generation.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        redis: RedisClient,
        ros_client: ROSClient,
        weather_client: WeatherClient,
    ):
        self.db = db
        self.redis = redis
        self.ros_client = ros_client
        self.weather_client = weather_client
        
        # Adjustment rules (configurable)
        self.rules = {
            "rainfall_reduction": {
                "threshold_mm": 10.0,
                "reduction_percent": 30.0,
            },
            "operation_cancellation": {
                "threshold_mm": 25.0,
                "cancel_duration_hours": 24,
            },
            "temperature_et_adjustment": {
                "threshold_drop_celsius": 5.0,
                "et_reduction_percent": 20.0,
            },
            "wind_application_time": {
                "threshold_kmh": 20.0,
                "time_increase_percent": 15.0,
            }
        }
    
    async def process_daily_weather(
        self,
        date: date,
        zone_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Process daily weather data and accumulate adjustments.
        Called daily by a scheduled job.
        """
        logger.info(f"Processing weather adjustments for {date}")
        
        adjustments = {
            "date": date.isoformat(),
            "zones": {},
            "summary": {
                "total_rainfall_mm": 0,
                "zones_with_reduction": 0,
                "zones_cancelled": 0,
                "average_et_adjustment": 0,
            }
        }
        
        for zone_id in zone_ids:
            # Get weather data for the zone
            weather_data = await self.weather_client.get_zone_weather(
                zone_id, date
            )
            
            if not weather_data:
                logger.warning(f"No weather data for zone {zone_id} on {date}")
                continue
            
            # Process adjustments for this zone
            zone_adjustments = await self._calculate_zone_adjustments(
                zone_id, date, weather_data
            )
            
            # Store in database
            await self._store_adjustments(zone_id, date, zone_adjustments)
            
            # Update summary
            adjustments["zones"][zone_id] = zone_adjustments
            adjustments["summary"]["total_rainfall_mm"] += weather_data.get("rainfall_mm", 0)
            
            if zone_adjustments.get("demand_reduction_percent", 0) > 0:
                adjustments["summary"]["zones_with_reduction"] += 1
            
            if zone_adjustments.get("operations_cancelled", False):
                adjustments["summary"]["zones_cancelled"] += 1
        
        # Cache weekly accumulation
        await self._update_weekly_accumulation(date, adjustments)
        
        return adjustments
    
    async def _calculate_zone_adjustments(
        self,
        zone_id: str,
        date: date,
        weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate adjustments based on weather rules"""
        adjustments = {
            "zone_id": zone_id,
            "date": date.isoformat(),
            "demand_reduction_percent": 0,
            "operations_cancelled": False,
            "et_adjustment_percent": 0,
            "application_time_increase_percent": 0,
            "factors": [],
        }
        
        rainfall_mm = weather_data.get("rainfall_mm", 0)
        temp_drop = weather_data.get("temperature_drop_celsius", 0)
        wind_speed = weather_data.get("wind_speed_kmh", 0)
        
        # Rule 1: Rainfall > 25mm → Cancel operations
        if rainfall_mm > self.rules["operation_cancellation"]["threshold_mm"]:
            adjustments["operations_cancelled"] = True
            adjustments["demand_reduction_percent"] = 100
            adjustments["factors"].append({
                "type": AdjustmentType.OPERATION_CANCELLATION,
                "reason": f"Heavy rainfall: {rainfall_mm:.1f}mm",
                "impact": "Operations cancelled for 24h",
            })
            
        # Rule 2: Rainfall > 10mm → Reduce by 30%
        elif rainfall_mm > self.rules["rainfall_reduction"]["threshold_mm"]:
            adjustments["demand_reduction_percent"] = self.rules["rainfall_reduction"]["reduction_percent"]
            adjustments["factors"].append({
                "type": AdjustmentType.RAINFALL_REDUCTION,
                "reason": f"Moderate rainfall: {rainfall_mm:.1f}mm",
                "impact": f"{adjustments['demand_reduction_percent']}% demand reduction",
            })
        
        # Rule 3: Temperature drop > 5°C → Reduce ET by 20%
        if temp_drop > self.rules["temperature_et_adjustment"]["threshold_drop_celsius"]:
            adjustments["et_adjustment_percent"] = -self.rules["temperature_et_adjustment"]["et_reduction_percent"]
            adjustments["factors"].append({
                "type": AdjustmentType.ET_ADJUSTMENT,
                "reason": f"Temperature drop: {temp_drop:.1f}°C",
                "impact": f"{abs(adjustments['et_adjustment_percent'])}% ET reduction",
            })
        
        # Rule 4: High wind → Increase application time by 15%
        if wind_speed > self.rules["wind_application_time"]["threshold_kmh"]:
            adjustments["application_time_increase_percent"] = self.rules["wind_application_time"]["time_increase_percent"]
            adjustments["factors"].append({
                "type": AdjustmentType.APPLICATION_TIME_INCREASE,
                "reason": f"High wind: {wind_speed:.1f}km/h",
                "impact": f"{adjustments['application_time_increase_percent']}% longer application",
            })
        
        return adjustments
    
    async def _store_adjustments(
        self,
        zone_id: str,
        date: date,
        adjustments: Dict[str, Any]
    ):
        """Store adjustments in database"""
        # Check if adjustment already exists
        result = await self.db.execute(
            select(WeeklyWeatherAdjustment).where(
                and_(
                    WeeklyWeatherAdjustment.zone_id == zone_id,
                    WeeklyWeatherAdjustment.adjustment_date == date
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.demand_reduction_percent = adjustments["demand_reduction_percent"]
            existing.operations_cancelled = adjustments["operations_cancelled"]
            existing.et_adjustment_percent = adjustments["et_adjustment_percent"]
            existing.application_time_increase_percent = adjustments["application_time_increase_percent"]
            existing.adjustment_factors = adjustments["factors"]
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            adjustment = WeeklyWeatherAdjustment(
                zone_id=zone_id,
                adjustment_date=date,
                week_number=date.isocalendar()[1],
                year=date.year,
                demand_reduction_percent=adjustments["demand_reduction_percent"],
                operations_cancelled=adjustments["operations_cancelled"],
                et_adjustment_percent=adjustments["et_adjustment_percent"],
                application_time_increase_percent=adjustments["application_time_increase_percent"],
                adjustment_factors=adjustments["factors"],
            )
            self.db.add(adjustment)
        
        await self.db.commit()
    
    async def _update_weekly_accumulation(
        self,
        date: date,
        daily_adjustments: Dict[str, Any]
    ):
        """Update the weekly accumulation in Redis"""
        week_number = date.isocalendar()[1]
        year = date.year
        key = f"weekly_adjustments:{year}:week_{week_number}"
        
        # Get existing accumulation
        weekly_data = await self.redis.get_json(key) or {
            "week_number": week_number,
            "year": year,
            "days_processed": [],
            "zone_accumulations": {},
        }
        
        # Add today's data
        if date.isoformat() not in weekly_data["days_processed"]:
            weekly_data["days_processed"].append(date.isoformat())
        
        # Accumulate by zone
        for zone_id, zone_adj in daily_adjustments["zones"].items():
            if zone_id not in weekly_data["zone_accumulations"]:
                weekly_data["zone_accumulations"][zone_id] = {
                    "total_rainfall_mm": 0,
                    "days_with_reduction": 0,
                    "days_cancelled": 0,
                    "average_et_adjustment": 0,
                    "max_wind_adjustment": 0,
                }
            
            zone_acc = weekly_data["zone_accumulations"][zone_id]
            
            # Update accumulations
            if zone_adj.get("demand_reduction_percent", 0) > 0:
                zone_acc["days_with_reduction"] += 1
            
            if zone_adj.get("operations_cancelled", False):
                zone_acc["days_cancelled"] += 1
            
            # Track maximum wind adjustment
            zone_acc["max_wind_adjustment"] = max(
                zone_acc["max_wind_adjustment"],
                zone_adj.get("application_time_increase_percent", 0)
            )
        
        # Store back to Redis (expires after 2 weeks)
        await self.redis.set_json(key, weekly_data, ex=14 * 24 * 3600)
    
    async def get_weekly_adjustments_for_scheduling(
        self,
        week_number: int,
        year: int
    ) -> Dict[str, Any]:
        """
        Get accumulated adjustments for next week's schedule generation.
        This is called by the schedule optimizer when generating a new schedule.
        """
        # Get from database
        result = await self.db.execute(
            select(WeeklyWeatherAdjustment).where(
                and_(
                    WeeklyWeatherAdjustment.week_number == week_number - 1,  # Previous week
                    WeeklyWeatherAdjustment.year == year
                )
            )
        )
        adjustments = result.scalars().all()
        
        # Aggregate by zone
        zone_adjustments = {}
        
        for adj in adjustments:
            if adj.zone_id not in zone_adjustments:
                zone_adjustments[adj.zone_id] = {
                    "demand_modifier": 1.0,  # Multiplicative factor
                    "et_modifier": 1.0,
                    "application_time_modifier": 1.0,
                    "blackout_dates": [],
                    "adjustment_reasons": [],
                }
            
            zone_data = zone_adjustments[adj.zone_id]
            
            # Apply demand reduction
            if adj.demand_reduction_percent > 0:
                zone_data["demand_modifier"] *= (1 - adj.demand_reduction_percent / 100)
                zone_data["adjustment_reasons"].append(
                    f"{adj.adjustment_date}: {adj.demand_reduction_percent}% reduction"
                )
            
            # Track cancellation dates
            if adj.operations_cancelled:
                zone_data["blackout_dates"].append(adj.adjustment_date.isoformat())
            
            # Apply ET adjustment
            if adj.et_adjustment_percent != 0:
                zone_data["et_modifier"] *= (1 + adj.et_adjustment_percent / 100)
            
            # Apply maximum application time increase
            if adj.application_time_increase_percent > 0:
                zone_data["application_time_modifier"] = max(
                    zone_data["application_time_modifier"],
                    1 + adj.application_time_increase_percent / 100
                )
        
        return {
            "week_number": week_number,
            "year": year,
            "based_on_week": week_number - 1,
            "zone_adjustments": zone_adjustments,
            "generated_at": datetime.utcnow().isoformat(),
        }
    
    async def generate_adjustment_report(
        self,
        week_number: int,
        year: int
    ) -> Dict[str, Any]:
        """Generate a human-readable adjustment report for zone managers"""
        adjustments = await self.get_weekly_adjustments_for_scheduling(
            week_number, year
        )
        
        report = {
            "title": f"Weekly Irrigation Adjustments - Week {week_number}, {year}",
            "based_on": f"Weather data from Week {week_number - 1}",
            "zones": {},
            "summary": {
                "zones_affected": 0,
                "average_reduction": 0,
                "total_cancelled_days": 0,
            }
        }
        
        for zone_id, adj in adjustments["zone_adjustments"].items():
            demand_change = (adj["demand_modifier"] - 1) * 100
            
            report["zones"][zone_id] = {
                "water_demand_change": f"{demand_change:+.1f}%",
                "application_time_change": f"{(adj['application_time_modifier'] - 1) * 100:+.1f}%",
                "cancelled_dates": adj["blackout_dates"],
                "reasons": adj["adjustment_reasons"],
                "recommendations": self._generate_recommendations(adj),
            }
            
            if demand_change != 0:
                report["summary"]["zones_affected"] += 1
                report["summary"]["average_reduction"] += demand_change
            
            report["summary"]["total_cancelled_days"] += len(adj["blackout_dates"])
        
        if report["summary"]["zones_affected"] > 0:
            report["summary"]["average_reduction"] /= report["summary"]["zones_affected"]
        
        return report
    
    def _generate_recommendations(self, adjustments: Dict[str, Any]) -> List[str]:
        """Generate recommendations for zone managers"""
        recommendations = []
        
        if adjustments["demand_modifier"] < 1.0:
            reduction = (1 - adjustments["demand_modifier"]) * 100
            recommendations.append(
                f"Reduce irrigation volumes by {reduction:.0f}% due to recent rainfall"
            )
        
        if adjustments["application_time_modifier"] > 1.0:
            increase = (adjustments["application_time_modifier"] - 1) * 100
            recommendations.append(
                f"Increase gate operation times by {increase:.0f}% to compensate for wind losses"
            )
        
        if adjustments["blackout_dates"]:
            recommendations.append(
                f"Skip irrigation on {len(adjustments['blackout_dates'])} days due to heavy rainfall"
            )
        
        if adjustments["et_modifier"] < 1.0:
            recommendations.append(
                "Consider reduced crop water requirements due to cooler temperatures"
            )
        
        return recommendations
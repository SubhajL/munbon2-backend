"""
Weekly Demand Repository
Database access methods for weekly water demands and crop season progress
"""

from typing import Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal

from core import get_logger
from db import DatabaseManager

logger = get_logger(__name__)


class WeeklyDemandRepository:
    """Repository for accessing weekly demand data"""
    
    def __init__(self):
        self.logger = logger.bind(repository="weekly_demand")
        self.db = DatabaseManager()
    
    async def get_weekly_demand(
        self,
        area_id: str,
        area_type: str,
        week_date: date,
        calculation_method: str = "ros"
    ) -> Optional[Dict]:
        """Get weekly demand for a specific area and week"""
        query = """
            SELECT 
                wd.*,
                wd.adjusted_demand_m3 as final_demand_m3,
                CASE 
                    WHEN wd.net_demand_m3 > 0 THEN 
                        (wd.adjusted_demand_m3 - wd.net_demand_m3) / wd.net_demand_m3 * 100
                    ELSE 0 
                END as adjustment_percentage
            FROM ros_gis.weekly_water_demands wd
            WHERE wd.area_id = $1
            AND wd.area_type = $2
            AND wd.week_start_date <= $3
            AND wd.week_end_date >= $3
            AND wd.calculation_method = $4
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(
                query,
                area_id,
                area_type,
                week_date,
                calculation_method
            )
        
        if row:
            return self._format_demand_row(row)
        return None
    
    async def get_current_week_demands(
        self,
        area_type: str,
        calculation_method: str = "ros",
        zone_filter: Optional[int] = None
    ) -> List[Dict]:
        """Get all demands for current week"""
        query = """
            SELECT 
                wd.*,
                wd.adjusted_demand_m3 as final_demand_m3
            FROM ros_gis.weekly_water_demands wd
            WHERE wd.area_type = $1
            AND wd.calculation_method = $2
            AND wd.week_start_date <= CURRENT_DATE
            AND wd.week_end_date >= CURRENT_DATE
        """
        
        params = [area_type, calculation_method]
        
        if zone_filter and area_type == "section":
            query += " AND wd.area_id LIKE $3"
            params.append(f"{zone_filter}-%")
        
        query += " ORDER BY wd.area_id"
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, *params)
        
        return [self._format_demand_row(row) for row in rows]
    
    async def get_historical_demands(
        self,
        area_id: str,
        area_type: str,
        start_date: date,
        end_date: date,
        calculation_method: str = "ros"
    ) -> List[Dict]:
        """Get historical demands for an area"""
        query = """
            SELECT 
                wd.*,
                wd.adjusted_demand_m3 as final_demand_m3
            FROM ros_gis.weekly_water_demands wd
            WHERE wd.area_id = $1
            AND wd.area_type = $2
            AND wd.week_start_date >= $3
            AND wd.week_start_date <= $4
            AND wd.calculation_method = $5
            ORDER BY wd.week_start_date
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(
                query,
                area_id,
                area_type,
                start_date,
                end_date,
                calculation_method
            )
        
        return [self._format_demand_row(row) for row in rows]
    
    async def compare_calculation_methods(
        self,
        area_id: str,
        area_type: str,
        week_date: date
    ) -> Dict:
        """Compare ROS vs RID-MS calculations for same area/week"""
        query = """
            SELECT 
                calculation_method,
                et0_mm,
                avg_kc_factor,
                gross_demand_m3,
                net_demand_m3,
                adjusted_demand_m3,
                sensor_adjustment_factor
            FROM ros_gis.weekly_water_demands
            WHERE area_id = $1
            AND area_type = $2
            AND week_start_date <= $3
            AND week_end_date >= $3
            AND calculation_method IN ('ros', 'rid_ms', 'combined')
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(
                query,
                area_id,
                area_type,
                week_date
            )
        
        comparison = {
            'area_id': area_id,
            'area_type': area_type,
            'week_date': week_date.isoformat(),
            'methods': {}
        }
        
        for row in rows:
            method = row['calculation_method']
            comparison['methods'][method] = {
                'et0_mm': float(row['et0_mm']),
                'avg_kc_factor': float(row['avg_kc_factor']),
                'gross_demand_m3': float(row['gross_demand_m3']),
                'net_demand_m3': float(row['net_demand_m3']),
                'adjusted_demand_m3': float(row['adjusted_demand_m3']),
                'sensor_adjustment_factor': float(row['sensor_adjustment_factor'])
            }
        
        # Calculate differences if both methods exist
        if 'ros' in comparison['methods'] and 'rid_ms' in comparison['methods']:
            ros = comparison['methods']['ros']
            ridms = comparison['methods']['rid_ms']
            
            comparison['differences'] = {
                'kc_diff_pct': ((ridms['avg_kc_factor'] - ros['avg_kc_factor']) / ros['avg_kc_factor'] * 100) if ros['avg_kc_factor'] > 0 else 0,
                'gross_diff_pct': ((ridms['gross_demand_m3'] - ros['gross_demand_m3']) / ros['gross_demand_m3'] * 100) if ros['gross_demand_m3'] > 0 else 0,
                'net_diff_pct': ((ridms['net_demand_m3'] - ros['net_demand_m3']) / ros['net_demand_m3'] * 100) if ros['net_demand_m3'] > 0 else 0,
                'final_diff_pct': ((ridms['adjusted_demand_m3'] - ros['adjusted_demand_m3']) / ros['adjusted_demand_m3'] * 100) if ros['adjusted_demand_m3'] > 0 else 0
            }
        
        return comparison
    
    async def get_season_progress(
        self,
        area_id: str,
        area_type: str,
        crop_type: Optional[str] = None,
        calculation_method: str = "ros"
    ) -> List[Dict]:
        """Get crop season progress for an area"""
        query = """
            SELECT 
                p.*,
                p.cumulative_delivered_m3 / NULLIF(p.cumulative_net_demand_m3, 0) * 100 as fulfillment_pct,
                p.cumulative_net_demand_m3 / NULLIF(p.projected_total_demand_m3, 0) * 100 as season_progress_pct
            FROM ros_gis.crop_season_weekly_progress p
            WHERE p.area_id = $1
            AND p.area_type = $2
            AND p.calculation_method = $3
        """
        
        params = [area_id, area_type, calculation_method]
        
        if crop_type:
            query += " AND p.crop_type = $4"
            params.append(crop_type)
        
        query += " ORDER BY p.week_start_date DESC"
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, *params)
        
        return [self._format_progress_row(row) for row in rows]
    
    async def get_current_season_summary(
        self,
        area_type: str = "zone",
        calculation_method: str = "ros"
    ) -> Dict:
        """Get summary of current season progress across all areas"""
        query = """
            SELECT 
                COUNT(DISTINCT p.area_id) as area_count,
                COUNT(DISTINCT p.crop_type) as crop_types,
                SUM(p.area_rai) as total_area_rai,
                SUM(p.cumulative_net_demand_m3) as total_demand_to_date,
                SUM(p.cumulative_delivered_m3) as total_delivered_to_date,
                SUM(p.projected_total_demand_m3) as total_projected_demand,
                AVG(p.delivery_efficiency_pct) as avg_delivery_efficiency,
                AVG(p.stress_indicator) as avg_stress_indicator
            FROM ros_gis.crop_season_weekly_progress p
            WHERE p.area_type = $1
            AND p.calculation_method = $2
            AND p.week_start_date = (
                SELECT MAX(week_start_date) 
                FROM ros_gis.crop_season_weekly_progress
                WHERE area_type = $1
            )
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, area_type, calculation_method)
        
        if not row:
            return {}
        
        return {
            'area_type': area_type,
            'calculation_method': calculation_method,
            'summary': {
                'area_count': row['area_count'],
                'crop_types': row['crop_types'],
                'total_area_rai': float(row['total_area_rai']) if row['total_area_rai'] else 0,
                'total_demand_to_date': float(row['total_demand_to_date']) if row['total_demand_to_date'] else 0,
                'total_delivered_to_date': float(row['total_delivered_to_date']) if row['total_delivered_to_date'] else 0,
                'total_projected_demand': float(row['total_projected_demand']) if row['total_projected_demand'] else 0,
                'overall_fulfillment_pct': (
                    float(row['total_delivered_to_date']) / float(row['total_demand_to_date']) * 100
                    if row['total_demand_to_date'] and float(row['total_demand_to_date']) > 0 else 0
                ),
                'season_completion_pct': (
                    float(row['total_demand_to_date']) / float(row['total_projected_demand']) * 100
                    if row['total_projected_demand'] and float(row['total_projected_demand']) > 0 else 0
                ),
                'avg_delivery_efficiency': float(row['avg_delivery_efficiency']) if row['avg_delivery_efficiency'] else 0,
                'avg_stress_indicator': float(row['avg_stress_indicator']) if row['avg_stress_indicator'] else 0
            }
        }
    
    async def get_stressed_areas(
        self,
        stress_threshold: float = 0.7,
        area_type: str = "section"
    ) -> List[Dict]:
        """Get areas with high water stress indicators"""
        query = """
            SELECT 
                p.area_id,
                p.area_type,
                p.crop_type,
                p.stress_indicator,
                p.demand_vs_delivered_ratio,
                p.weekly_adjusted_demand_m3,
                p.weekly_delivered_m3,
                p.remaining_weeks
            FROM ros_gis.crop_season_weekly_progress p
            WHERE p.stress_indicator >= $1
            AND p.area_type = $2
            AND p.week_start_date = (
                SELECT MAX(week_start_date) 
                FROM ros_gis.crop_season_weekly_progress
                WHERE area_type = $2
            )
            ORDER BY p.stress_indicator DESC
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, stress_threshold, area_type)
        
        return [
            {
                'area_id': row['area_id'],
                'area_type': row['area_type'],
                'crop_type': row['crop_type'],
                'stress_indicator': float(row['stress_indicator']),
                'demand_vs_delivered_ratio': float(row['demand_vs_delivered_ratio']),
                'demand_deficit_m3': float(row['weekly_adjusted_demand_m3'] - row['weekly_delivered_m3']),
                'remaining_weeks': row['remaining_weeks'],
                'priority': 'high' if float(row['stress_indicator']) > 0.8 else 'medium'
            }
            for row in rows
        ]
    
    async def update_delivery_data(
        self,
        area_id: str,
        area_type: str,
        week_date: date,
        delivered_m3: float,
        scheduled_m3: float
    ):
        """Update actual delivery data for tracking"""
        query = """
            UPDATE ros_gis.crop_season_weekly_progress
            SET 
                weekly_delivered_m3 = $1,
                weekly_scheduled_m3 = $2,
                delivery_efficiency_pct = CASE 
                    WHEN $2 > 0 THEN $1 / $2 * 100 
                    ELSE 0 
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE area_id = $3
            AND area_type = $4
            AND week_start_date <= $5
            AND week_end_date >= $5
        """
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                query,
                delivered_m3,
                scheduled_m3,
                area_id,
                area_type,
                week_date
            )
    
    def _format_demand_row(self, row) -> Dict:
        """Format database row to response dict"""
        return {
            'id': str(row['id']),
            'week_start_date': row['week_start_date'].isoformat(),
            'week_end_date': row['week_end_date'].isoformat(),
            'area_id': row['area_id'],
            'area_type': row['area_type'],
            'calculation_method': row['calculation_method'],
            'area_rai': float(row['area_rai']),
            'active_plots': row['active_plots'],
            'et0_mm': float(row['et0_mm']),
            'avg_kc_factor': float(row['avg_kc_factor']),
            'gross_demand_mm': float(row['gross_demand_mm']),
            'net_demand_mm': float(row['net_demand_mm']),
            'gross_demand_m3': float(row['gross_demand_m3']),
            'net_demand_m3': float(row['net_demand_m3']),
            'effective_rainfall_mm': float(row['effective_rainfall_mm']),
            'effective_rainfall_m3': float(row['effective_rainfall_m3']),
            'sensor_adjustment_factor': float(row['sensor_adjustment_factor']),
            'adjusted_demand_m3': float(row['adjusted_demand_m3']),
            'final_demand_m3': float(row.get('final_demand_m3', row['adjusted_demand_m3'])),
            'adjustment_percentage': float(row.get('adjustment_percentage', 0)),
            'water_level_avg_cm': float(row['water_level_avg_cm']) if row.get('water_level_avg_cm') else None,
            'data_source': row['data_source'],
            'calculation_timestamp': row['calculation_timestamp'].isoformat(),
            'updated_at': row['updated_at'].isoformat()
        }
    
    def _format_progress_row(self, row) -> Dict:
        """Format season progress row"""
        return {
            'id': str(row['id']),
            'area_id': row['area_id'],
            'area_type': row['area_type'],
            'crop_type': row['crop_type'],
            'planting_date': row['planting_date'].isoformat(),
            'expected_harvest_date': row['expected_harvest_date'].isoformat(),
            'week_number': row['week_number'],
            'week_start_date': row['week_start_date'].isoformat(),
            'growth_stage': row['growth_stage'],
            'area_rai': float(row['area_rai']),
            'weekly_demand_m3': float(row['weekly_adjusted_demand_m3']),
            'weekly_delivered_m3': float(row['weekly_delivered_m3']) if row.get('weekly_delivered_m3') else 0,
            'cumulative_demand_m3': float(row['cumulative_net_demand_m3']),
            'cumulative_delivered_m3': float(row['cumulative_delivered_m3']),
            'remaining_weeks': row['remaining_weeks'],
            'projected_total_demand_m3': float(row['projected_total_demand_m3']) if row.get('projected_total_demand_m3') else 0,
            'fulfillment_pct': float(row.get('fulfillment_pct', 0)),
            'season_progress_pct': float(row.get('season_progress_pct', 0)),
            'stress_indicator': float(row['stress_indicator']) if row.get('stress_indicator') else 0
        }


# Singleton instance
weekly_demand_repo = WeeklyDemandRepository()
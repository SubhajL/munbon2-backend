"""
Weekly Water Demand Calculator V2 - Using actual gis.zone table
Calculates and stores weekly water demands using pp-zz-cc-ss format
"""

import asyncio
import asyncpg
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
import json

from db.database import Database
from db.weekly_demand_repository import WeeklyDemandRepository
from clients.ros_client import ROSClient
from clients.rid_ms_client import RIDMSClient
from clients.weather_client import WeatherClient
from utils.date_utils import get_week_number, get_week_date_range
from utils.logger import get_logger

logger = get_logger(__name__)


class WeeklyDemandCalculatorV2:
    """Calculates weekly water demands for sections using actual gis.zone data"""
    
    def __init__(self):
        self.db = Database()
        self.repository = WeeklyDemandRepository()
        self.ros_client = ROSClient()
        self.rid_ms_client = RIDMSClient()
        self.weather_client = WeatherClient()
    
    async def calculate_weekly_demands(self):
        """Main calculation process - runs every Monday at 3 AM"""
        try:
            logger.info("Starting weekly demand calculation V2")
            start_time = datetime.now()
            
            # Get current week's date range
            week_start, week_end = get_week_date_range(date.today())
            
            # Get water levels from last week
            last_week_water_levels = await self._get_last_week_water_levels()
            
            # Process sections from gis.zone table
            sections_processed = await self._process_sections_from_gis(
                week_start, week_end, last_week_water_levels
            )
            
            # Calculate zone totals
            zones_processed = await self._calculate_zone_totals(week_start, week_end)
            
            # Calculate munbon total
            await self._calculate_munbon_total(week_start, week_end)
            
            # Update crop season progress
            await self._update_season_progress(week_start)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "Weekly demand calculation V2 completed",
                sections_processed=sections_processed,
                zones_processed=zones_processed,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(
                "Weekly demand calculation V2 failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _process_sections_from_gis(
        self,
        week_start: date,
        week_end: date,
        last_week_water_levels: Dict[str, float]
    ) -> int:
        """Process all sections from gis.zone table in postgres database"""
        section_count = 0
        
        # Connect to postgres database for GIS data
        gis_db_config = {
            'host': self.db.config['host'],
            'port': self.db.config['port'],
            'user': self.db.config['user'],
            'password': self.db.config['password'],
            'database': 'postgres'  # GIS data is in postgres database
        }
        
        gis_conn = await asyncpg.connect(**gis_db_config)
        
        try:
            # Query sections from gis.zone table (singular)
            query = """
                SELECT 
                    code as section_id,  -- pp-zz-cc-ss format
                    layer_name,          -- contains zone info
                    props->>'Area_Rai' as area_rai,
                    props->>'AOS_Station' as aos_station,
                    props->>'Crop_Type' as crop_type,
                    props->>'Soil_Type' as soil_type,
                    props->>'Elevation' as elevation,
                    -- Extract zone from code
                    SUBSTRING(code FROM 4 FOR 2)::int as zone_id
                FROM gis.zone
                WHERE code LIKE '01-%'  -- Munbon project code
                AND props->>'Area_Rai' IS NOT NULL
                ORDER BY code
            """
            
            sections = await gis_conn.fetch(query)
            
            for section in sections:
                try:
                    section_id = section['section_id']
                    
                    # Get last week's water level for this section
                    last_week_water_mm = last_week_water_levels.get(section_id, 0)
                    
                    # Calculate demands using ROS method
                    ros_demand = await self._calculate_section_demand(
                        section, week_start, week_end, 'ros'
                    )
                    
                    # Calculate demands using RID-MS method
                    rid_ms_demand = await self._calculate_section_demand(
                        section, week_start, week_end, 'rid_ms'
                    )
                    
                    # Calculate combined demand (weighted average)
                    combined_demand = self._calculate_combined_demand(
                        ros_demand, rid_ms_demand
                    )
                    
                    # Apply water level adjustment (subtraction)
                    for demand in [ros_demand, rid_ms_demand, combined_demand]:
                        # Store last week's water level
                        demand['last_week_water_level_mm'] = last_week_water_mm
                        
                        # Calculate adjusted demand: current demand - last week's water
                        original_demand_mm = demand['gross_demand_mm']
                        adjusted_demand_mm = max(0, original_demand_mm - last_week_water_mm)
                        
                        demand['water_adjustment_mm'] = last_week_water_mm
                        demand['adjusted_demand_mm'] = adjusted_demand_mm
                        
                        # Update m3 values based on adjusted mm
                        area_rai = demand['area_rai']
                        demand['adjusted_demand_m3'] = (adjusted_demand_mm * area_rai * 1600) / 1000
                    
                    # Store all three calculations
                    await self._store_weekly_demand(
                        ros_demand, last_week_water_mm, 'section'
                    )
                    await self._store_weekly_demand(
                        rid_ms_demand, last_week_water_mm, 'section'
                    )
                    await self._store_weekly_demand(
                        combined_demand, last_week_water_mm, 'section'
                    )
                    
                    section_count += 1
                    
                except Exception as e:
                    logger.error(
                        "Failed to calculate section demand",
                        section_id=section_id,
                        error=str(e)
                    )
        
        finally:
            await gis_conn.close()
            
        return section_count
    
    async def _calculate_zone_totals(
        self,
        week_start: date,
        week_end: date
    ) -> int:
        """Calculate zone totals by aggregating sections"""
        zone_count = 0
        
        # First get unique zones from postgres database
        gis_db_config = {
            'host': self.db.config['host'],
            'port': self.db.config['port'],
            'user': self.db.config['user'],
            'password': self.db.config['password'],
            'database': 'postgres'
        }
        
        gis_conn = await asyncpg.connect(**gis_db_config)
        
        try:
            # Get unique zones
            query = """
                SELECT DISTINCT
                    SUBSTRING(code FROM 4 FOR 2)::int as zone_id
                FROM gis.zone
                WHERE code LIKE '01-%'
                ORDER BY zone_id
            """
            
            zones = await gis_conn.fetch(query)
        finally:
            await gis_conn.close()
            
        # Now aggregate demands from munbon_dev database
        async with self.db.get_connection() as conn:
            
            for zone in zones:
                zone_id = zone['zone_id']
                
                # Aggregate section demands for each calculation method
                for method in ['ros', 'rid_ms', 'combined']:
                    try:
                        # Get aggregated demand from sections
                        agg_query = """
                            SELECT 
                                SUM(area_rai) as total_area_rai,
                                COUNT(*) as section_count,
                                SUM(gross_demand_m3) as total_gross_demand_m3,
                                SUM(net_demand_m3) as total_net_demand_m3,
                                SUM(effective_rainfall_m3) as total_rainfall_m3,
                                SUM(adjusted_demand_m3) as total_adjusted_demand_m3,
                                AVG(et0_mm) as avg_et0_mm,
                                AVG(avg_kc_factor) as avg_kc_factor
                            FROM ros_gis.weekly_water_demands
                            WHERE week_start_date = $1
                            AND area_type = 'section'
                            AND calculation_method = $2
                            AND SUBSTRING(area_id FROM 4 FOR 2)::int = $3
                        """
                        
                        result = await conn.fetchrow(
                            agg_query, week_start, method, zone_id
                        )
                        
                        if result and result['section_count'] > 0:
                            # Create zone demand record
                            zone_demand = {
                                'week_start_date': week_start,
                                'week_end_date': week_end,
                                'area_id': f"01-{zone_id:02d}",  # Zone ID in pp-zz format
                                'area_type': 'zone',
                                'calculation_method': method,
                                'area_rai': float(result['total_area_rai'] or 0),
                                'active_plots': result['section_count'],
                                'et0_mm': float(result['avg_et0_mm'] or 0),
                                'avg_kc_factor': float(result['avg_kc_factor'] or 0),
                                'gross_demand_m3': float(result['total_gross_demand_m3'] or 0),
                                'net_demand_m3': float(result['total_net_demand_m3'] or 0),
                                'effective_rainfall_m3': float(result['total_rainfall_m3'] or 0),
                                'adjusted_demand_m3': float(result['total_adjusted_demand_m3'] or 0),
                                'data_source': 'aggregated_from_sections'
                            }
                            
                            # Store zone demand
                            await self.repository.store_weekly_demand(zone_demand)
                            
                            if method == 'combined':
                                zone_count += 1
                                
                    except Exception as e:
                        logger.error(
                            "Failed to calculate zone demand",
                            zone_id=zone_id,
                            method=method,
                            error=str(e)
                        )
        
        return zone_count
    
    async def _calculate_munbon_total(
        self,
        week_start: date,
        week_end: date
    ):
        """Calculate total for entire Munbon area"""
        async with self.db.get_connection() as conn:
            for method in ['ros', 'rid_ms', 'combined']:
                # Aggregate all zones
                query = """
                    SELECT 
                        SUM(area_rai) as total_area_rai,
                        COUNT(DISTINCT area_id) as zone_count,
                        SUM(gross_demand_m3) as total_gross_demand_m3,
                        SUM(net_demand_m3) as total_net_demand_m3,
                        SUM(effective_rainfall_m3) as total_rainfall_m3,
                        SUM(adjusted_demand_m3) as total_adjusted_demand_m3,
                        AVG(et0_mm) as avg_et0_mm,
                        AVG(avg_kc_factor) as avg_kc_factor
                    FROM ros_gis.weekly_water_demands
                    WHERE week_start_date = $1
                    AND area_type = 'zone'
                    AND calculation_method = $2
                """
                
                result = await conn.fetchrow(query, week_start, method)
                
                if result and result['zone_count'] > 0:
                    munbon_demand = {
                        'week_start_date': week_start,
                        'week_end_date': week_end,
                        'area_id': '01',  # Munbon project code
                        'area_type': 'munbon',
                        'calculation_method': method,
                        'area_rai': float(result['total_area_rai'] or 0),
                        'active_plots': result['zone_count'],
                        'et0_mm': float(result['avg_et0_mm'] or 0),
                        'avg_kc_factor': float(result['avg_kc_factor'] or 0),
                        'gross_demand_m3': float(result['total_gross_demand_m3'] or 0),
                        'net_demand_m3': float(result['total_net_demand_m3'] or 0),
                        'effective_rainfall_m3': float(result['total_rainfall_m3'] or 0),
                        'adjusted_demand_m3': float(result['total_adjusted_demand_m3'] or 0),
                        'data_source': 'aggregated_from_zones'
                    }
                    
                    await self.repository.store_weekly_demand(munbon_demand)
    
    async def _calculate_section_demand(
        self,
        section: Dict,
        week_start: date,
        week_end: date,
        method: str
    ) -> Dict:
        """Calculate weekly demand for a section"""
        section_id = section['section_id']
        zone_id = section['zone_id']
        aos_station = section['aos_station'] or 'default'
        area_rai = float(section['area_rai'] or 0)
        
        # Get week number for data lookup
        week_number, year = get_week_number(week_start)
        
        # Get ET0 for this week
        et0_data = await self._get_weekly_et0(aos_station, week_number, year)
        
        # Get effective rainfall
        rainfall_data = await self._get_effective_rainfall(zone_id, week_number, year)
        
        # Get active plots and crops
        crop_data = await self._get_section_crops(section_id)
        
        if method == 'ros':
            # Traditional ROS calculation
            demand_result = await self.ros_client.calculate_demand({
                'section_id': section_id,
                'week': week_number,
                'year': year,
                'area_rai': area_rai,
                'et0_mm': et0_data['et0_mm'],
                'crop_data': crop_data,
                'effective_rainfall_mm': rainfall_data['effective_rainfall_mm']
            })
        else:  # rid_ms
            # AquaCrop-based calculation
            demand_result = await self.rid_ms_client.calculate_demand({
                'section_id': section_id,
                'week': week_number,
                'year': year,
                'area_rai': area_rai,
                'et0_mm': et0_data['et0_mm'],
                'crop_data': crop_data,
                'effective_rainfall_mm': rainfall_data['effective_rainfall_mm']
            })
        
        return {
            'week_start_date': week_start,
            'week_end_date': week_end,
            'area_id': section_id,
            'area_type': 'section',
            'calculation_method': method,
            'area_rai': area_rai,
            'active_plots': len(crop_data),
            'et0_mm': et0_data['et0_mm'],
            'avg_kc_factor': demand_result.get('avg_kc_factor', 0),
            'gross_demand_mm': demand_result.get('gross_demand_mm', 0),
            'net_demand_mm': demand_result.get('net_demand_mm', 0),
            'gross_demand_m3': demand_result.get('gross_demand_m3', 0),
            'net_demand_m3': demand_result.get('net_demand_m3', 0),
            'effective_rainfall_mm': rainfall_data['effective_rainfall_mm'],
            'effective_rainfall_m3': rainfall_data['effective_rainfall_m3'],
            'data_source': f"{method}_calculation",
            # These will be filled in later during adjustment
            'last_week_water_level_mm': 0,
            'water_adjustment_mm': 0,
            'adjusted_demand_mm': 0,
            'adjusted_demand_m3': 0
        }
    
    async def _get_section_crops(self, section_id: str) -> List[Dict]:
        """Get active crops for a section"""
        async with self.db.get_connection() as conn:
            query = """
                SELECT 
                    plot_code,
                    crop_type,
                    planting_date,
                    area_rai
                FROM ros_gis.plot_planting_dates
                WHERE section_id = $1
                AND is_active = true
                AND planting_date <= CURRENT_DATE
                AND (harvest_date IS NULL OR harvest_date >= CURRENT_DATE)
            """
            
            rows = await conn.fetch(query, section_id)
            return [dict(row) for row in rows]
    
    async def _get_weekly_et0(
        self,
        aos_station: str,
        week_number: int,
        year: int
    ) -> Dict[str, float]:
        """Get weekly ET0 data"""
        async with self.db.get_connection() as conn:
            query = """
                SELECT et0_mm
                FROM ros.weekly_eto
                WHERE aos_station_id = $1
                AND week_number = $2
                AND year = $3
            """
            
            result = await conn.fetchrow(query, aos_station, week_number, year)
            
            if result:
                return {'et0_mm': float(result['et0_mm'])}
            else:
                # Default value
                return {'et0_mm': 35.0}
    
    async def _get_effective_rainfall(
        self,
        zone_id: int,
        week_number: int,
        year: int
    ) -> Dict[str, float]:
        """Get effective rainfall data"""
        async with self.db.get_connection() as conn:
            query = """
                SELECT 
                    effective_rainfall_mm,
                    (effective_rainfall_mm * area_rai * 10 / 1000) as effective_rainfall_m3
                FROM ros.zone_effective_rainfall
                WHERE zone_id = $1
                AND week_number = $2
                AND year = $3
            """
            
            result = await conn.fetchrow(query, zone_id, week_number, year)
            
            if result:
                return {
                    'effective_rainfall_mm': float(result['effective_rainfall_mm']),
                    'effective_rainfall_m3': float(result['effective_rainfall_m3'])
                }
            else:
                return {
                    'effective_rainfall_mm': 0.0,
                    'effective_rainfall_m3': 0.0
                }
    
    async def _get_last_week_water_levels(self) -> Dict[str, float]:
        """Get last week's accumulated water levels in mm"""
        try:
            # Get last week's date range
            today = date.today()
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)
            
            logger.info(f"Fetching water levels for week {last_monday} to {last_sunday}")
            
            # Query to get average water levels in mm
            query = """
                SELECT 
                    section_id,
                    AVG(COALESCE(avg_water_level_mm, avg_water_level_m * 1000)) as avg_water_level_mm
                FROM ros_gis.water_level_aggregations
                WHERE date BETWEEN $1 AND $2
                GROUP BY section_id
            """
            
            async with self.db.get_connection() as conn:
                rows = await conn.fetch(query, last_monday, last_sunday)
                
                water_levels = {}
                
                for row in rows:
                    section_id = row['section_id']
                    # Water level in mm - this will be subtracted from demand
                    water_level_mm = float(row['avg_water_level_mm']) if row['avg_water_level_mm'] else 0
                    water_levels[section_id] = water_level_mm
                    
                    if water_level_mm > 20:  # Log high water levels
                        logger.info(
                            f"Section {section_id}: High water level {water_level_mm:.1f}mm from last week"
                        )
                
                logger.info(f"Retrieved water levels for {len(water_levels)} sections")
                
                # Also get current week's water levels for reporting
                current_monday = today - timedelta(days=today.weekday())
                current_levels_query = """
                    SELECT section_id, 
                           AVG(COALESCE(avg_water_level_mm, avg_water_level_m * 1000)) as avg_level_mm
                    FROM ros_gis.water_level_aggregations
                    WHERE date >= $1
                    GROUP BY section_id
                """
                
                current_levels = await conn.fetch(current_levels_query, current_monday)
                self._current_water_levels_mm = {
                    row['section_id']: float(row['avg_level_mm']) 
                    for row in current_levels if row['avg_level_mm']
                }
                
                return water_levels
                
        except Exception as e:
            logger.error(f"Failed to get water levels: {str(e)}")
            # Return empty dict on error to continue with no adjustment
            return {}
    
    def _calculate_combined_demand(
        self,
        ros_demand: Dict,
        rid_ms_demand: Dict
    ) -> Dict:
        """Calculate weighted average of ROS and RID-MS demands"""
        # 60% ROS, 40% RID-MS weighting
        ros_weight = 0.6
        rid_ms_weight = 0.4
        
        combined = ros_demand.copy()
        combined['calculation_method'] = 'combined'
        
        # Weighted average of demand values
        for field in ['gross_demand_mm', 'net_demand_mm', 'gross_demand_m3', 'net_demand_m3']:
            combined[field] = (
                ros_demand[field] * ros_weight +
                rid_ms_demand[field] * rid_ms_weight
            )
        
        # Average of factors
        combined['avg_kc_factor'] = (
            ros_demand['avg_kc_factor'] * ros_weight +
            rid_ms_demand['avg_kc_factor'] * rid_ms_weight
        )
        
        return combined
    
    async def _store_weekly_demand(
        self,
        demand: Dict,
        last_week_water_mm: float,
        area_type: str
    ):
        """Store calculated demand in database with water level info"""
        # Water adjustment is already calculated in demand dict
        # Just add current water level info if available
        section_id = demand.get('area_id')
        if hasattr(self, '_current_water_levels_mm') and section_id in self._current_water_levels_mm:
            current_water_mm = self._current_water_levels_mm[section_id]
            demand['water_level_m'] = current_water_mm / 1000  # Convert to meters for display
            
            # Determine water level status based on current level in meters
            water_level_m = current_water_mm / 1000
            if water_level_m < 0.02:
                demand['water_level_status'] = 'CRITICAL_LOW'
            elif water_level_m < 0.05:
                demand['water_level_status'] = 'WARNING_LOW'
            elif water_level_m < 0.10:
                demand['water_level_status'] = 'OPTIMAL'
            elif water_level_m < 0.15:
                demand['water_level_status'] = 'WARNING_HIGH'
            elif water_level_m < 0.20:
                demand['water_level_status'] = 'CRITICAL_HIGH'
            else:
                demand['water_level_status'] = 'ABOVE_CRITICAL'
            
            demand['water_level_adjustment_applied'] = last_week_water_mm > 0
        
        await self.repository.store_weekly_demand(demand)
    
    async def _update_season_progress(self, week_start: date):
        """Update crop season progress tracking with water level info"""
        try:
            logger.info("Updating crop season progress with water level data")
            
            async with self.db.get_connection() as conn:
                # Update crop progress with water level status
                update_query = """
                    UPDATE ros_gis.crop_season_weekly_progress csp
                    SET 
                        avg_water_level_m = wla.avg_level,
                        water_level_status = CASE
                            WHEN wla.avg_level < 0.02 THEN 'CRITICAL_LOW'
                            WHEN wla.avg_level < 0.05 THEN 'WARNING_LOW'
                            WHEN wla.avg_level < 0.10 THEN 'OPTIMAL'
                            WHEN wla.avg_level < 0.15 THEN 'WARNING_HIGH'
                            WHEN wla.avg_level < 0.20 THEN 'CRITICAL_HIGH'
                            ELSE 'ABOVE_CRITICAL'
                        END,
                        water_stress_days = CASE
                            WHEN wla.avg_level < 0.05 THEN 
                                COALESCE(csp.water_stress_days, 0) + 7
                            ELSE 
                                COALESCE(csp.water_stress_days, 0)
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    FROM (
                        SELECT section_id, AVG(avg_water_level_m) as avg_level
                        FROM ros_gis.water_level_aggregations
                        WHERE date >= $1 AND date < $1 + INTERVAL '7 days'
                        GROUP BY section_id
                    ) wla
                    WHERE csp.area_id = wla.section_id
                    AND csp.week_start_date = $1
                    AND csp.area_type = 'section'
                """
                
                result = await conn.execute(update_query, week_start)
                
                # Also update zone and munbon totals
                zone_update_query = """
                    UPDATE ros_gis.crop_season_weekly_progress csp
                    SET 
                        avg_water_level_m = zone_wl.avg_level,
                        water_level_status = zone_wl.status,
                        water_stress_days = zone_wl.stress_days,
                        updated_at = CURRENT_TIMESTAMP
                    FROM (
                        SELECT 
                            SUBSTRING(area_id FROM 1 FOR 5) as zone_id,
                            AVG(avg_water_level_m) as avg_level,
                            MODE() WITHIN GROUP (ORDER BY water_level_status) as status,
                            MAX(water_stress_days) as stress_days
                        FROM ros_gis.crop_season_weekly_progress
                        WHERE week_start_date = $1
                        AND area_type = 'section'
                        GROUP BY SUBSTRING(area_id FROM 1 FOR 5)
                    ) zone_wl
                    WHERE csp.area_id = zone_wl.zone_id
                    AND csp.week_start_date = $1
                    AND csp.area_type = 'zone'
                """
                
                await conn.execute(zone_update_query, week_start)
                
                logger.info("Crop season progress updated with water level data")
                
        except Exception as e:
            logger.error(f"Failed to update season progress: {str(e)}")
            # Continue even if update fails
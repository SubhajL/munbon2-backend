"""
Weekly Demand Calculator Service
Calculates and stores weekly water demands for sections and zones
Runs every Monday at 3 AM to prepare demands for the current week
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import aiocron

from core import get_logger
from db import DatabaseManager
from config import settings
from clients import ROSClient, RIDMSClient, SensorDataClient
from services.calculation_engine import CalculationEngine
from utils.date_utils import get_week_number, get_current_week_dates

logger = get_logger(__name__)


class WeeklyDemandCalculator:
    """Calculates and stores weekly demands for immediate implementation"""
    
    def __init__(self):
        self.logger = logger.bind(service="weekly_demand_calculator")
        self.db = DatabaseManager()
        self.ros_client = ROSClient()
        self.ridms_client = RIDMSClient()
        self.sensor_client = SensorDataClient()
        self.calculator = CalculationEngine()
        self.weekly_task = None
        self.is_running = False
    
    async def start_scheduler(self):
        """Start the weekly scheduler - runs Monday at 3 AM"""
        if self.is_running:
            self.logger.warning("Weekly demand calculator already running")
            return
        
        # Schedule for Monday 3 AM every week
        self.weekly_task = aiocron.crontab('0 3 * * 1', func=self.calculate_current_week_demands)
        self.is_running = True
        
        self.logger.info("Weekly demand calculator started (runs Monday at 3:00 AM)")
        
        # Run immediately in development
        if settings.environment == "development":
            self.logger.info("Development mode: Running initial calculation")
            asyncio.create_task(self.calculate_current_week_demands())
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.weekly_task:
            self.weekly_task.stop()
            self.weekly_task = None
            self.is_running = False
            self.logger.info("Weekly demand calculator stopped")
    
    async def calculate_current_week_demands(self):
        """Calculate demands for the current week with sensor adjustments"""
        start_time = datetime.now()
        
        # Get current week dates
        week_start, week_end = get_current_week_dates()
        week_number, year = get_week_number(week_start)
        
        try:
            self.logger.info(
                "Starting weekly demand calculation for current week",
                week_start=week_start.isoformat(),
                week_end=week_end.isoformat(),
                week_number=week_number,
                year=year
            )
            
            # Get sensor adjustments from last week
            last_week_adjustments = await self._get_last_week_sensor_adjustments()
            
            # Get active areas
            active_sections = await self._get_active_sections()
            active_zones = await self._get_active_zones()
            
            # Calculate and store section demands
            section_count = 0
            for section in active_sections:
                try:
                    # Calculate both ROS and RID-MS demands
                    ros_demand = await self._calculate_section_demand(
                        section, week_start, week_end, 'ros'
                    )
                    ridms_demand = await self._calculate_section_demand(
                        section, week_start, week_end, 'rid_ms'
                    )
                    combined_demand = self._calculate_combined_demand(ros_demand, ridms_demand)
                    
                    # Apply sensor adjustments
                    adjustment_factor = last_week_adjustments.get(
                        section['section_id'], 1.0
                    )
                    
                    # Store all three calculations
                    await self._store_weekly_demand(
                        ros_demand, adjustment_factor, 'section'
                    )
                    await self._store_weekly_demand(
                        ridms_demand, adjustment_factor, 'section'
                    )
                    await self._store_weekly_demand(
                        combined_demand, adjustment_factor, 'section'
                    )
                    
                    section_count += 1
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to calculate section demand",
                        section_id=section['section_id'],
                        error=str(e)
                    )
            
            # Calculate and store zone demands
            zone_count = 0
            for zone in active_zones:
                try:
                    # Aggregate from sections
                    ros_zone_demand = await self._aggregate_zone_demand(
                        zone['zone_id'], week_start, week_end, 'ros'
                    )
                    ridms_zone_demand = await self._aggregate_zone_demand(
                        zone['zone_id'], week_start, week_end, 'rid_ms'
                    )
                    combined_zone_demand = self._calculate_combined_demand(
                        ros_zone_demand, ridms_zone_demand
                    )
                    
                    # Zone adjustment is average of section adjustments
                    zone_adjustment = await self._get_zone_adjustment_factor(
                        zone['zone_id'], last_week_adjustments
                    )
                    
                    # Store zone demands
                    await self._store_weekly_demand(
                        ros_zone_demand, zone_adjustment, 'zone'
                    )
                    await self._store_weekly_demand(
                        ridms_zone_demand, zone_adjustment, 'zone'
                    )
                    await self._store_weekly_demand(
                        combined_zone_demand, zone_adjustment, 'zone'
                    )
                    
                    zone_count += 1
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to calculate zone demand",
                        zone_id=zone['zone_id'],
                        error=str(e)
                    )
            
            # Calculate munbon total
            await self._calculate_munbon_total(week_start, week_end)
            
            # Update crop season progress
            await self._update_season_progress(week_start)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(
                "Weekly demand calculation completed",
                sections_processed=section_count,
                zones_processed=zone_count,
                duration_seconds=duration
            )
            
        except Exception as e:
            self.logger.error(
                "Weekly demand calculation failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _get_last_week_sensor_adjustments(self) -> Dict[str, float]:
        """Get sensor-based adjustment factors from last week"""
        last_monday = date.today() - timedelta(days=7)
        
        # Query aggregated sensor data from last week
        query = """
            SELECT 
                s.section_id,
                AVG(wl.water_level_cm) as avg_water_level,
                AVG(wl.water_level_cm) / s.target_water_level_cm as level_ratio
            FROM sensor_data.water_level_readings wl
            JOIN sensor_management.sensor_mappings sm ON wl.sensor_id = sm.sensor_id
            JOIN ros.sections s ON sm.section_id = s.section_id
            WHERE wl.timestamp >= $1 AND wl.timestamp < $2
            AND wl.quality_score >= 0.8
            GROUP BY s.section_id, s.target_water_level_cm
        """
        
        adjustments = {}
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(
                query,
                last_monday,
                last_monday + timedelta(days=7)
            )
            
            for row in rows:
                # Calculate adjustment factor based on water level
                level_ratio = float(row['level_ratio'])
                
                if level_ratio < 0.7:  # Low water
                    adjustment = 1.2  # Increase demand by 20%
                elif level_ratio > 1.3:  # High water
                    adjustment = 0.8  # Reduce demand by 20%
                else:
                    # Linear interpolation
                    adjustment = 1.0 + (1.0 - level_ratio) * 0.2
                
                adjustments[row['section_id']] = adjustment
        
        return adjustments
    
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
        aos_station = section['aos_station_id']
        
        # Get week number for data lookup
        week_number, year = get_week_number(week_start)
        
        # Get ET0 for this week
        et0_data = await self._get_weekly_et0(aos_station, week_number, year)
        
        # Get effective rainfall
        rainfall_data = await self._get_effective_rainfall(zone_id, week_number, year)
        
        # Get active plots and crops
        plots = await self._get_section_active_plots(section_id)
        
        # Calculate demands by crop type
        total_gross_demand_m3 = 0
        total_net_demand_m3 = 0
        total_area_rai = 0
        weighted_kc_sum = 0
        
        for plot in plots:
            area_rai = float(plot['area_rai'])
            crop_type = plot['crop_type']
            crop_week = plot['crop_week_number']
            
            # Get Kc factor
            kc = await self._get_kc_factor(crop_type, crop_week, method)
            
            # Calculate plot demand
            if method == 'ros':
                plot_demand = self._calculate_ros_demand(
                    et0_data['et0_mm'],
                    kc,
                    rainfall_data['effective_mm'],
                    area_rai
                )
            else:  # rid_ms
                plot_demand = await self._calculate_ridms_demand(
                    et0_data['et0_mm'],
                    kc,
                    rainfall_data['effective_mm'],
                    area_rai,
                    crop_type
                )
            
            total_gross_demand_m3 += plot_demand['gross_demand_m3']
            total_net_demand_m3 += plot_demand['net_demand_m3']
            total_area_rai += area_rai
            weighted_kc_sum += kc * area_rai
        
        # Calculate averages
        avg_kc = weighted_kc_sum / total_area_rai if total_area_rai > 0 else 0
        gross_demand_mm = total_gross_demand_m3 / (total_area_rai * 1.6) if total_area_rai > 0 else 0
        net_demand_mm = total_net_demand_m3 / (total_area_rai * 1.6) if total_area_rai > 0 else 0
        
        return {
            'week_start_date': week_start,
            'week_end_date': week_end,
            'area_id': section_id,
            'area_type': 'section',
            'calculation_method': method,
            'area_rai': total_area_rai,
            'active_plots': len(plots),
            'et0_mm': et0_data['et0_mm'],
            'avg_kc_factor': avg_kc,
            'gross_demand_mm': gross_demand_mm,
            'net_demand_mm': net_demand_mm,
            'gross_demand_m3': total_gross_demand_m3,
            'net_demand_m3': total_net_demand_m3,
            'effective_rainfall_mm': rainfall_data['effective_mm'],
            'effective_rainfall_m3': rainfall_data['effective_mm'] * total_area_rai * 1.6,
            'data_source': f"{method.upper()} calculation with {aos_station} weather data"
        }
    
    async def _aggregate_zone_demand(
        self,
        zone_id: int,
        week_start: date,
        week_end: date,
        method: str
    ) -> Dict:
        """Aggregate zone demand from sections"""
        query = """
            SELECT 
                COUNT(*) as section_count,
                SUM(area_rai) as total_area_rai,
                SUM(active_plots) as total_plots,
                AVG(et0_mm) as avg_et0,
                SUM(avg_kc_factor * area_rai) / SUM(area_rai) as weighted_kc,
                SUM(gross_demand_m3) as total_gross_m3,
                SUM(net_demand_m3) as total_net_m3,
                SUM(effective_rainfall_m3) as total_rainfall_m3,
                AVG(effective_rainfall_mm) as avg_rainfall_mm
            FROM ros_gis.weekly_water_demands
            WHERE area_type = 'section'
            AND area_id LIKE $1
            AND week_start_date = $2
            AND calculation_method = $3
        """
        
        zone_pattern = f"{zone_id}-%"
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, zone_pattern, week_start, method)
        
        if not row or row['section_count'] == 0:
            return None
        
        total_area = float(row['total_area_rai'])
        gross_mm = float(row['total_gross_m3']) / (total_area * 1.6) if total_area > 0 else 0
        net_mm = float(row['total_net_m3']) / (total_area * 1.6) if total_area > 0 else 0
        
        return {
            'week_start_date': week_start,
            'week_end_date': week_end,
            'area_id': str(zone_id),
            'area_type': 'zone',
            'calculation_method': method,
            'area_rai': total_area,
            'active_plots': int(row['total_plots']),
            'et0_mm': float(row['avg_et0']),
            'avg_kc_factor': float(row['weighted_kc']),
            'gross_demand_mm': gross_mm,
            'net_demand_mm': net_mm,
            'gross_demand_m3': float(row['total_gross_m3']),
            'net_demand_m3': float(row['total_net_m3']),
            'effective_rainfall_mm': float(row['avg_rainfall_mm']),
            'effective_rainfall_m3': float(row['total_rainfall_m3']),
            'data_source': f"Aggregated from {row['section_count']} sections"
        }
    
    async def _calculate_munbon_total(self, week_start: date, week_end: date):
        """Calculate total munbon demand"""
        for method in ['ros', 'rid_ms', 'combined']:
            query = """
                SELECT 
                    COUNT(*) as zone_count,
                    SUM(area_rai) as total_area_rai,
                    SUM(active_plots) as total_plots,
                    AVG(et0_mm) as avg_et0,
                    SUM(avg_kc_factor * area_rai) / SUM(area_rai) as weighted_kc,
                    SUM(gross_demand_m3) as total_gross_m3,
                    SUM(net_demand_m3) as total_net_m3,
                    SUM(effective_rainfall_m3) as total_rainfall_m3,
                    AVG(effective_rainfall_mm) as avg_rainfall_mm,
                    AVG(sensor_adjustment_factor) as avg_adjustment
                FROM ros_gis.weekly_water_demands
                WHERE area_type = 'zone'
                AND week_start_date = $1
                AND calculation_method = $2
            """
            
            async with await self.db.get_connection() as conn:
                row = await conn.fetchrow(query, week_start, method)
            
            if row and row['zone_count'] > 0:
                total_area = float(row['total_area_rai'])
                
                munbon_demand = {
                    'week_start_date': week_start,
                    'week_end_date': week_end,
                    'area_id': 'munbon',
                    'area_type': 'munbon',
                    'calculation_method': method,
                    'area_rai': total_area,
                    'active_plots': int(row['total_plots']),
                    'et0_mm': float(row['avg_et0']),
                    'avg_kc_factor': float(row['weighted_kc']),
                    'gross_demand_mm': float(row['total_gross_m3']) / (total_area * 1.6),
                    'net_demand_mm': float(row['total_net_m3']) / (total_area * 1.6),
                    'gross_demand_m3': float(row['total_gross_m3']),
                    'net_demand_m3': float(row['total_net_m3']),
                    'effective_rainfall_mm': float(row['avg_rainfall_mm']),
                    'effective_rainfall_m3': float(row['total_rainfall_m3']),
                    'sensor_adjustment_factor': float(row['avg_adjustment']),
                    'adjusted_demand_m3': float(row['total_net_m3']) * float(row['avg_adjustment']),
                    'data_source': f"Aggregated from {row['zone_count']} zones"
                }
                
                await self._store_weekly_demand(munbon_demand, 1.0, 'munbon')
    
    async def _store_weekly_demand(
        self,
        demand_data: Dict,
        adjustment_factor: float,
        area_type: str
    ):
        """Store calculated demand in database"""
        if not demand_data:
            return
        
        # Apply adjustment
        adjusted_demand = demand_data['net_demand_m3'] * adjustment_factor
        
        query = """
            INSERT INTO ros_gis.weekly_water_demands (
                week_start_date, week_end_date, area_id, area_type,
                calculation_method, area_rai, active_plots,
                et0_mm, avg_kc_factor,
                gross_demand_mm, net_demand_mm,
                gross_demand_m3, net_demand_m3,
                effective_rainfall_mm, effective_rainfall_m3,
                sensor_adjustment_factor, adjusted_demand_m3,
                data_source, calculation_timestamp
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19
            )
            ON CONFLICT (week_start_date, area_id, area_type, calculation_method)
            DO UPDATE SET
                area_rai = EXCLUDED.area_rai,
                active_plots = EXCLUDED.active_plots,
                et0_mm = EXCLUDED.et0_mm,
                avg_kc_factor = EXCLUDED.avg_kc_factor,
                gross_demand_mm = EXCLUDED.gross_demand_mm,
                net_demand_mm = EXCLUDED.net_demand_mm,
                gross_demand_m3 = EXCLUDED.gross_demand_m3,
                net_demand_m3 = EXCLUDED.net_demand_m3,
                effective_rainfall_mm = EXCLUDED.effective_rainfall_mm,
                effective_rainfall_m3 = EXCLUDED.effective_rainfall_m3,
                sensor_adjustment_factor = EXCLUDED.sensor_adjustment_factor,
                adjusted_demand_m3 = EXCLUDED.adjusted_demand_m3,
                data_source = EXCLUDED.data_source,
                calculation_timestamp = EXCLUDED.calculation_timestamp,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                query,
                demand_data['week_start_date'],
                demand_data['week_end_date'],
                demand_data['area_id'],
                demand_data['area_type'],
                demand_data['calculation_method'],
                demand_data['area_rai'],
                demand_data['active_plots'],
                demand_data['et0_mm'],
                demand_data['avg_kc_factor'],
                demand_data['gross_demand_mm'],
                demand_data['net_demand_mm'],
                demand_data['gross_demand_m3'],
                demand_data['net_demand_m3'],
                demand_data['effective_rainfall_mm'],
                demand_data['effective_rainfall_m3'],
                adjustment_factor,
                adjusted_demand,
                demand_data['data_source'],
                datetime.now()
            )
    
    async def _update_season_progress(self, week_start: date):
        """Update crop season progress tracking"""
        # Get all active crop seasons
        query = """
            SELECT DISTINCT
                s.section_id as area_id,
                'section' as area_type,
                cs.crop_type,
                cs.planting_date,
                cs.expected_harvest_date,
                cs.season_year,
                cs.season_name,
                EXTRACT(WEEK FROM AGE($1, cs.planting_date))::INTEGER + 1 as week_number
            FROM ros.plot_crop_seasons cs
            JOIN gis.agricultural_plots p ON cs.plot_code = p.plot_code
            JOIN ros.sections s ON p.section_id = s.section_id
            WHERE cs.is_active = true
            AND $1 >= cs.planting_date
            AND $1 <= cs.expected_harvest_date
        """
        
        async with await self.db.get_connection() as conn:
            seasons = await conn.fetch(query, week_start)
        
        for season in seasons:
            for method in ['ros', 'rid_ms', 'combined']:
                await self._update_single_season_progress(
                    season,
                    week_start,
                    method
                )
    
    async def _update_single_season_progress(
        self,
        season: Dict,
        week_start: date,
        method: str
    ):
        """Update progress for a single crop season"""
        # Get weekly demand data
        demand_query = """
            SELECT * FROM ros_gis.weekly_water_demands
            WHERE area_id = $1
            AND area_type = $2
            AND week_start_date = $3
            AND calculation_method = $4
        """
        
        async with await self.db.get_connection() as conn:
            demand = await conn.fetchrow(
                demand_query,
                season['area_id'],
                season['area_type'],
                week_start,
                method
            )
        
        if not demand:
            return
        
        # Get growth stage
        growth_stage = self._get_growth_stage_for_week(
            season['crop_type'],
            season['week_number']
        )
        
        # Calculate remaining weeks
        remaining_weeks = int(
            (season['expected_harvest_date'] - week_start).days / 7
        )
        
        # Insert or update progress
        progress_query = """
            INSERT INTO ros_gis.crop_season_weekly_progress (
                area_id, area_type, crop_type, planting_date,
                expected_harvest_date, calculation_method,
                season_year, season_name,
                week_number, week_start_date, week_end_date,
                growth_stage, area_rai, active_plots,
                weekly_gross_demand_m3, weekly_net_demand_m3,
                weekly_effective_rainfall_m3, weekly_adjusted_demand_m3,
                remaining_weeks, weekly_demand_id
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
            )
            ON CONFLICT (area_id, area_type, week_start_date, calculation_method)
            DO UPDATE SET
                week_number = EXCLUDED.week_number,
                growth_stage = EXCLUDED.growth_stage,
                area_rai = EXCLUDED.area_rai,
                active_plots = EXCLUDED.active_plots,
                weekly_gross_demand_m3 = EXCLUDED.weekly_gross_demand_m3,
                weekly_net_demand_m3 = EXCLUDED.weekly_net_demand_m3,
                weekly_effective_rainfall_m3 = EXCLUDED.weekly_effective_rainfall_m3,
                weekly_adjusted_demand_m3 = EXCLUDED.weekly_adjusted_demand_m3,
                remaining_weeks = EXCLUDED.remaining_weeks,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                progress_query,
                season['area_id'],
                season['area_type'],
                season['crop_type'],
                season['planting_date'],
                season['expected_harvest_date'],
                method,
                season['season_year'],
                season['season_name'],
                season['week_number'],
                week_start,
                week_start + timedelta(days=6),
                growth_stage,
                demand['area_rai'],
                demand['active_plots'],
                demand['gross_demand_m3'],
                demand['net_demand_m3'],
                demand['effective_rainfall_m3'],
                demand['adjusted_demand_m3'],
                remaining_weeks,
                demand['id']
            )
    
    def _calculate_combined_demand(self, ros_demand: Dict, ridms_demand: Dict) -> Dict:
        """Calculate weighted average of ROS and RID-MS demands"""
        if not ros_demand or not ridms_demand:
            return ros_demand or ridms_demand
        
        # 70% ROS, 30% RID-MS
        combined = ros_demand.copy()
        combined['calculation_method'] = 'combined'
        
        # Weight the demand values
        for key in ['gross_demand_mm', 'net_demand_mm', 'gross_demand_m3', 'net_demand_m3']:
            combined[key] = ros_demand[key] * 0.7 + ridms_demand[key] * 0.3
        
        # Average the Kc factor
        combined['avg_kc_factor'] = ros_demand['avg_kc_factor'] * 0.7 + ridms_demand['avg_kc_factor'] * 0.3
        
        combined['data_source'] = "Combined (70% ROS, 30% RID-MS)"
        
        return combined
    
    async def _get_zone_adjustment_factor(
        self,
        zone_id: int,
        section_adjustments: Dict[str, float]
    ) -> float:
        """Calculate zone adjustment as average of section adjustments"""
        zone_sections = [
            section_id for section_id in section_adjustments.keys()
            if section_id.startswith(f"{zone_id}-")
        ]
        
        if not zone_sections:
            return 1.0
        
        total_adjustment = sum(
            section_adjustments[section_id]
            for section_id in zone_sections
        )
        
        return total_adjustment / len(zone_sections)
    
    async def _get_active_sections(self) -> List[Dict]:
        """Get all sections with active crops"""
        query = """
            SELECT DISTINCT
                s.section_id,
                s.zone_id,
                s.aos_station_id,
                COUNT(DISTINCT p.plot_code) as active_plots
            FROM ros.sections s
            JOIN gis.agricultural_plots p ON s.section_id = p.section_id
            JOIN ros.plot_crop_seasons cs ON p.plot_code = cs.plot_code
            WHERE cs.is_active = true
            GROUP BY s.section_id, s.zone_id, s.aos_station_id
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query)
        
        return [dict(row) for row in rows]
    
    async def _get_active_zones(self) -> List[Dict]:
        """Get all zones with active crops"""
        query = """
            SELECT DISTINCT z.zone_id
            FROM ros.zones z
            WHERE EXISTS (
                SELECT 1
                FROM ros.sections s
                JOIN gis.agricultural_plots p ON s.section_id = p.section_id
                JOIN ros.plot_crop_seasons cs ON p.plot_code = cs.plot_code
                WHERE s.zone_id = z.zone_id
                AND cs.is_active = true
            )
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query)
        
        return [dict(row) for row in rows]
    
    async def _get_section_active_plots(self, section_id: str) -> List[Dict]:
        """Get active plots in a section with crop information"""
        query = """
            SELECT 
                p.plot_code,
                p.area_rai,
                cs.crop_type,
                cs.planting_date,
                EXTRACT(WEEK FROM AGE(CURRENT_DATE, cs.planting_date))::INTEGER + 1 as crop_week_number
            FROM gis.agricultural_plots p
            JOIN ros.plot_crop_seasons cs ON p.plot_code = cs.plot_code
            WHERE p.section_id = $1
            AND cs.is_active = true
        """
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, section_id)
        
        return [dict(row) for row in rows]
    
    async def _get_weekly_et0(self, aos_station: str, week: int, year: int) -> Dict:
        """Get weekly ET0 from ROS data"""
        query = """
            SELECT et0_mm
            FROM ros.weekly_et0_data
            WHERE aos_station_id = $1
            AND week_number = $2
            AND year = $3
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, aos_station, week, year)
        
        if row:
            return {'et0_mm': float(row['et0_mm'])}
        
        # Fallback to historical average
        query = """
            SELECT AVG(et0_mm) as avg_et0
            FROM ros.weekly_et0_data
            WHERE aos_station_id = $1
            AND week_number = $2
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, aos_station, week)
        
        return {'et0_mm': float(row['avg_et0']) if row else 35.0}
    
    async def _get_effective_rainfall(self, zone_id: int, week: int, year: int) -> Dict:
        """Get effective rainfall from ROS data"""
        query = """
            SELECT effective_rainfall_mm
            FROM ros.weekly_effective_rainfall
            WHERE zone_id = $1
            AND week_number = $2
            AND year = $3
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, zone_id, week, year)
        
        if row:
            return {'effective_mm': float(row['effective_rainfall_mm'])}
        
        # Fallback to historical average
        query = """
            SELECT AVG(effective_rainfall_mm) as avg_rainfall
            FROM ros.weekly_effective_rainfall
            WHERE zone_id = $1
            AND week_number = $2
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, zone_id, week)
        
        return {'effective_mm': float(row['avg_rainfall']) if row else 0.0}
    
    async def _get_kc_factor(self, crop_type: str, week_number: int, method: str) -> float:
        """Get Kc factor from ROS or RID-MS tables"""
        table = "ros.kc_values" if method == "ros" else "ros.kc_values_ridms"
        
        query = f"""
            SELECT kc_value
            FROM {table}
            WHERE crop_type = $1
            AND week_number = $2
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, crop_type, week_number)
        
        if row:
            return float(row['kc_value'])
        
        # Default based on growth stage
        if week_number <= 2:
            return 0.4
        elif week_number <= 6:
            return 0.7
        elif week_number <= 12:
            return 1.1
        else:
            return 0.8
    
    def _calculate_ros_demand(
        self,
        et0_mm: float,
        kc: float,
        effective_rainfall_mm: float,
        area_rai: float
    ) -> Dict:
        """Calculate using ROS method"""
        gross_demand_mm = et0_mm * kc
        net_demand_mm = max(0, gross_demand_mm - effective_rainfall_mm)
        
        return {
            'gross_demand_mm': gross_demand_mm,
            'net_demand_mm': net_demand_mm,
            'gross_demand_m3': gross_demand_mm * area_rai * 1.6,
            'net_demand_m3': net_demand_mm * area_rai * 1.6
        }
    
    async def _calculate_ridms_demand(
        self,
        et0_mm: float,
        kc: float,
        effective_rainfall_mm: float,
        area_rai: float,
        crop_type: str
    ) -> Dict:
        """Calculate using RID-MS/AquaCrop method"""
        # RID-MS applies additional factors
        soil_factor = 1.1  # Sandy soil adjustment
        efficiency_factor = 0.85  # System efficiency
        
        gross_demand_mm = et0_mm * kc * soil_factor / efficiency_factor
        net_demand_mm = max(0, gross_demand_mm - effective_rainfall_mm)
        
        return {
            'gross_demand_mm': gross_demand_mm,
            'net_demand_mm': net_demand_mm,
            'gross_demand_m3': gross_demand_mm * area_rai * 1.6,
            'net_demand_m3': net_demand_mm * area_rai * 1.6
        }
    
    def _get_growth_stage_for_week(self, crop_type: str, week_number: int) -> str:
        """Get growth stage name"""
        stages = {
            'rice': [
                (2, 'Initial'),
                (6, 'Development'),
                (12, 'Mid-season'),
                (16, 'Late season')
            ],
            'sugarcane': [
                (8, 'Germination'),
                (20, 'Tillering'),
                (40, 'Grand growth'),
                (52, 'Maturation')
            ]
        }
        
        crop_stages = stages.get(crop_type.lower(), stages['rice'])
        
        for week_limit, stage_name in crop_stages:
            if week_number <= week_limit:
                return stage_name
        
        return crop_stages[-1][1]


# Singleton instance
weekly_demand_calculator = WeeklyDemandCalculator()
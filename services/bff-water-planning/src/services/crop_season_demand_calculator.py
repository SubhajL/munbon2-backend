"""
Crop Season Demand Calculator Service
Calculates total water demand for entire crop season using historical data
"""

from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
import asyncio

from core import get_logger
from db import DatabaseManager
from clients import ROSClient, RIDMSClient
from services.calculation_engine import CalculationEngine
from utils.date_utils import get_week_number

logger = get_logger(__name__)


class CropSeasonDemandCalculator:
    """Calculates water demand for entire crop season"""
    
    # Crop duration in weeks
    CROP_DURATIONS = {
        'rice': 16,  # 16 weeks (~112 days)
        'sugarcane': 52,  # 52 weeks (1 year)
        'cassava': 40,  # 40 weeks (~280 days)
        'maize': 12,  # 12 weeks (~84 days)
        'vegetables': 8,  # 8 weeks (~56 days)
        'soybean': 14,  # 14 weeks (~98 days)
        'mungbean': 10,  # 10 weeks (~70 days)
    }
    
    def __init__(self):
        self.logger = logger.bind(service="crop_season_demand_calculator")
        self.db = DatabaseManager()
        self.ros_client = ROSClient()
        self.ridms_client = RIDMSClient()
        self.calculator = CalculationEngine()
    
    async def calculate_full_season_demand(
        self,
        area_id: str,
        area_type: str,
        crop_type: str,
        planting_date: date,
        calculation_method: str = "ros",
        include_rainfall_forecast: bool = True
    ) -> Dict:
        """
        Calculate total water demand for entire crop season
        
        Args:
            area_id: Plot, section, zone ID or 'munbon'
            area_type: 'plot', 'section', 'zone', or 'munbon'
            crop_type: Type of crop
            planting_date: Planting date
            calculation_method: 'ros', 'rid_ms', or 'combined'
            include_rainfall_forecast: Include rainfall forecast in calculations
        
        Returns:
            Complete season demand with weekly breakdown
        """
        try:
            # Get crop duration
            crop_weeks = self.CROP_DURATIONS.get(crop_type.lower(), 16)
            harvest_date = planting_date + timedelta(weeks=crop_weeks)
            
            # Get area information
            area_info = await self._get_area_info(area_id, area_type)
            area_rai = area_info['area_rai']
            
            # Calculate weekly demands
            weekly_demands = []
            total_gross_demand_m3 = 0
            total_net_demand_m3 = 0
            total_effective_rainfall_m3 = 0
            peak_weekly_demand_m3 = 0
            peak_demand_week = 0
            
            current_date = planting_date
            for week_num in range(crop_weeks):
                week_start = current_date
                week_end = current_date + timedelta(days=6)
                
                # Get calendar week info
                calendar_week, calendar_year = get_week_number(week_start)
                
                # Get ET0 data
                et0_data = await self._get_weekly_et0(
                    area_info['aos_station'],
                    calendar_week,
                    calendar_year
                )
                
                # Get Kc factor
                kc_factor = await self._get_kc_factor(
                    crop_type,
                    week_num + 1,
                    calculation_method
                )
                
                # Get effective rainfall
                rainfall_data = await self._get_effective_rainfall(
                    area_info['zone_id'],
                    calendar_week,
                    calendar_year,
                    include_forecast=include_rainfall_forecast
                )
                
                # Calculate demands
                if calculation_method == "ros":
                    demand_result = self._calculate_ros_demand(
                        et0_data['et0_mm'],
                        kc_factor,
                        rainfall_data['effective_mm'],
                        area_rai
                    )
                elif calculation_method == "rid_ms":
                    demand_result = await self._calculate_ridms_demand(
                        area_id,
                        area_type,
                        crop_type,
                        week_num + 1,
                        et0_data['et0_mm'],
                        rainfall_data['effective_mm'],
                        area_rai
                    )
                else:  # combined
                    ros_demand = self._calculate_ros_demand(
                        et0_data['et0_mm'],
                        kc_factor,
                        rainfall_data['effective_mm'],
                        area_rai
                    )
                    ridms_demand = await self._calculate_ridms_demand(
                        area_id,
                        area_type,
                        crop_type,
                        week_num + 1,
                        et0_data['et0_mm'],
                        rainfall_data['effective_mm'],
                        area_rai
                    )
                    # Weight average (70% ROS, 30% RID-MS)
                    demand_result = {
                        'gross_demand_mm': ros_demand['gross_demand_mm'] * 0.7 + ridms_demand['gross_demand_mm'] * 0.3,
                        'net_demand_mm': ros_demand['net_demand_mm'] * 0.7 + ridms_demand['net_demand_mm'] * 0.3,
                        'gross_demand_m3': ros_demand['gross_demand_m3'] * 0.7 + ridms_demand['gross_demand_m3'] * 0.3,
                        'net_demand_m3': ros_demand['net_demand_m3'] * 0.7 + ridms_demand['net_demand_m3'] * 0.3
                    }
                
                # Get growth stage
                growth_stage = self._get_growth_stage(crop_type, week_num + 1)
                
                # Add weekly data
                weekly_data = {
                    'week_number': week_num + 1,
                    'calendar_week': calendar_week,
                    'calendar_year': calendar_year,
                    'start_date': week_start,
                    'end_date': week_end,
                    'et0_mm': et0_data['et0_mm'],
                    'kc_factor': kc_factor,
                    'effective_rainfall_mm': rainfall_data['effective_mm'],
                    'gross_demand_mm': demand_result['gross_demand_mm'],
                    'net_demand_mm': demand_result['net_demand_mm'],
                    'gross_demand_m3': demand_result['gross_demand_m3'],
                    'net_demand_m3': demand_result['net_demand_m3'],
                    'growth_stage': growth_stage,
                    'water_level_adjustment': None  # Can be added later
                }
                weekly_demands.append(weekly_data)
                
                # Update totals
                total_gross_demand_m3 += demand_result['gross_demand_m3']
                total_net_demand_m3 += demand_result['net_demand_m3']
                total_effective_rainfall_m3 += rainfall_data['effective_mm'] * area_rai * 1.6  # Convert to m³
                
                if demand_result['net_demand_m3'] > peak_weekly_demand_m3:
                    peak_weekly_demand_m3 = demand_result['net_demand_m3']
                    peak_demand_week = week_num + 1
                
                current_date = week_end + timedelta(days=1)
            
            # Calculate averages
            average_weekly_demand_m3 = total_net_demand_m3 / crop_weeks if crop_weeks > 0 else 0
            
            # Prepare data sources
            data_sources = {
                'et0_source': 'Historical AOS weather data',
                'kc_source': f'{calculation_method.upper()} coefficient tables',
                'rainfall_source': 'Historical rainfall with TMD forecast' if include_rainfall_forecast else 'Historical rainfall data',
                'calculation_method': calculation_method
            }
            
            return {
                'area_id': area_id,
                'area_type': area_type,
                'area_rai': area_rai,
                'crop_type': crop_type,
                'planting_date': planting_date,
                'expected_harvest_date': harvest_date,
                'total_crop_weeks': crop_weeks,
                'calculation_method': calculation_method,
                'total_gross_demand_m3': total_gross_demand_m3,
                'total_net_demand_m3': total_net_demand_m3,
                'total_effective_rainfall_m3': total_effective_rainfall_m3,
                'average_weekly_demand_m3': average_weekly_demand_m3,
                'peak_weekly_demand_m3': peak_weekly_demand_m3,
                'peak_demand_week': peak_demand_week,
                'weekly_breakdown': weekly_demands,
                'data_sources': data_sources
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to calculate season demand",
                area_id=area_id,
                crop_type=crop_type,
                error=str(e)
            )
            raise
    
    async def calculate_batch_season_demands(
        self,
        area_type: str,
        area_ids: Optional[List[str]] = None,
        crop_types: Optional[List[str]] = None,
        planting_after: Optional[date] = None,
        calculation_method: str = "ros"
    ) -> List[Dict]:
        """Calculate season demands for multiple areas in batch"""
        # Get active crops based on filters
        query = """
            SELECT DISTINCT p.plot_code, p.section_id, p.zone_id,
                   c.crop_type, c.planting_date, p.area_rai
            FROM gis.agricultural_plots p
            JOIN ros.plot_crop_seasons c ON p.plot_code = c.plot_code
            WHERE c.is_active = true
        """
        
        params = []
        conditions = []
        
        if area_type == "section" and area_ids:
            conditions.append("p.section_id = ANY($1)")
            params.append(area_ids)
        elif area_type == "zone" and area_ids:
            conditions.append("p.zone_id = ANY($1)")
            params.append(area_ids)
        
        if crop_types:
            conditions.append(f"c.crop_type = ANY(${len(params) + 1})")
            params.append(crop_types)
        
        if planting_after:
            conditions.append(f"c.planting_date >= ${len(params) + 1}")
            params.append(planting_after)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, *params)
        
        # Calculate demands for each area
        results = []
        for row in rows:
            try:
                if area_type == "plot":
                    target_id = row['plot_code']
                elif area_type == "section":
                    target_id = row['section_id']
                else:  # zone
                    target_id = str(row['zone_id'])
                
                demand = await self.calculate_full_season_demand(
                    area_id=target_id,
                    area_type=area_type,
                    crop_type=row['crop_type'],
                    planting_date=row['planting_date'],
                    calculation_method=calculation_method,
                    include_rainfall_forecast=False  # Use historical only for batch
                )
                
                results.append({
                    'area_id': target_id,
                    'crop_type': row['crop_type'],
                    'planting_date': row['planting_date'],
                    'area_rai': float(row['area_rai']),
                    'total_net_demand_m3': demand['total_net_demand_m3'],
                    'average_weekly_demand_m3': demand['average_weekly_demand_m3'],
                    'peak_weekly_demand_m3': demand['peak_weekly_demand_m3']
                })
                
            except Exception as e:
                self.logger.error(
                    "Failed to calculate batch demand",
                    area_id=target_id,
                    error=str(e)
                )
        
        return results
    
    async def get_active_season_summary(
        self,
        zone: Optional[int] = None,
        crop_type: Optional[str] = None
    ) -> Dict:
        """Get summary of all active crop seasons"""
        query = """
            SELECT 
                p.zone_id,
                c.crop_type,
                COUNT(DISTINCT p.plot_code) as plot_count,
                SUM(p.area_rai) as total_area_rai,
                MIN(c.planting_date) as earliest_planting,
                MAX(c.planting_date) as latest_planting
            FROM gis.agricultural_plots p
            JOIN ros.plot_crop_seasons c ON p.plot_code = c.plot_code
            WHERE c.is_active = true
        """
        
        params = []
        if zone:
            query += " AND p.zone_id = $1"
            params.append(zone)
        
        if crop_type:
            query += f" AND c.crop_type = ${len(params) + 1}"
            params.append(crop_type)
        
        query += " GROUP BY p.zone_id, c.crop_type"
        
        async with await self.db.get_connection() as conn:
            rows = await conn.fetch(query, *params)
        
        # Calculate estimated demands
        summary = {
            'total_plots': 0,
            'total_area_rai': 0,
            'by_zone': {},
            'by_crop': {},
            'estimated_total_demand_m3': 0
        }
        
        for row in rows:
            zone_id = str(row['zone_id'])
            crop = row['crop_type']
            
            # Update totals
            summary['total_plots'] += row['plot_count']
            summary['total_area_rai'] += float(row['total_area_rai'])
            
            # By zone
            if zone_id not in summary['by_zone']:
                summary['by_zone'][zone_id] = {
                    'plot_count': 0,
                    'area_rai': 0,
                    'crops': []
                }
            summary['by_zone'][zone_id]['plot_count'] += row['plot_count']
            summary['by_zone'][zone_id]['area_rai'] += float(row['total_area_rai'])
            if crop not in summary['by_zone'][zone_id]['crops']:
                summary['by_zone'][zone_id]['crops'].append(crop)
            
            # By crop
            if crop not in summary['by_crop']:
                summary['by_crop'][crop] = {
                    'plot_count': 0,
                    'area_rai': 0,
                    'zones': []
                }
            summary['by_crop'][crop]['plot_count'] += row['plot_count']
            summary['by_crop'][crop]['area_rai'] += float(row['total_area_rai'])
            if zone_id not in summary['by_crop'][crop]['zones']:
                summary['by_crop'][crop]['zones'].append(zone_id)
            
            # Estimate demand (rough calculation: 5000 m³/rai for rice)
            if crop.lower() == 'rice':
                summary['estimated_total_demand_m3'] += float(row['total_area_rai']) * 5000
            elif crop.lower() == 'sugarcane':
                summary['estimated_total_demand_m3'] += float(row['total_area_rai']) * 8000
            else:
                summary['estimated_total_demand_m3'] += float(row['total_area_rai']) * 4000
        
        return summary
    
    async def _get_area_info(self, area_id: str, area_type: str) -> Dict:
        """Get area information including AOS station"""
        if area_type == "plot":
            query = """
                SELECT p.area_rai, p.section_id, p.zone_id,
                       s.aos_station_id as aos_station
                FROM gis.agricultural_plots p
                JOIN ros.sections s ON p.section_id = s.section_id
                WHERE p.plot_code = $1
            """
            params = [area_id]
        elif area_type == "section":
            query = """
                SELECT SUM(p.area_rai) as area_rai,
                       s.zone_id, s.aos_station_id as aos_station
                FROM ros.sections s
                LEFT JOIN gis.agricultural_plots p ON s.section_id = p.section_id
                WHERE s.section_id = $1
                GROUP BY s.zone_id, s.aos_station_id
            """
            params = [area_id]
        elif area_type == "zone":
            query = """
                SELECT SUM(p.area_rai) as area_rai,
                       z.zone_id, z.aos_station_id as aos_station
                FROM ros.zones z
                LEFT JOIN ros.sections s ON z.zone_id = s.zone_id
                LEFT JOIN gis.agricultural_plots p ON s.section_id = p.section_id
                WHERE z.zone_id = $1
                GROUP BY z.zone_id, z.aos_station_id
            """
            params = [int(area_id)]
        else:  # munbon
            query = """
                SELECT SUM(p.area_rai) as area_rai,
                       'Khon Kaen' as aos_station
                FROM gis.agricultural_plots p
            """
            params = []
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, *params)
        
        if not row:
            raise ValueError(f"Area not found: {area_id}")
        
        return {
            'area_rai': float(row['area_rai'] or 0),
            'aos_station': row.get('aos_station', 'Khon Kaen'),
            'zone_id': row.get('zone_id', 1)
        }
    
    async def _get_weekly_et0(
        self,
        aos_station: str,
        week: int,
        year: int
    ) -> Dict:
        """Get weekly ET0 from historical data"""
        query = """
            SELECT et0_mm
            FROM ros.weekly_et0_historical
            WHERE aos_station_id = $1
            AND week_number = $2
            AND year = $3
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, aos_station, week, year)
        
        if row:
            return {'et0_mm': float(row['et0_mm'])}
        
        # Fall back to average for that week
        query = """
            SELECT AVG(et0_mm) as avg_et0
            FROM ros.weekly_et0_historical
            WHERE aos_station_id = $1
            AND week_number = $2
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, aos_station, week)
        
        return {'et0_mm': float(row['avg_et0']) if row and row['avg_et0'] else 35.0}
    
    async def _get_kc_factor(
        self,
        crop_type: str,
        week_number: int,
        method: str
    ) -> float:
        """Get Kc factor for crop and week"""
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
        
        # Default Kc values by growth stage
        if week_number <= 2:
            return 0.4  # Initial stage
        elif week_number <= 6:
            return 0.7  # Development stage
        elif week_number <= 12:
            return 1.1  # Mid-season stage
        else:
            return 0.8  # Late season stage
    
    async def _get_effective_rainfall(
        self,
        zone_id: int,
        week: int,
        year: int,
        include_forecast: bool = True
    ) -> Dict:
        """Get effective rainfall data"""
        # Try historical data first
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
        
        # Fall back to average
        query = """
            SELECT AVG(effective_rainfall_mm) as avg_rainfall
            FROM ros.weekly_effective_rainfall
            WHERE zone_id = $1
            AND week_number = $2
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query, zone_id, week)
        
        avg_rainfall = float(row['avg_rainfall']) if row and row['avg_rainfall'] else 0.0
        
        # Apply forecast adjustment if enabled and for future dates
        if include_forecast and year >= datetime.now().year:
            # Simple forecast adjustment (could be enhanced)
            avg_rainfall *= 0.8  # Assume 80% of historical average
        
        return {'effective_mm': avg_rainfall}
    
    def _calculate_ros_demand(
        self,
        et0_mm: float,
        kc: float,
        effective_rainfall_mm: float,
        area_rai: float
    ) -> Dict:
        """Calculate water demand using ROS method"""
        # Gross demand = ET0 × Kc
        gross_demand_mm = et0_mm * kc
        
        # Net demand = Gross demand - Effective rainfall
        net_demand_mm = max(0, gross_demand_mm - effective_rainfall_mm)
        
        # Convert to m³ (1 rai = 1,600 m², 1 mm = 0.001 m)
        gross_demand_m3 = gross_demand_mm * area_rai * 1.6
        net_demand_m3 = net_demand_mm * area_rai * 1.6
        
        return {
            'gross_demand_mm': gross_demand_mm,
            'net_demand_mm': net_demand_mm,
            'gross_demand_m3': gross_demand_m3,
            'net_demand_m3': net_demand_m3
        }
    
    async def _calculate_ridms_demand(
        self,
        area_id: str,
        area_type: str,
        crop_type: str,
        week_number: int,
        et0_mm: float,
        effective_rainfall_mm: float,
        area_rai: float
    ) -> Dict:
        """Calculate water demand using RID-MS/AquaCrop method"""
        # This would integrate with RID-MS service
        # For now, use modified calculation
        
        # Get crop coefficient from RID-MS
        kc = await self._get_kc_factor(crop_type, week_number, "rid_ms")
        
        # RID-MS uses additional factors
        soil_factor = 1.1  # Sandy soil needs more water
        efficiency_factor = 0.85  # Irrigation efficiency
        
        # Gross demand with adjustments
        gross_demand_mm = et0_mm * kc * soil_factor / efficiency_factor
        
        # Net demand
        net_demand_mm = max(0, gross_demand_mm - effective_rainfall_mm)
        
        # Convert to m³
        gross_demand_m3 = gross_demand_mm * area_rai * 1.6
        net_demand_m3 = net_demand_mm * area_rai * 1.6
        
        return {
            'gross_demand_mm': gross_demand_mm,
            'net_demand_mm': net_demand_mm,
            'gross_demand_m3': gross_demand_m3,
            'net_demand_m3': net_demand_m3
        }
    
    def _get_growth_stage(self, crop_type: str, week_number: int) -> str:
        """Get growth stage name for crop and week"""
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
            ],
            'cassava': [
                (4, 'Establishment'),
                (12, 'Vegetative'),
                (32, 'Storage root bulking'),
                (40, 'Maturation')
            ]
        }
        
        crop_stages = stages.get(crop_type.lower(), stages['rice'])
        
        for week_limit, stage_name in crop_stages:
            if week_number <= week_limit:
                return stage_name
        
        return crop_stages[-1][1]  # Return last stage
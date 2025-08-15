"""
Daily Demand Calculator Service
Calculates daily water demands from ROS and AquaCrop, accumulating until control interval
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, date
from enum import Enum
import asyncio
from collections import defaultdict

from core import get_logger
from config import settings
from db import DatabaseManager
from services.cache_manager import get_cache_manager
from clients import ROSClient, GISClient

logger = get_logger(__name__)


class DemandSource(Enum):
    """Source of water demand calculation"""
    ROS = "ros"
    AQUACROP = "aquacrop"
    COMBINED = "combined"


class ControlInterval(Enum):
    """Control interval for field operations"""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class DailyDemandCalculator:
    """Calculates and accumulates daily water demands"""
    
    def __init__(self):
        self.logger = logger.bind(service="daily_demand_calculator")
        self.db = DatabaseManager()
        self.ros_client = ROSClient()
        self.gis_client = GISClient()
        self.cache = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize service"""
        if not self._initialized:
            self.cache = await get_cache_manager()
            self._initialized = True
    
    async def calculate_daily_demands(
        self,
        date: date,
        zones: Optional[List[int]] = None
    ) -> Dict[str, Dict]:
        """
        Calculate daily water demands for all plots/sections
        
        Args:
            date: Date to calculate demands for
            zones: Specific zones to calculate (None = all zones)
            
        Returns:
            Dict of demands by plot_id/section_id
        """
        await self.initialize()
        
        self.logger.info(
            "Calculating daily demands",
            date=date.isoformat(),
            zones=zones
        )
        
        # Get all active plots/sections
        plots = await self._get_active_plots(zones)
        
        daily_demands = {}
        
        for plot in plots:
            plot_id = plot['plot_id']
            
            # Calculate ROS demand
            ros_demand = await self._calculate_ros_demand(plot, date)
            
            # Get AquaCrop demand from latest geopackage processing
            aquacrop_demand = await self._get_aquacrop_demand(plot_id, date)
            
            # Combine demands (using configured strategy)
            combined_demand = self._combine_demands(ros_demand, aquacrop_demand)
            
            daily_demands[plot_id] = {
                "plot_id": plot_id,
                "section_id": plot['section_id'],
                "date": date.isoformat(),
                "ros_demand_m3": ros_demand.get('net_demand_m3', 0),
                "aquacrop_demand_m3": aquacrop_demand.get('net_demand_m3', 0),
                "combined_demand_m3": combined_demand['net_demand_m3'],
                "crop_type": plot['crop_type'],
                "growth_stage": combined_demand.get('growth_stage'),
                "stress_level": combined_demand.get('stress_level'),
                "area_rai": plot['area_rai'],
                "source": combined_demand['source']
            }
        
        # Store daily demands
        await self._store_daily_demands(daily_demands)
        
        return daily_demands
    
    async def _calculate_ros_demand(
        self,
        plot: Dict,
        date: date
    ) -> Dict:
        """Calculate water demand using ROS service"""
        try:
            # Get crop calendar
            crop_info = await self.ros_client.get_crop_calendar(
                plot['plot_id'],
                plot['crop_type']
            )
            
            if not crop_info:
                return {"net_demand_m3": 0, "source": "ros"}
            
            # Calculate crop week
            planting_date = datetime.fromisoformat(crop_info['plantingDate']).date()
            days_since_planting = (date - planting_date).days
            crop_week = max(1, (days_since_planting // 7) + 1)
            
            # Get water demand
            demand = await self.ros_client.calculate_water_demand({
                "areaId": plot['plot_id'],
                "cropType": plot['crop_type'],
                "areaType": "plot",
                "areaRai": plot['area_rai'],
                "cropWeek": crop_week,
                "calendarWeek": date.isocalendar()[1],
                "calendarYear": date.year,
                "growthStage": self._get_growth_stage(plot['crop_type'], crop_week)
            })
            
            if demand:
                # Convert weekly to daily demand
                demand['net_demand_m3'] = demand.get('netWaterDemandM3', 0) / 7
                demand['source'] = "ros"
            
            return demand or {"net_demand_m3": 0, "source": "ros"}
            
        except Exception as e:
            self.logger.error(
                "Failed to calculate ROS demand",
                plot_id=plot['plot_id'],
                error=str(e)
            )
            return {"net_demand_m3": 0, "source": "ros", "error": str(e)}
    
    async def _get_aquacrop_demand(
        self,
        plot_id: str,
        date: date
    ) -> Dict:
        """Get AquaCrop demand from processed geopackage data"""
        try:
            # Query database for latest AquaCrop results
            async with self.db.get_connection() as conn:
                query = """
                    SELECT 
                        net_irrigation_mm,
                        gross_irrigation_mm,
                        soil_moisture_percent,
                        crop_stage,
                        water_stress_level,
                        processing_date
                    FROM ros_gis.aquacrop_results
                    WHERE plot_id = $1
                        AND calculation_date = $2
                    ORDER BY processing_date DESC
                    LIMIT 1
                """
                
                result = await conn.fetchone(query, plot_id, date)
                
                if result:
                    # Get plot area for conversion
                    plot_query = "SELECT area_rai FROM ros_gis.sections WHERE section_id = $1"
                    plot_data = await conn.fetchone(plot_query, plot_id)
                    area_rai = plot_data['area_rai'] if plot_data else 100
                    
                    # Convert mm to m³ (1mm on 1 rai = 1.6 m³)
                    net_demand_m3 = result['net_irrigation_mm'] * area_rai * 1.6
                    
                    return {
                        "net_demand_m3": net_demand_m3,
                        "gross_demand_m3": result['gross_irrigation_mm'] * area_rai * 1.6,
                        "soil_moisture": result['soil_moisture_percent'],
                        "growth_stage": result['crop_stage'],
                        "stress_level": result['water_stress_level'],
                        "source": "aquacrop"
                    }
                
                return {"net_demand_m3": 0, "source": "aquacrop", "status": "no_data"}
                
        except Exception as e:
            self.logger.error(
                "Failed to get AquaCrop demand",
                plot_id=plot_id,
                error=str(e)
            )
            return {"net_demand_m3": 0, "source": "aquacrop", "error": str(e)}
    
    def _combine_demands(
        self,
        ros_demand: Dict,
        aquacrop_demand: Dict
    ) -> Dict:
        """Combine ROS and AquaCrop demands using configured strategy"""
        # Strategy options:
        # 1. Use AquaCrop if available (more accurate with actual field data)
        # 2. Average both
        # 3. Use maximum (conservative)
        # 4. Weighted average based on confidence
        
        strategy = settings.demand_combination_strategy  # Default: "aquacrop_priority"
        
        if strategy == "aquacrop_priority":
            # Use AquaCrop if available and valid
            if aquacrop_demand.get('net_demand_m3', 0) > 0 and 'error' not in aquacrop_demand:
                return {
                    **aquacrop_demand,
                    "source": "aquacrop",
                    "ros_backup": ros_demand.get('net_demand_m3', 0)
                }
            else:
                return {
                    **ros_demand,
                    "source": "ros",
                    "aquacrop_status": aquacrop_demand.get('status', 'error')
                }
        
        elif strategy == "average":
            ros_val = ros_demand.get('net_demand_m3', 0)
            aqua_val = aquacrop_demand.get('net_demand_m3', 0)
            
            if ros_val > 0 and aqua_val > 0:
                return {
                    "net_demand_m3": (ros_val + aqua_val) / 2,
                    "source": "combined_average",
                    "ros_demand_m3": ros_val,
                    "aquacrop_demand_m3": aqua_val,
                    "growth_stage": aquacrop_demand.get('growth_stage') or ros_demand.get('growth_stage'),
                    "stress_level": aquacrop_demand.get('stress_level') or ros_demand.get('stress_level')
                }
            elif ros_val > 0:
                return {**ros_demand, "source": "ros_only"}
            else:
                return {**aquacrop_demand, "source": "aquacrop_only"}
        
        elif strategy == "maximum":
            ros_val = ros_demand.get('net_demand_m3', 0)
            aqua_val = aquacrop_demand.get('net_demand_m3', 0)
            
            if ros_val >= aqua_val:
                return {**ros_demand, "source": "ros_maximum"}
            else:
                return {**aquacrop_demand, "source": "aquacrop_maximum"}
        
        else:
            # Default to ROS
            return {**ros_demand, "source": "ros_default"}
    
    async def accumulate_to_control_interval(
        self,
        start_date: date,
        interval: ControlInterval,
        zones: Optional[List[int]] = None
    ) -> Dict[str, Dict]:
        """
        Accumulate daily demands to control interval
        
        Args:
            start_date: Start date of the interval
            interval: Control interval (weekly/biweekly/monthly)
            zones: Specific zones to process
            
        Returns:
            Accumulated demands by section with delivery scheduling info
        """
        # Determine end date based on interval
        if interval == ControlInterval.WEEKLY:
            end_date = start_date + timedelta(days=7)
        elif interval == ControlInterval.BIWEEKLY:
            end_date = start_date + timedelta(days=14)
        elif interval == ControlInterval.MONTHLY:
            # Get last day of month
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        else:
            end_date = start_date + timedelta(days=7)
        
        self.logger.info(
            "Accumulating demands for control interval",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            interval=interval.value
        )
        
        # Get all daily demands for the period
        daily_demands = await self._get_stored_daily_demands(
            start_date,
            end_date,
            zones
        )
        
        # Aggregate by section and irrigation infrastructure
        section_demands = defaultdict(lambda: {
            "total_demand_m3": 0,
            "plots": [],
            "days_with_demand": 0,
            "peak_daily_demand_m3": 0,
            "avg_daily_demand_m3": 0,
            "delivery_gate": None,
            "irrigation_channel": None
        })
        
        # Group by section
        for demand in daily_demands:
            section_id = demand['section_id']
            section = section_demands[section_id]
            
            section['total_demand_m3'] += demand['combined_demand_m3']
            section['plots'].append(demand['plot_id'])
            section['days_with_demand'] += 1 if demand['combined_demand_m3'] > 0 else 0
            section['peak_daily_demand_m3'] = max(
                section['peak_daily_demand_m3'],
                demand['combined_demand_m3']
            )
            
            # Get delivery infrastructure
            if not section['delivery_gate']:
                gate_info = await self._get_delivery_infrastructure(section_id)
                section['delivery_gate'] = gate_info['delivery_gate']
                section['irrigation_channel'] = gate_info['irrigation_channel']
        
        # Calculate averages and prepare for scheduling
        for section_id, section in section_demands.items():
            days = (end_date - start_date).days
            section['avg_daily_demand_m3'] = section['total_demand_m3'] / days
            section['section_id'] = section_id
            section['control_interval'] = interval.value
            section['start_date'] = start_date.isoformat()
            section['end_date'] = end_date.isoformat()
            
            # Remove duplicates from plots list
            section['plots'] = list(set(section['plots']))
            section['plot_count'] = len(section['plots'])
        
        # Aggregate by irrigation infrastructure
        channel_demands = await self._aggregate_by_channel(dict(section_demands))
        
        return {
            "section_demands": dict(section_demands),
            "channel_demands": channel_demands,
            "interval": {
                "type": interval.value,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days
            }
        }
    
    async def _aggregate_by_channel(
        self,
        section_demands: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Aggregate demands by common irrigation channels"""
        channel_demands = defaultdict(lambda: {
            "total_demand_m3": 0,
            "sections": [],
            "total_plots": 0,
            "peak_flow_required_m3s": 0,
            "delivery_gates": set()
        })
        
        for section_id, demand in section_demands.items():
            channel = demand.get('irrigation_channel', 'unknown')
            gate = demand.get('delivery_gate', 'unknown')
            
            ch_demand = channel_demands[channel]
            ch_demand['total_demand_m3'] += demand['total_demand_m3']
            ch_demand['sections'].append(section_id)
            ch_demand['total_plots'] += demand['plot_count']
            ch_demand['delivery_gates'].add(gate)
            
            # Calculate peak flow (assuming 8-hour delivery window)
            peak_flow = demand['peak_daily_demand_m3'] / (8 * 3600)
            ch_demand['peak_flow_required_m3s'] += peak_flow
        
        # Convert sets to lists for JSON serialization
        for channel, data in channel_demands.items():
            data['delivery_gates'] = list(data['delivery_gates'])
            data['channel_id'] = channel
            data['section_count'] = len(data['sections'])
        
        return dict(channel_demands)
    
    async def _get_active_plots(
        self,
        zones: Optional[List[int]] = None
    ) -> List[Dict]:
        """Get all active plots/sections"""
        try:
            async with self.db.get_connection() as conn:
                conditions = ["status = 'active'"]
                params = []
                
                if zones:
                    conditions.append(f"zone = ANY($1)")
                    params.append(zones)
                
                where_clause = " AND ".join(conditions)
                
                query = f"""
                    SELECT 
                        p.plot_id,
                        p.section_id,
                        p.zone,
                        p.area_rai,
                        p.crop_type,
                        p.planting_date,
                        p.expected_harvest_date,
                        s.delivery_gate,
                        s.elevation_m
                    FROM ros_gis.plots p
                    JOIN ros_gis.sections s ON p.section_id = s.section_id
                    WHERE {where_clause}
                    ORDER BY p.zone, p.section_id, p.plot_id
                """
                
                results = await conn.fetch(query, *params)
                
                return [dict(row) for row in results]
                
        except Exception as e:
            self.logger.error("Failed to get active plots", error=str(e))
            # Fallback to mock data
            return self._get_mock_plots(zones)
    
    def _get_mock_plots(self, zones: Optional[List[int]] = None) -> List[Dict]:
        """Get mock plot data for testing"""
        mock_plots = []
        zones_to_use = zones or [2, 3, 5, 6]
        
        for zone in zones_to_use:
            for section in ['A', 'B', 'C', 'D']:
                for plot in range(1, 6):  # 5 plots per section
                    mock_plots.append({
                        'plot_id': f"Z{zone}S{section}P{plot}",
                        'section_id': f"Zone_{zone}_Section_{section}",
                        'zone': zone,
                        'area_rai': 20 + (plot * 5),  # 20-45 rai per plot
                        'crop_type': 'rice' if zone in [2, 3] else 'sugarcane',
                        'planting_date': (datetime.now() - timedelta(days=30)).date(),
                        'expected_harvest_date': (datetime.now() + timedelta(days=90)).date(),
                        'delivery_gate': f"M(0,{2 if zone in [2,3] else 5})->Zone_{zone}",
                        'elevation_m': 220 - (zone * 0.5)
                    })
        
        return mock_plots
    
    async def _store_daily_demands(self, demands: Dict[str, Dict]) -> None:
        """Store calculated daily demands"""
        try:
            async with self.db.get_connection() as conn:
                # Prepare bulk insert
                values = []
                for plot_id, demand in demands.items():
                    values.append((
                        plot_id,
                        demand['section_id'],
                        demand['date'],
                        demand['ros_demand_m3'],
                        demand['aquacrop_demand_m3'],
                        demand['combined_demand_m3'],
                        demand['crop_type'],
                        demand['growth_stage'],
                        demand['stress_level'],
                        demand['area_rai'],
                        demand['source']
                    ))
                
                # Bulk insert
                await conn.executemany(
                    """
                    INSERT INTO ros_gis.daily_demands
                    (plot_id, section_id, date, ros_demand_m3, aquacrop_demand_m3,
                     combined_demand_m3, crop_type, growth_stage, stress_level,
                     area_rai, source)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (plot_id, date) DO UPDATE SET
                        ros_demand_m3 = EXCLUDED.ros_demand_m3,
                        aquacrop_demand_m3 = EXCLUDED.aquacrop_demand_m3,
                        combined_demand_m3 = EXCLUDED.combined_demand_m3,
                        growth_stage = EXCLUDED.growth_stage,
                        stress_level = EXCLUDED.stress_level,
                        source = EXCLUDED.source,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    values
                )
                
                self.logger.info(
                    "Stored daily demands",
                    count=len(values)
                )
                
        except Exception as e:
            self.logger.error("Failed to store daily demands", error=str(e))
    
    async def _get_stored_daily_demands(
        self,
        start_date: date,
        end_date: date,
        zones: Optional[List[int]] = None
    ) -> List[Dict]:
        """Retrieve stored daily demands for a date range"""
        try:
            async with self.db.get_connection() as conn:
                conditions = [
                    "date >= $1",
                    "date < $2"
                ]
                params = [start_date, end_date]
                
                if zones:
                    conditions.append(f"zone = ANY($3)")
                    params.append(zones)
                
                where_clause = " AND ".join(conditions)
                
                query = f"""
                    SELECT 
                        dd.*,
                        s.zone,
                        s.delivery_gate
                    FROM ros_gis.daily_demands dd
                    JOIN ros_gis.sections s ON dd.section_id = s.section_id
                    WHERE {where_clause}
                    ORDER BY dd.date, dd.section_id, dd.plot_id
                """
                
                results = await conn.fetch(query, *params)
                return [dict(row) for row in results]
                
        except Exception as e:
            self.logger.error(
                "Failed to get stored demands",
                error=str(e)
            )
            return []
    
    async def _get_delivery_infrastructure(
        self,
        section_id: str
    ) -> Dict[str, str]:
        """Get delivery gate and irrigation channel for a section"""
        try:
            async with self.db.get_connection() as conn:
                query = """
                    SELECT 
                        s.delivery_gate,
                        gm.irrigation_channel,
                        gm.gate_id
                    FROM ros_gis.sections s
                    LEFT JOIN ros_gis.gate_mappings gm ON s.section_id = gm.section_id
                    WHERE s.section_id = $1
                """
                
                result = await conn.fetchone(query, section_id)
                
                if result:
                    return {
                        "delivery_gate": result['delivery_gate'] or result['gate_id'],
                        "irrigation_channel": result['irrigation_channel'] or 'main'
                    }
                
                # Default based on zone
                zone = int(section_id.split('_')[1]) if '_' in section_id else 1
                return {
                    "delivery_gate": f"M(0,{2 if zone in [2,3] else 5})->Zone_{zone}",
                    "irrigation_channel": f"channel_zone_{zone}"
                }
                
        except Exception as e:
            self.logger.error(
                "Failed to get delivery infrastructure",
                section_id=section_id,
                error=str(e)
            )
            return {
                "delivery_gate": "unknown",
                "irrigation_channel": "unknown"
            }
    
    def _get_growth_stage(self, crop_type: str, crop_week: int) -> str:
        """Determine growth stage based on crop type and week"""
        if crop_type == "rice":
            if crop_week <= 3:
                return "seedling"
            elif crop_week <= 7:
                return "tillering"
            elif crop_week <= 11:
                return "flowering"
            elif crop_week <= 14:
                return "grain_filling"
            else:
                return "maturity"
        elif crop_type == "sugarcane":
            if crop_week <= 12:
                return "germination"
            elif crop_week <= 28:
                return "tillering"
            elif crop_week <= 40:
                return "grand_growth"
            elif crop_week <= 48:
                return "ripening"
            else:
                return "maturity"
        else:
            return "vegetative"
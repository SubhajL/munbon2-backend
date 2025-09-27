"""
Daily Demand Scheduler Service
Handles scheduled daily water demand calculations and database storage
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import aiocron
from core import get_logger
from config import settings
from db import DatabaseManager
from services.daily_demand_calculator import DailyDemandCalculator
from api.subscriptions import publish_demand_update

logger = get_logger(__name__)


class DailyDemandScheduler:
    """Schedules and manages daily water demand calculations"""
    
    def __init__(self):
        self.logger = logger.bind(service="daily_demand_scheduler")
        self.db = DatabaseManager()
        self.calculator = DailyDemandCalculator()
        self.daily_task = None
        self.is_running = False
    
    async def start_scheduler(self):
        """Start the daily scheduler - runs at 2 AM every day"""
        if self.is_running:
            self.logger.warning("Daily scheduler already running")
            return
        
        # Schedule for 2 AM every day
        self.daily_task = aiocron.crontab('0 2 * * *', func=self.run_daily_calculation)
        self.is_running = True
        
        self.logger.info("Daily demand scheduler started (runs at 2:00 AM)")
        
        # Also run immediately if in development mode
        if settings.environment == "development":
            self.logger.info("Development mode: Running initial calculation")
            asyncio.create_task(self.run_daily_calculation())
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.daily_task:
            self.daily_task.stop()
            self.daily_task = None
            self.is_running = False
            self.logger.info("Daily demand scheduler stopped")
    
    async def run_daily_calculation(self):
        """Run the daily water demand calculation process"""
        start_time = datetime.now()
        calculation_date = date.today()
        
        try:
            self.logger.info(
                "Starting daily demand calculation",
                date=calculation_date.isoformat()
            )
            
            # Get active crop season configuration
            season_config = await self._get_active_season_config()
            if not season_config:
                self.logger.warning("No active crop season found, skipping calculation")
                return
            
            # Determine which zones to calculate based on season config
            zones = await self._get_zones_to_calculate(season_config)
            
            # Calculate daily demands for all active plots
            daily_demands = await self.calculator.calculate_daily_demands(
                calculation_date,
                zones
            )
            
            # Store results in database
            stored_count = await self._store_daily_demands_batch(
                daily_demands,
                season_config['config_id']
            )
            
            # Aggregate to section, zone, and munbon levels
            aggregations = await self._aggregate_spatial_levels(
                daily_demands,
                calculation_date,
                season_config['config_id']
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(
                "Daily demand calculation completed",
                date=calculation_date.isoformat(),
                plots_calculated=len(daily_demands),
                stored_count=stored_count,
                duration_seconds=duration,
                aggregations=aggregations
            )
            
            # Store calculation summary
            await self._store_calculation_summary(
                calculation_date,
                len(daily_demands),
                stored_count,
                aggregations,
                duration
            )
            
            # Publish update notifications
            await self._publish_calculation_updates(calculation_date, aggregations)
            
        except Exception as e:
            self.logger.error(
                "Daily calculation failed",
                date=calculation_date.isoformat(),
                error=str(e)
            )
            raise
    
    async def _get_active_season_config(self) -> Optional[Dict]:
        """Get the active crop season configuration"""
        query = """
            SELECT config_id, season_name, season_year, 
                   coverage_type, selected_zones, selected_sections,
                   demand_combination_strategy, awd_integration_enabled
            FROM ros_gis.crop_season_config
            WHERE is_active = true
            LIMIT 1
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query)
            if row:
                return dict(row)
            return None
    
    async def _get_zones_to_calculate(self, season_config: Dict) -> Optional[List[int]]:
        """Determine which zones to calculate based on season config"""
        coverage_type = season_config['coverage_type']
        
        if coverage_type == 'full_munbon':
            return None  # Calculate all zones
        elif coverage_type == 'zones':
            return season_config['selected_zones']
        elif coverage_type == 'sections':
            # Get unique zones from selected sections
            sections = season_config['selected_sections']
            zones = set()
            for section_id in sections:
                # Extract zone from section ID (format: ZZ-XX-XX-XX)
                zone = int(section_id.split('-')[0])
                zones.add(zone)
            return list(zones)
        
        return None
    
    async def _store_daily_demands_batch(
        self, 
        demands: Dict[str, Dict],
        season_config_id: str
    ) -> int:
        """Store daily demands in batch"""
        if not demands:
            return 0
        
        # Prepare batch insert data
        values = []
        for plot_id, demand in demands.items():
            values.append((
                plot_id,
                demand['section_id'],
                demand['date'],
                demand.get('ros_demand_m3'),
                demand.get('aquacrop_demand_m3'),
                demand['combined_demand_m3'],
                demand.get('crop_type'),
                demand.get('growth_stage'),
                demand.get('stress_level'),
                demand.get('area_rai'),
                demand.get('source'),
                season_config_id
            ))
        
        query = """
            INSERT INTO ros_gis.daily_demands (
                plot_id, section_id, date,
                ros_demand_m3, aquacrop_demand_m3, combined_demand_m3,
                crop_type, growth_stage, stress_level,
                area_rai, source, season_config_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (plot_id, date) 
            DO UPDATE SET
                ros_demand_m3 = EXCLUDED.ros_demand_m3,
                aquacrop_demand_m3 = EXCLUDED.aquacrop_demand_m3,
                combined_demand_m3 = EXCLUDED.combined_demand_m3,
                growth_stage = EXCLUDED.growth_stage,
                stress_level = EXCLUDED.stress_level,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with await self.db.get_connection() as conn:
            # Use executemany for batch insert
            await conn.executemany(query, values)
        
        return len(values)
    
    async def _aggregate_spatial_levels(
        self,
        plot_demands: Dict[str, Dict],
        calculation_date: date,
        season_config_id: str
    ) -> Dict[str, int]:
        """Aggregate demands to section, zone, and munbon levels"""
        
        # Group by section
        section_demands = {}
        for plot_id, demand in plot_demands.items():
            section_id = demand['section_id']
            if section_id not in section_demands:
                section_demands[section_id] = {
                    'total_demand_m3': 0,
                    'total_area_rai': 0,
                    'plot_count': 0
                }
            
            section_demands[section_id]['total_demand_m3'] += demand['combined_demand_m3']
            section_demands[section_id]['total_area_rai'] += demand.get('area_rai', 0)
            section_demands[section_id]['plot_count'] += 1
        
        # Store section aggregations
        await self._store_section_aggregations(
            section_demands,
            calculation_date,
            season_config_id
        )
        
        # Group by zone
        zone_demands = {}
        for section_id, section_data in section_demands.items():
            # Extract zone from section ID (format: ZZ-XX-XX-XX)
            zone = int(section_id.split('-')[0])
            if zone not in zone_demands:
                zone_demands[zone] = {
                    'total_demand_m3': 0,
                    'total_area_rai': 0,
                    'section_count': 0
                }
            
            zone_demands[zone]['total_demand_m3'] += section_data['total_demand_m3']
            zone_demands[zone]['total_area_rai'] += section_data['total_area_rai']
            zone_demands[zone]['section_count'] += 1
        
        # Store zone aggregations
        await self._store_zone_aggregations(
            zone_demands,
            calculation_date,
            season_config_id
        )
        
        # Calculate munbon total
        munbon_total = sum(z['total_demand_m3'] for z in zone_demands.values())
        munbon_area = sum(z['total_area_rai'] for z in zone_demands.values())
        
        # Store munbon aggregation
        await self._store_munbon_aggregation(
            munbon_total,
            munbon_area,
            len(zone_demands),
            calculation_date,
            season_config_id
        )
        
        return {
            'sections': len(section_demands),
            'zones': len(zone_demands),
            'munbon_total_m3': munbon_total
        }
    
    async def _store_section_aggregations(
        self,
        section_demands: Dict,
        calculation_date: date,
        season_config_id: str
    ):
        """Store section-level aggregations"""
        query = """
            INSERT INTO ros_gis.daily_demand_aggregations (
                aggregation_level, area_id, date,
                total_demand_m3, total_area_rai, unit_count,
                season_config_id
            ) VALUES ('section', $1, $2, $3, $4, $5, $6)
            ON CONFLICT (aggregation_level, area_id, date)
            DO UPDATE SET
                total_demand_m3 = EXCLUDED.total_demand_m3,
                total_area_rai = EXCLUDED.total_area_rai,
                unit_count = EXCLUDED.unit_count,
                updated_at = CURRENT_TIMESTAMP
        """
        
        values = [
            (
                section_id,
                calculation_date,
                data['total_demand_m3'],
                data['total_area_rai'],
                data['plot_count'],
                season_config_id
            )
            for section_id, data in section_demands.items()
        ]
        
        async with await self.db.get_connection() as conn:
            await conn.executemany(query, values)
    
    async def _store_zone_aggregations(
        self,
        zone_demands: Dict,
        calculation_date: date,
        season_config_id: str
    ):
        """Store zone-level aggregations"""
        query = """
            INSERT INTO ros_gis.daily_demand_aggregations (
                aggregation_level, area_id, date,
                total_demand_m3, total_area_rai, unit_count,
                season_config_id
            ) VALUES ('zone', $1, $2, $3, $4, $5, $6)
            ON CONFLICT (aggregation_level, area_id, date)
            DO UPDATE SET
                total_demand_m3 = EXCLUDED.total_demand_m3,
                total_area_rai = EXCLUDED.total_area_rai,
                unit_count = EXCLUDED.unit_count,
                updated_at = CURRENT_TIMESTAMP
        """
        
        values = [
            (
                str(zone),
                calculation_date,
                data['total_demand_m3'],
                data['total_area_rai'],
                data['section_count'],
                season_config_id
            )
            for zone, data in zone_demands.items()
        ]
        
        async with await self.db.get_connection() as conn:
            await conn.executemany(query, values)
    
    async def _store_munbon_aggregation(
        self,
        total_demand_m3: float,
        total_area_rai: float,
        zone_count: int,
        calculation_date: date,
        season_config_id: str
    ):
        """Store munbon-level aggregation"""
        query = """
            INSERT INTO ros_gis.daily_demand_aggregations (
                aggregation_level, area_id, date,
                total_demand_m3, total_area_rai, unit_count,
                season_config_id
            ) VALUES ('munbon', 'munbon', $1, $2, $3, $4, $5)
            ON CONFLICT (aggregation_level, area_id, date)
            DO UPDATE SET
                total_demand_m3 = EXCLUDED.total_demand_m3,
                total_area_rai = EXCLUDED.total_area_rai,
                unit_count = EXCLUDED.unit_count,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                query,
                calculation_date,
                total_demand_m3,
                total_area_rai,
                zone_count,
                season_config_id
            )
    
    async def _store_calculation_summary(
        self,
        calculation_date: date,
        plots_calculated: int,
        stored_count: int,
        aggregations: Dict,
        duration_seconds: float
    ):
        """Store calculation summary for monitoring"""
        query = """
            INSERT INTO ros_gis.daily_calculation_summary (
                calculation_date, plots_calculated, records_stored,
                sections_aggregated, zones_aggregated, 
                munbon_total_m3, duration_seconds, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        
        status = 'success' if stored_count == plots_calculated else 'partial'
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                query,
                calculation_date,
                plots_calculated,
                stored_count,
                aggregations['sections'],
                aggregations['zones'],
                aggregations['munbon_total_m3'],
                duration_seconds,
                status
            )
    
    async def _publish_calculation_updates(
        self, 
        calculation_date: date,
        aggregations: Dict
    ):
        """Publish calculation completion updates via Redis"""
        # Publish zone-level updates
        for zone in range(1, 7):  # Zones 1-6
            await publish_demand_update(
                section_id=f"zone_{zone}",
                level_type="zone",
                method="daily_batch",
                gross_demand_m3=0,  # Will be fetched by subscribers
                net_demand_m3=0,
                trigger="scheduled"
            )
        
        # Publish munbon-level update
        await publish_demand_update(
            section_id="munbon",
            level_type="munbon", 
            method="daily_batch",
            gross_demand_m3=0,
            net_demand_m3=aggregations['munbon_total_m3'],
            trigger="scheduled"
        )
        
        self.logger.info(
            "Published demand updates",
            date=calculation_date.isoformat(),
            zones_notified=6,
            munbon_total=aggregations['munbon_total_m3']
        )
    
    async def run_manual_calculation(self, target_date: Optional[date] = None):
        """Manually trigger daily calculation for testing or recovery"""
        if target_date is None:
            target_date = date.today()
        
        self.logger.info(
            "Running manual daily calculation",
            date=target_date.isoformat()
        )
        
        # Temporarily set the date
        original_today = date.today
        date.today = lambda: target_date
        
        try:
            await self.run_daily_calculation()
        finally:
            date.today = original_today


# Singleton instance
daily_demand_scheduler = DailyDemandScheduler()
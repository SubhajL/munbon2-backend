"""
Weekly Accumulation Scheduler Service
Handles scheduled weekly water demand accumulation for control intervals
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import aiocron
from core import get_logger
from config import settings
from db import DatabaseManager
from services.daily_demand_calculator import DailyDemandCalculator, ControlInterval
from services.scheduler_client import SchedulerClient

logger = get_logger(__name__)


class WeeklyAccumulationScheduler:
    """Schedules and manages weekly water demand accumulation"""
    
    def __init__(self):
        self.logger = logger.bind(service="weekly_accumulation_scheduler")
        self.db = DatabaseManager()
        self.calculator = DailyDemandCalculator()
        self.scheduler_client = SchedulerClient()
        self.weekly_task = None
        self.is_running = False
    
    async def start_scheduler(self):
        """Start the weekly scheduler - runs Monday at 3 AM"""
        if self.is_running:
            self.logger.warning("Weekly scheduler already running")
            return
        
        # Schedule for Monday 3 AM every week
        self.weekly_task = aiocron.crontab('0 3 * * 1', func=self.run_weekly_accumulation)
        self.is_running = True
        
        self.logger.info("Weekly accumulation scheduler started (runs Monday at 3:00 AM)")
        
        # Also run immediately if in development mode
        if settings.environment == "development":
            self.logger.info("Development mode: Running initial accumulation")
            asyncio.create_task(self.run_weekly_accumulation())
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        if self.weekly_task:
            self.weekly_task.stop()
            self.weekly_task = None
            self.is_running = False
            self.logger.info("Weekly accumulation scheduler stopped")
    
    async def run_weekly_accumulation(self):
        """Run the weekly accumulation process"""
        start_time = datetime.now()
        
        # Calculate the week that just completed (last Monday to Sunday)
        today = date.today()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        
        try:
            self.logger.info(
                "Starting weekly accumulation",
                week_start=last_monday.isoformat(),
                week_end=(last_monday + timedelta(days=6)).isoformat()
            )
            
            # Get active crop season configuration
            season_config = await self._get_active_season_config()
            if not season_config:
                self.logger.warning("No active crop season found, skipping accumulation")
                return
            
            # Determine zones to process
            zones = await self._get_zones_to_process(season_config)
            
            # Accumulate weekly demands
            weekly_accumulation = await self.calculator.accumulate_to_control_interval(
                last_monday,
                ControlInterval.WEEKLY,
                zones
            )
            
            # Store accumulated demands
            stored_count = await self._store_accumulated_demands(
                weekly_accumulation,
                season_config['config_id']
            )
            
            # Group by irrigation infrastructure (gates and channels)
            infrastructure_grouping = await self._group_by_infrastructure(
                weekly_accumulation['section_demands']
            )
            
            # Send to scheduler service for delivery planning
            if infrastructure_grouping['gate_groups']:
                schedule_result = await self._send_to_scheduler(
                    infrastructure_grouping,
                    last_monday,
                    ControlInterval.WEEKLY
                )
            else:
                schedule_result = None
            
            duration = (datetime.now() - start_time).total_seconds()
            
            self.logger.info(
                "Weekly accumulation completed",
                week_start=last_monday.isoformat(),
                sections_processed=len(weekly_accumulation['section_demands']),
                channels_grouped=len(weekly_accumulation['channel_demands']),
                gates_scheduled=len(infrastructure_grouping.get('gate_groups', {})),
                duration_seconds=duration
            )
            
            # Store accumulation summary
            await self._store_accumulation_summary(
                last_monday,
                weekly_accumulation,
                infrastructure_grouping,
                schedule_result,
                duration
            )
            
        except Exception as e:
            self.logger.error(
                "Weekly accumulation failed",
                week_start=last_monday.isoformat(),
                error=str(e)
            )
            raise
    
    async def _get_active_season_config(self) -> Optional[Dict]:
        """Get the active crop season configuration"""
        query = """
            SELECT config_id, season_name, season_year, 
                   coverage_type, selected_zones, selected_sections,
                   accumulation_period
            FROM ros_gis.crop_season_config
            WHERE is_active = true
            LIMIT 1
        """
        
        async with await self.db.get_connection() as conn:
            row = await conn.fetchrow(query)
            if row:
                return dict(row)
            return None
    
    async def _get_zones_to_process(self, season_config: Dict) -> Optional[List[int]]:
        """Determine which zones to process based on season config"""
        coverage_type = season_config['coverage_type']
        
        if coverage_type == 'full_munbon':
            return None  # Process all zones
        elif coverage_type == 'zones':
            return season_config['selected_zones']
        elif coverage_type == 'sections':
            # Get unique zones from selected sections
            sections = season_config['selected_sections']
            zones = set()
            for section_id in sections:
                zone = int(section_id.split('-')[0])
                zones.add(zone)
            return list(zones)
        
        return None
    
    async def _store_accumulated_demands(
        self,
        accumulation: Dict,
        season_config_id: str
    ) -> int:
        """Store accumulated demands in database"""
        section_demands = accumulation['section_demands']
        interval_info = accumulation['interval']
        
        values = []
        for section_id, demand_data in section_demands.items():
            values.append((
                section_id,
                interval_info['type'],
                interval_info['start'],
                interval_info['end'],
                demand_data['total_demand_m3'],
                demand_data['plot_count'],
                demand_data['avg_daily_demand_m3'],
                demand_data['peak_daily_demand_m3'],
                demand_data['delivery_gate'],
                demand_data['irrigation_channel'],
                None,  # schedule_id will be updated later
                season_config_id
            ))
        
        query = """
            INSERT INTO ros_gis.accumulated_demands (
                section_id, control_interval, start_date, end_date,
                total_demand_m3, plot_count, avg_daily_demand_m3,
                peak_daily_demand_m3, delivery_gate, irrigation_channel,
                schedule_id, season_config_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (section_id, control_interval, start_date)
            DO UPDATE SET
                total_demand_m3 = EXCLUDED.total_demand_m3,
                plot_count = EXCLUDED.plot_count,
                avg_daily_demand_m3 = EXCLUDED.avg_daily_demand_m3,
                peak_daily_demand_m3 = EXCLUDED.peak_daily_demand_m3,
                updated_at = CURRENT_TIMESTAMP
        """
        
        async with await self.db.get_connection() as conn:
            await conn.executemany(query, values)
        
        return len(values)
    
    async def _group_by_infrastructure(
        self,
        section_demands: Dict[str, Dict]
    ) -> Dict:
        """Group sections by delivery gates and irrigation channels"""
        gate_groups = {}
        channel_groups = {}
        
        for section_id, demand in section_demands.items():
            gate = demand.get('delivery_gate')
            channel = demand.get('irrigation_channel')
            
            # Group by gate
            if gate:
                if gate not in gate_groups:
                    gate_groups[gate] = {
                        'sections': [],
                        'total_demand_m3': 0,
                        'total_area_rai': 0,
                        'channel': channel
                    }
                
                gate_groups[gate]['sections'].append(section_id)
                gate_groups[gate]['total_demand_m3'] += demand['total_demand_m3']
                gate_groups[gate]['total_area_rai'] += demand.get('total_area_rai', 0)
            
            # Group by channel
            if channel:
                if channel not in channel_groups:
                    channel_groups[channel] = {
                        'sections': [],
                        'gates': set(),
                        'total_demand_m3': 0
                    }
                
                channel_groups[channel]['sections'].append(section_id)
                if gate:
                    channel_groups[channel]['gates'].add(gate)
                channel_groups[channel]['total_demand_m3'] += demand['total_demand_m3']
        
        # Convert sets to lists for serialization
        for channel_data in channel_groups.values():
            channel_data['gates'] = list(channel_data['gates'])
        
        return {
            'gate_groups': gate_groups,
            'channel_groups': channel_groups
        }
    
    async def _send_to_scheduler(
        self,
        infrastructure_grouping: Dict,
        start_date: date,
        interval: ControlInterval
    ) -> Optional[Dict]:
        """Send accumulated demands to scheduler service"""
        try:
            # Prepare schedule request
            schedule_request = {
                'control_interval': interval.value,
                'start_date': start_date.isoformat(),
                'end_date': (start_date + timedelta(days=6)).isoformat(),
                'gate_demands': []
            }
            
            for gate_id, gate_data in infrastructure_grouping['gate_groups'].items():
                schedule_request['gate_demands'].append({
                    'gate_id': gate_id,
                    'sections': gate_data['sections'],
                    'total_demand_m3': gate_data['total_demand_m3'],
                    'channel_id': gate_data.get('channel'),
                    'priority': 'normal'  # Could be enhanced with priority logic
                })
            
            # Send to scheduler service
            result = await self.scheduler_client.create_schedule(schedule_request)
            
            if result:
                # Update accumulated demands with schedule ID
                await self._update_schedule_ids(
                    infrastructure_grouping['gate_groups'],
                    result.get('schedule_id'),
                    start_date
                )
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to send to scheduler", error=str(e))
            return None
    
    async def _update_schedule_ids(
        self,
        gate_groups: Dict,
        schedule_id: str,
        start_date: date
    ):
        """Update accumulated demands with schedule ID"""
        all_sections = []
        for gate_data in gate_groups.values():
            all_sections.extend(gate_data['sections'])
        
        query = """
            UPDATE ros_gis.accumulated_demands
            SET schedule_id = $1
            WHERE section_id = ANY($2)
            AND start_date = $3
            AND control_interval = 'weekly'
        """
        
        async with await self.db.get_connection() as conn:
            await conn.execute(query, schedule_id, all_sections, start_date)
    
    async def _store_accumulation_summary(
        self,
        week_start: date,
        accumulation: Dict,
        infrastructure: Dict,
        schedule_result: Optional[Dict],
        duration_seconds: float
    ):
        """Store accumulation summary for monitoring"""
        query = """
            INSERT INTO ros_gis.weekly_accumulation_summary (
                week_start_date, week_end_date,
                sections_processed, total_demand_m3,
                gates_scheduled, channels_involved,
                schedule_created, schedule_id,
                duration_seconds, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """
        
        total_demand = sum(
            s['total_demand_m3'] 
            for s in accumulation['section_demands'].values()
        )
        
        status = 'success' if schedule_result else 'no_schedule'
        
        async with await self.db.get_connection() as conn:
            await conn.execute(
                query,
                week_start,
                week_start + timedelta(days=6),
                len(accumulation['section_demands']),
                total_demand,
                len(infrastructure['gate_groups']),
                len(infrastructure['channel_groups']),
                schedule_result is not None,
                schedule_result.get('schedule_id') if schedule_result else None,
                duration_seconds,
                status
            )
    
    async def run_manual_accumulation(
        self, 
        week_start: Optional[date] = None,
        interval: ControlInterval = ControlInterval.WEEKLY
    ):
        """Manually trigger accumulation for testing or recovery"""
        if week_start is None:
            # Default to last Monday
            today = date.today()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday + 7)
        
        self.logger.info(
            "Running manual accumulation",
            week_start=week_start.isoformat(),
            interval=interval.value
        )
        
        # Temporarily override the date calculation
        original_today = date.today
        date.today = lambda: week_start + timedelta(days=7)
        
        try:
            await self.run_weekly_accumulation()
        finally:
            date.today = original_today


# Singleton instance
weekly_accumulation_scheduler = WeeklyAccumulationScheduler()
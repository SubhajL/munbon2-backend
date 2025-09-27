"""
Weekly Scheduler for Water Demand Calculations
Runs every Monday at 3 AM to calculate weekly demands
"""

import asyncio
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.weekly_demand_calculator_v2 import WeeklyDemandCalculatorV2
from services.crop_season_demand_calculator import CropSeasonDemandCalculator
from utils.logger import get_logger

logger = get_logger(__name__)


class WeeklyScheduler:
    """Manages weekly scheduled tasks for water demand calculations"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.demand_calculator = WeeklyDemandCalculatorV2()
        self.crop_progress_calculator = CropSeasonDemandCalculator()
        
    def start(self):
        """Start the scheduler"""
        # Schedule weekly demand calculation every Monday at 3 AM
        self.scheduler.add_job(
            self._run_weekly_calculations,
            CronTrigger(day_of_week='mon', hour=3, minute=0),
            id='weekly_demand_calculation',
            name='Weekly Water Demand Calculation',
            misfire_grace_time=3600  # 1 hour grace period
        )
        
        # Also run immediately if it's Monday and hasn't run today
        if datetime.now().weekday() == 0:  # Monday
            self.scheduler.add_job(
                self._run_weekly_calculations,
                'date',
                run_date=datetime.now(),
                id='immediate_weekly_calculation'
            )
        
        self.scheduler.start()
        logger.info("Weekly scheduler started")
        
    async def _run_weekly_calculations(self):
        """Run all weekly calculations"""
        try:
            logger.info("Starting weekly calculations")
            start_time = datetime.now()
            
            # Step 1: Calculate weekly demands using actual data from services
            await self.demand_calculator.calculate_weekly_demands()
            
            # Step 2: Update crop season progress
            await self.crop_progress_calculator.update_weekly_progress()
            
            # Step 3: Generate daily demand schedules for the week
            # This would call daily_demand_scheduler service
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Weekly calculations completed in {duration:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error in weekly calculations: {str(e)}", exc_info=True)
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Weekly scheduler stopped")
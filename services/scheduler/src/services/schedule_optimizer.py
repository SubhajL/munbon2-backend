from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from uuid import UUID
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..core.logger import get_logger
from ..core.redis import RedisClient
from ..core.config import settings
from ..models.schedule import (
    WeeklySchedule, ScheduledOperation, FieldInstruction,
    OptimizationConstraint, FieldTeam
)
from ..algorithms.mixed_integer_optimizer import MixedIntegerOptimizer
from ..algorithms.travel_optimizer import TravelOptimizer
from .demand_aggregator import DemandAggregator
from .field_instruction_generator import FieldInstructionGenerator
from .weekly_adjustment_accumulator import WeeklyAdjustmentAccumulator
from .clients import ROSClient, GISClient, FlowMonitoringClient, WeatherClient

logger = get_logger(__name__)


class ScheduleOptimizer:
    """Main service for schedule optimization"""
    
    def __init__(
        self,
        db: AsyncSession,
        redis: RedisClient,
        ros_client: ROSClient,
        gis_client: GISClient,
        flow_client: FlowMonitoringClient,
        weather_client: Optional[WeatherClient] = None
    ):
        self.db = db
        self.redis = redis
        self.demand_aggregator = DemandAggregator(ros_client, gis_client, flow_client, redis)
        self.milp_optimizer = MixedIntegerOptimizer({"timeout_seconds": settings.optimization_timeout_seconds})
        self.travel_optimizer = TravelOptimizer()
        self.instruction_generator = FieldInstructionGenerator()
        self.ros_client = ros_client
        self.gis_client = gis_client
        self.flow_client = flow_client
        self.weather_client = weather_client or WeatherClient()
        self.adjustment_accumulator = WeeklyAdjustmentAccumulator(
            db, redis, ros_client, self.weather_client
        )
    
    async def generate_weekly_schedule(
        self,
        week_number: int,
        year: int,
        constraints: Optional[Dict[str, Any]] = None
    ) -> WeeklySchedule:
        """Generate optimized schedule for a week"""
        
        logger.info(f"Generating schedule for week {week_number}, {year}")
        
        # Step 1: Aggregate demands
        demands = await self.demand_aggregator.aggregate_weekly_demands(week_number, year)
        
        # Step 1.5: Apply weather-based adjustments from previous week
        weather_adjustments = await self.adjustment_accumulator.get_weekly_adjustments_for_scheduling(
            week_number, year
        )
        demands = await self._apply_weather_adjustments(demands, weather_adjustments)
        
        # Step 2: Get network topology
        network = await self._get_network_data()
        
        # Step 3: Get available teams
        teams = await self._get_available_teams(week_number, year)
        
        # Step 4: Get optimization constraints
        db_constraints = await self._get_optimization_constraints()
        
        # Step 5: Prepare time horizon
        time_horizon = self._prepare_time_horizon(week_number, year, constraints)
        
        # Step 6: Run optimization
        optimization_result = await self._run_optimization(
            demands, network, teams, db_constraints, time_horizon
        )
        
        # Step 7: Create schedule record
        schedule = await self._create_schedule_record(
            week_number, year, demands, optimization_result
        )
        
        # Step 8: Create operation records
        operations = await self._create_operation_records(
            schedule, optimization_result, network
        )
        
        # Step 9: Generate field instructions
        instructions = await self._generate_field_instructions(
            schedule, operations, teams, optimization_result
        )
        
        # Step 10: Save to database
        await self._save_schedule(schedule, operations, instructions)
        
        logger.info(f"Schedule generated successfully: {schedule.schedule_code}")
        
        return schedule
    
    async def _get_network_data(self) -> Dict[str, Any]:
        """Get network topology and gate information"""
        
        # Get from Flow Monitoring Service
        gate_positions = await self.flow_client.get_gate_positions()
        
        # Get canal network from GIS
        canal_network = await self.gis_client.get_canal_network_topology()
        
        # Combine data
        network = {
            "gates": {},
            "canals": canal_network.get("canals", {}),
            "connections": canal_network.get("connections", []),
        }
        
        # Enrich gate data
        for gate_id, position in gate_positions.items():
            gate_info = canal_network.get("gates", {}).get(gate_id, {})
            network["gates"][gate_id] = {
                **gate_info,
                "current_position": position,
                "id": gate_id,
            }
        
        return network
    
    async def _get_available_teams(self, week_number: int, year: int) -> List[Dict]:
        """Get available field teams for the week"""
        
        # Query database for active teams
        result = await self.db.execute(
            select(FieldTeam).where(FieldTeam.is_active == True)
        )
        teams = result.scalars().all()
        
        # Convert to dict format
        team_list = []
        for team in teams:
            team_dict = {
                "team_code": team.team_code,
                "team_name": team.team_name,
                "max_operations_per_day": team.max_operations_per_day,
                "available_days": team.available_days,
                "base_location_lat": team.base_location_lat,
                "base_location_lng": team.base_location_lng,
                "supervisor_name": team.supervisor_name,
                "supervisor_phone": team.supervisor_phone,
            }
            team_list.append(team_dict)
        
        return team_list
    
    async def _get_optimization_constraints(self) -> List[OptimizationConstraint]:
        """Get active optimization constraints from database"""
        
        result = await self.db.execute(
            select(OptimizationConstraint).where(
                OptimizationConstraint.is_active == True
            )
        )
        
        return result.scalars().all()
    
    def _prepare_time_horizon(
        self,
        week_number: int,
        year: int,
        user_constraints: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Prepare time horizon for optimization"""
        
        # Calculate week dates
        jan1 = date(year, 1, 1)
        week_start = jan1 + timedelta(days=(week_number - 1) * 7 - jan1.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Default operation days (Tuesday, Thursday)
        operation_days = [1, 3]  # 0=Monday, 6=Sunday
        
        # Override with user constraints if provided
        if user_constraints:
            if "operation_days" in user_constraints:
                operation_days = user_constraints["operation_days"]
        
        return {
            "start_date": week_start,
            "end_date": week_end,
            "operation_days": operation_days,
            "slot_minutes": 30,  # 30-minute time slots
            "work_start": "07:00",
            "work_end": "17:00",
        }
    
    async def _run_optimization(
        self,
        demands: Dict,
        network: Dict,
        teams: List,
        constraints: List,
        time_horizon: Dict
    ) -> Dict[str, Any]:
        """Run the optimization algorithm"""
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            self.milp_optimizer.optimize,
            demands,
            network,
            teams,
            constraints,
            time_horizon
        )
        
        return result
    
    async def _create_schedule_record(
        self,
        week_number: int,
        year: int,
        demands: Dict,
        optimization_result: Dict
    ) -> WeeklySchedule:
        """Create schedule database record"""
        
        # Calculate week dates
        jan1 = date(year, 1, 1)
        week_start = jan1 + timedelta(days=(week_number - 1) * 7 - jan1.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Extract metrics
        operations = optimization_result.get("operations", [])
        metrics = optimization_result.get("metrics", {})
        
        # Calculate efficiency
        total_demand = demands.get("totalDemandM3", 0)
        total_allocated = sum(op.get("expected_flow", 0) * 3600 for op in operations)  # Convert to m³
        efficiency = (total_allocated / total_demand * 100) if total_demand > 0 else 0
        
        # Create schedule
        schedule = WeeklySchedule(
            schedule_code=f"SCH-{year}-W{week_number:02d}",
            week_number=week_number,
            year=year,
            start_date=week_start,
            end_date=week_end,
            status="draft",
            version=1,
            total_water_demand_m3=total_demand,
            total_water_allocated_m3=total_allocated,
            efficiency_percent=efficiency,
            total_operations=len(operations),
            field_days=[week_start + timedelta(days=d) for d in [1, 3]],  # Tue, Thu
            total_travel_km=metrics.get("total_distance_km", 0),
            estimated_labor_hours=metrics.get("total_duration_minutes", 0) / 60,
            optimization_time_seconds=metrics.get("optimization_time", 0),
            optimization_iterations=metrics.get("iterations", 0),
            objective_value=metrics.get("objective_value", 0),
            constraints_summary={
                "demand_constraints": len(demands.get("byZone", {})),
                "team_constraints": len(optimization_result.get("team_routes", {})),
                "applied_constraints": optimization_result.get("status", "unknown"),
            },
            weather_forecast={
                "source": "forecast_placeholder",
                "rain_probability": 0.1,
                "temperature_avg": 28,
            },
        )
        
        return schedule
    
    async def _create_operation_records(
        self,
        schedule: WeeklySchedule,
        optimization_result: Dict,
        network: Dict
    ) -> List[ScheduledOperation]:
        """Create operation records from optimization result"""
        
        operations = []
        
        for op_data in optimization_result.get("operations", []):
            gate_id = op_data["gate_id"]
            gate_info = network["gates"].get(gate_id, {})
            
            operation = ScheduledOperation(
                schedule_id=schedule.id,
                gate_id=gate_id,
                gate_name=gate_info.get("name", gate_id),
                canal_name=gate_info.get("canal", ""),
                zone_id=str(gate_info.get("zone", "")),
                operation_date=op_data["time_slot"].date(),
                planned_start_time=op_data["time_slot"].time(),
                planned_end_time=(op_data["time_slot"] + timedelta(minutes=15)).time(),
                duration_minutes=15,
                current_opening_percent=gate_info.get("current_position", 0),
                target_opening_percent=op_data["target_opening"],
                operation_type=self._determine_operation_type(
                    gate_info.get("current_position", 0),
                    op_data["target_opening"]
                ),
                expected_flow_before=gate_info.get("current_flow", 0),
                expected_flow_after=op_data["expected_flow"],
                downstream_impact=self._calculate_downstream_impact(gate_id, network),
                team_id=op_data["team_id"],
                team_name=op_data.get("team_name", op_data["team_id"]),
                operation_sequence=op_data.get("sequence", 1),
                latitude=gate_info.get("latitude", 0),
                longitude=gate_info.get("longitude", 0),
                location_description=gate_info.get("description", ""),
                status="scheduled",
            )
            
            operations.append(operation)
        
        return operations
    
    def _determine_operation_type(self, current: float, target: float) -> str:
        """Determine operation type based on positions"""
        
        if target > current:
            return "open"
        elif target < current:
            return "close"
        else:
            return "maintain"
    
    def _calculate_downstream_impact(self, gate_id: str, network: Dict) -> List[str]:
        """Calculate which areas are affected downstream"""
        
        # Simplified - in reality would trace network graph
        downstream_map = {
            "M(0,0)": ["All zones"],
            "M(0,2)": ["Zone 1", "Zone 2"],
            "M(0,3)": ["Zone 3", "Zone 4"],
            "M(0,4)": ["Zone 5", "Zone 6"],
        }
        
        return downstream_map.get(gate_id, ["Unknown"])
    
    async def _generate_field_instructions(
        self,
        schedule: WeeklySchedule,
        operations: List[ScheduledOperation],
        teams: List[Dict],
        optimization_result: Dict
    ) -> List[FieldInstruction]:
        """Generate field instructions for each team"""
        
        instructions = []
        team_routes = optimization_result.get("team_routes", {})
        
        for team in teams:
            team_id = team["team_code"]
            
            # Get operations for this team
            team_operations = [op for op in operations if op.team_id == team_id]
            
            if team_operations:
                # Get route info
                route_info = team_routes.get(team_id, {})
                
                # Generate instruction
                instruction = await self.instruction_generator.generate_team_instructions(
                    schedule.id,
                    team_id,
                    team_operations,
                    route_info,
                    team
                )
                
                instructions.append(instruction)
        
        return instructions
    
    async def _save_schedule(
        self,
        schedule: WeeklySchedule,
        operations: List[ScheduledOperation],
        instructions: List[FieldInstruction]
    ):
        """Save schedule and related records to database"""
        
        # Add to session
        self.db.add(schedule)
        
        for operation in operations:
            self.db.add(operation)
        
        for instruction in instructions:
            self.db.add(instruction)
        
        # Commit transaction
        await self.db.commit()
        
        # Refresh to get IDs
        await self.db.refresh(schedule)
        
        # Cache current schedule
        await self.redis.set_json(
            f"current_schedule:{schedule.year}:week_{schedule.week_number}",
            {
                "id": str(schedule.id),
                "code": schedule.schedule_code,
                "status": schedule.status,
                "total_operations": schedule.total_operations,
            },
            expire=86400  # 24 hours
        )
    
    async def approve_schedule(self, schedule_id: UUID, approver: str) -> WeeklySchedule:
        """Approve a schedule for execution"""
        
        # Get schedule
        result = await self.db.execute(
            select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        if schedule.status != "draft":
            raise ValueError(f"Schedule is not in draft status: {schedule.status}")
        
        # Update status
        schedule.status = "approved"
        schedule.updated_by = approver
        
        await self.db.commit()
        await self.db.refresh(schedule)
        
        # Notify teams
        await self._notify_teams_of_approval(schedule)
        
        return schedule
    
    async def _notify_teams_of_approval(self, schedule: WeeklySchedule):
        """Notify field teams that schedule is approved"""
        
        # Get team assignments
        result = await self.db.execute(
            select(FieldInstruction).where(
                FieldInstruction.schedule_id == schedule.id
            )
        )
        instructions = result.scalars().all()
        
        # Send notifications (simplified)
        for instruction in instructions:
            notification = {
                "type": "schedule_approved",
                "schedule_id": str(schedule.id),
                "team_id": instruction.team_id,
                "operation_date": instruction.operation_date.isoformat(),
                "total_operations": instruction.total_operations,
            }
            
            # Publish to Redis for real-time notification
            await self.redis.publish(
                f"team_notifications:{instruction.team_id}",
                notification
            )
    
    async def get_schedule_by_week(
        self,
        week_number: int,
        year: int
    ) -> Optional[WeeklySchedule]:
        """Get schedule for a specific week"""
        
        result = await self.db.execute(
            select(WeeklySchedule).where(
                and_(
                    WeeklySchedule.week_number == week_number,
                    WeeklySchedule.year == year,
                    WeeklySchedule.status.in_(["draft", "approved", "active"])
                )
            ).order_by(WeeklySchedule.version.desc())
        )
        
        return result.scalar_one_or_none()
    
    async def _apply_weather_adjustments(
        self,
        demands: Dict[str, Any],
        weather_adjustments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply weather-based adjustments from previous week to water demands.
        
        This implements the accumulation of weather impacts on next week's schedule:
        - Rainfall > 10mm → Reduce irrigation by 30%
        - Rainfall > 25mm → Cancel operations for affected days
        - Temperature drop > 5°C → Reduce ET by 20%
        - High wind → Increase application time by 15%
        """
        logger.info(f"Applying weather adjustments from week {weather_adjustments.get('based_on_week')}")
        
        adjusted_demands = demands.copy()
        zone_adjustments = weather_adjustments.get("zone_adjustments", {})
        
        # Track total adjustments for reporting
        total_original_demand = 0
        total_adjusted_demand = 0
        
        # Apply adjustments to each zone
        for zone in adjusted_demands.get("zones", []):
            zone_id = zone["zone_id"]
            original_demand = zone["total_demand_m3"]
            total_original_demand += original_demand
            
            if zone_id in zone_adjustments:
                adj = zone_adjustments[zone_id]
                
                # Apply demand modifier (multiplicative)
                adjusted_demand = original_demand * adj["demand_modifier"]
                zone["total_demand_m3"] = adjusted_demand
                zone["weather_adjusted"] = True
                zone["adjustment_factor"] = adj["demand_modifier"]
                zone["adjustment_reasons"] = adj["adjustment_reasons"]
                
                # Apply to individual plots
                for plot in zone.get("plots", []):
                    plot["demand_m3"] *= adj["demand_modifier"]
                    plot["weather_adjusted"] = True
                
                # Mark blackout dates
                if adj["blackout_dates"]:
                    zone["blackout_dates"] = adj["blackout_dates"]
                    zone["skip_irrigation_days"] = len(adj["blackout_dates"])
                
                # Note application time increases
                if adj["application_time_modifier"] > 1.0:
                    zone["application_time_modifier"] = adj["application_time_modifier"]
                    zone["extended_operation_time"] = True
                
                # ET adjustments
                if adj["et_modifier"] != 1.0:
                    zone["et_modifier"] = adj["et_modifier"]
                    zone["et_adjusted"] = True
                
                total_adjusted_demand += adjusted_demand
                
                logger.info(
                    f"Zone {zone_id}: Demand adjusted from {original_demand:.0f} to "
                    f"{adjusted_demand:.0f} m³ ({(adj['demand_modifier']-1)*100:+.1f}%)"
                )
            else:
                total_adjusted_demand += original_demand
        
        # Update summary
        adjusted_demands["weather_adjustments_applied"] = True
        adjusted_demands["total_demand_reduction_m3"] = total_original_demand - total_adjusted_demand
        adjusted_demands["total_demand_reduction_percent"] = (
            (total_original_demand - total_adjusted_demand) / total_original_demand * 100
            if total_original_demand > 0 else 0
        )
        
        # Store adjustment report for zone managers
        report = await self.adjustment_accumulator.generate_adjustment_report(
            weather_adjustments["week_number"],
            weather_adjustments["year"]
        )
        
        # Cache the report
        await self.redis.set_json(
            f"weather_adjustment_report:{weather_adjustments['week_number']}:{weather_adjustments['year']}",
            report,
            ex=30 * 24 * 3600  # Keep for 30 days
        )
        
        logger.info(
            f"Weather adjustments applied: {total_original_demand:.0f} → "
            f"{total_adjusted_demand:.0f} m³ ({adjusted_demands['total_demand_reduction_percent']:.1f}% reduction)"
        )
        
        return adjusted_demands
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from uuid import UUID, uuid4
import asyncio
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import selectinload

from ..core.logger import get_logger
from ..core.redis import RedisClient
from ..models.schedule import (
    WeeklySchedule, ScheduledOperation, FieldTeam,
    OptimizationConstraint
)
from ..algorithms.mixed_integer_optimizer import MixedIntegerOptimizer
from ..algorithms.travel_optimizer import TravelOptimizer
from .clients import ROSClient, GISClient, FlowMonitoringClient
from .demand_aggregator import DemandAggregator

logger = get_logger(__name__)


class AdaptationStrategy(Enum):
    """Adaptation strategies for different scenarios"""
    REROUTE_FLOW = "reroute_flow"
    DELAY_OPERATIONS = "delay_operations"
    REDUCE_DEMAND = "reduce_demand"
    INCREASE_FLOW = "increase_flow"
    EMERGENCY_OVERRIDE = "emergency_override"
    PARTIAL_DELIVERY = "partial_delivery"
    NONE = "none"


class RealTimeAdapter:
    """Handle real-time adaptation of schedules based on dynamic events"""
    
    def __init__(
        self,
        db: AsyncSession,
        redis: RedisClient,
        ros_client: ROSClient,
        gis_client: GISClient,
        flow_client: FlowMonitoringClient
    ):
        self.db = db
        self.redis = redis
        self.ros_client = ros_client
        self.gis_client = gis_client
        self.flow_client = flow_client
        self.demand_aggregator = DemandAggregator(
            ros_client, gis_client, flow_client, redis
        )
        self.milp_optimizer = MixedIntegerOptimizer({"timeout_seconds": 30})
        self.travel_optimizer = TravelOptimizer()
    
    async def handle_gate_failure(
        self,
        schedule_id: UUID,
        gate_id: str,
        failure_type: str,
        estimated_repair_hours: float,
        timestamp: datetime
    ) -> Dict[str, Any]:
        """
        Handle gate failure by rerouting water flow and rescheduling operations.
        
        Process:
        1. Assess hydraulic impact
        2. Find alternative flow paths
        3. Identify affected operations
        4. Generate adaptation strategy
        5. Reschedule operations
        6. Notify teams
        """
        logger.warning(f"Handling gate failure: {gate_id} - {failure_type}")
        
        # Get schedule and affected operations
        schedule = await self._get_schedule(schedule_id)
        affected_ops = await self._get_affected_operations(schedule_id, gate_id, timestamp)
        
        # Assess hydraulic impact
        impact = await self._assess_gate_failure_impact(gate_id)
        
        # Find alternative paths
        alternatives = await self._find_alternative_paths(
            gate_id,
            impact["affected_zones"]
        )
        
        # Determine strategy
        strategy = self._determine_failure_strategy(
            impact,
            alternatives,
            estimated_repair_hours
        )
        
        # Execute adaptation
        adaptation_result = await self._execute_gate_failure_adaptation(
            schedule,
            affected_ops,
            strategy,
            alternatives,
            gate_id,
            estimated_repair_hours
        )
        
        # Store adaptation history
        await self._store_adaptation_history(
            schedule_id,
            "gate_failure",
            {
                "gate_id": gate_id,
                "failure_type": failure_type,
                "strategy": strategy.value,
                "affected_operations": len(affected_ops),
            },
            adaptation_result
        )
        
        # Send notifications
        notifications = await self._send_failure_notifications(
            affected_ops,
            gate_id,
            strategy,
            adaptation_result
        )
        
        return {
            "id": str(uuid4()),
            "strategy": strategy.value,
            "affected_operations": [str(op.id) for op in affected_ops],
            "new_operations": adaptation_result.get("new_operations", []),
            "water_impact": impact["water_shortage_m3"],
            "affected_zones": impact["affected_zones"],
            "delay_hours": estimated_repair_hours if strategy == AdaptationStrategy.DELAY_OPERATIONS else 0,
            "notifications": notifications,
        }
    
    async def handle_weather_change(
        self,
        schedule_id: UUID,
        weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle weather changes by adjusting water demands and operations.
        
        Weather impacts:
        - Rainfall: Reduce irrigation requirements
        - Temperature: Adjust ET rates
        - Wind: Modify application efficiency
        """
        logger.info(f"Handling weather change for schedule {schedule_id}")
        
        schedule = await self._get_schedule(schedule_id)
        
        # Analyze weather impact on demands
        impact_analysis = await self.ros_client.analyze_weather_impact(
            weather_data,
            schedule.week_number,
            schedule.year
        )
        
        # Determine if adaptation is needed
        if abs(impact_analysis["demand_adjustment_percent"]) < 5:
            logger.info("Weather impact minimal, no adaptation needed")
            return {
                "id": str(uuid4()),
                "strategy": AdaptationStrategy.NONE.value,
                "affected_operations": [],
                "demand_adjustment": impact_analysis["demand_adjustment_percent"],
                "water_saved": 0,
                "notifications": [],
            }
        
        # Get adjusted demands
        adjusted_demands = await self.ros_client.get_adjusted_demands(
            schedule.week_number,
            schedule.year,
            impact_analysis["adjustment_factors"]
        )
        
        # Identify operations to modify
        affected_ops = await self._get_future_operations(schedule_id)
        
        # Recalculate gate operations
        modified_ops = await self._adjust_operations_for_demand(
            affected_ops,
            adjusted_demands,
            impact_analysis["demand_adjustment_percent"]
        )
        
        # Update operations in database
        await self._update_operations(modified_ops)
        
        # Calculate water saved
        original_water = sum(op.expected_flow_after * op.duration_minutes * 60 for op in affected_ops)
        adjusted_water = sum(op["expected_flow"] * op["duration_minutes"] * 60 for op in modified_ops)
        water_saved = original_water - adjusted_water
        
        # Send notifications
        notifications = await self._send_weather_notifications(
            affected_ops,
            weather_data,
            impact_analysis
        )
        
        return {
            "id": str(uuid4()),
            "affected_operations": [str(op.id) for op in affected_ops],
            "modified_operations": modified_ops,
            "demand_adjustment": impact_analysis["demand_adjustment_percent"],
            "water_saved": water_saved,
            "notifications": notifications,
        }
    
    async def handle_demand_change(
        self,
        schedule_id: UUID,
        zone_id: str,
        plot_ids: List[str],
        demand_change_m3: float,
        urgency: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Handle sudden demand changes (emergency requests, crop stress).
        
        Urgency levels:
        - emergency: Immediate response required
        - high: Within 4 hours
        - normal: Within 24 hours
        """
        logger.info(f"Handling demand change: {zone_id} - {demand_change_m3}m³ ({urgency})")
        
        schedule = await self._get_schedule(schedule_id)
        
        # Check water availability
        available_water = await self.flow_client.get_available_water(zone_id)
        
        if demand_change_m3 > available_water["available_m3"]:
            # Need to reallocate from other zones
            reallocation = await self._plan_water_reallocation(
                zone_id,
                demand_change_m3,
                available_water,
                urgency
            )
        else:
            reallocation = None
        
        # Find gates to adjust
        gates_to_adjust = await self._find_gates_for_zone(zone_id)
        
        # Calculate new gate settings
        gate_adjustments = await self._calculate_gate_adjustments(
            gates_to_adjust,
            demand_change_m3,
            urgency == "emergency"
        )
        
        # Create new operations
        new_operations = []
        for gate_id, adjustment in gate_adjustments.items():
            new_op = await self._create_emergency_operation(
                schedule_id,
                gate_id,
                adjustment,
                urgency,
                reason
            )
            new_operations.append(new_op)
        
        # If emergency, execute immediately
        if urgency == "emergency":
            await self._execute_emergency_operations(new_operations)
        
        # Send notifications
        notifications = await self._send_demand_change_notifications(
            zone_id,
            demand_change_m3,
            urgency,
            new_operations
        )
        
        return {
            "id": str(uuid4()),
            "affected_operations": [],
            "new_operations": [self._serialize_operation(op) for op in new_operations],
            "gates_adjusted": list(gate_adjustments.keys()),
            "estimated_delivery_time": self._estimate_delivery_time(urgency),
            "notifications": notifications,
        }
    
    async def reoptimize_schedule(
        self,
        schedule_id: UUID,
        from_date: date,
        constraints: Optional[Dict[str, Any]] = None,
        reason: str = "Manual reoptimization"
    ) -> Dict[str, Any]:
        """
        Perform full reoptimization of remaining schedule.
        
        Used when:
        - Multiple failures accumulate
        - Significant deviations occur
        - Manual intervention requested
        """
        logger.info(f"Reoptimizing schedule {schedule_id} from {from_date}")
        
        schedule = await self._get_schedule(schedule_id)
        
        # Get completed and in-progress operations (fixed)
        fixed_ops = await self._get_fixed_operations(schedule_id, from_date)
        
        # Get remaining operations to reoptimize
        flexible_ops = await self._get_flexible_operations(schedule_id, from_date)
        
        if not flexible_ops:
            logger.info("No operations to reoptimize")
            return {
                "new_version": schedule.version,
                "changes": [],
                "metrics": {},
            }
        
        # Get current system state
        system_state = await self._get_system_state()
        
        # Update demands based on what's been delivered
        remaining_demands = await self._calculate_remaining_demands(
            schedule,
            fixed_ops,
            from_date
        )
        
        # Get network data
        network = await self._get_network_data()
        
        # Get available teams
        teams = await self._get_available_teams(from_date)
        
        # Build new constraints
        optimization_constraints = await self._build_reoptimization_constraints(
            fixed_ops,
            system_state,
            constraints
        )
        
        # Run optimization
        optimization_result = await self._run_reoptimization(
            remaining_demands,
            network,
            teams,
            optimization_constraints,
            fixed_ops,
            from_date
        )
        
        # Compare with current schedule
        changes = self._compare_schedules(flexible_ops, optimization_result["operations"])
        
        # Update operations
        await self._apply_schedule_changes(schedule_id, changes)
        
        # Increment version
        schedule.version += 1
        await self.db.commit()
        
        # Send notifications
        await self._send_reoptimization_notifications(changes, reason)
        
        return {
            "new_version": schedule.version,
            "changes": changes,
            "metrics": optimization_result["metrics"],
        }
    
    async def _assess_gate_failure_impact(self, gate_id: str) -> Dict[str, Any]:
        """Assess hydraulic impact of gate failure"""
        
        # Get downstream impact from Flow Monitoring
        impact = await self.flow_client.simulate_gate_failure(gate_id)
        
        # Get affected zones from GIS
        affected_zones = await self.gis_client.get_zones_affected_by_gate(gate_id)
        
        # Calculate water shortage
        water_shortage = impact.get("flow_reduction_m3s", 0) * 3600 * 24  # Daily shortage
        
        return {
            "water_shortage_m3": water_shortage,
            "affected_zones": affected_zones,
            "downstream_gates": impact.get("affected_gates", []),
            "pressure_drop": impact.get("pressure_drop_percent", 0),
        }
    
    async def _find_alternative_paths(
        self,
        failed_gate_id: str,
        affected_zones: List[str]
    ) -> List[Dict[str, Any]]:
        """Find alternative water delivery paths"""
        
        alternatives = []
        
        for zone in affected_zones:
            # Get alternative paths from Flow Monitoring
            paths = await self.flow_client.find_alternative_paths(
                source="main_canal",
                destination=zone,
                blocked_gates=[failed_gate_id]
            )
            
            for path in paths:
                # Evaluate path feasibility
                feasibility = await self._evaluate_path_feasibility(path)
                
                if feasibility["is_feasible"]:
                    alternatives.append({
                        "zone": zone,
                        "path": path["gates"],
                        "additional_loss_percent": path["efficiency_loss"],
                        "travel_time_minutes": path["travel_time"],
                        "required_adjustments": feasibility["adjustments"],
                    })
        
        return alternatives
    
    def _determine_failure_strategy(
        self,
        impact: Dict[str, Any],
        alternatives: List[Dict[str, Any]],
        repair_hours: float
    ) -> AdaptationStrategy:
        """Determine best adaptation strategy"""
        
        # If short repair time and low impact, delay operations
        if repair_hours <= 4 and impact["water_shortage_m3"] < 1000:
            return AdaptationStrategy.DELAY_OPERATIONS
        
        # If good alternatives exist, reroute
        if alternatives and all(alt["additional_loss_percent"] < 20 for alt in alternatives):
            return AdaptationStrategy.REROUTE_FLOW
        
        # If partial alternatives, partial delivery
        if alternatives:
            return AdaptationStrategy.PARTIAL_DELIVERY
        
        # If critical shortage, emergency override
        if impact["water_shortage_m3"] > 5000:
            return AdaptationStrategy.EMERGENCY_OVERRIDE
        
        # Default to delay
        return AdaptationStrategy.DELAY_OPERATIONS
    
    async def _execute_gate_failure_adaptation(
        self,
        schedule: WeeklySchedule,
        affected_ops: List[ScheduledOperation],
        strategy: AdaptationStrategy,
        alternatives: List[Dict[str, Any]],
        failed_gate_id: str,
        repair_hours: float
    ) -> Dict[str, Any]:
        """Execute the chosen adaptation strategy"""
        
        if strategy == AdaptationStrategy.DELAY_OPERATIONS:
            # Delay all affected operations
            delay_time = timedelta(hours=repair_hours)
            new_ops = []
            
            for op in affected_ops:
                op.operation_date += delay_time
                op.planned_start_time = (
                    datetime.combine(date.min, op.planned_start_time) + delay_time
                ).time()
                op.notes = f"Delayed due to {failed_gate_id} failure"
                new_ops.append(self._serialize_operation(op))
            
            await self.db.commit()
            return {"new_operations": new_ops}
            
        elif strategy == AdaptationStrategy.REROUTE_FLOW:
            # Create new operations for alternative paths
            new_ops = []
            
            for alt in alternatives:
                for gate_id in alt["path"]:
                    if gate_id != failed_gate_id:
                        # Create operation for alternative gate
                        new_op = await self._create_reroute_operation(
                            schedule.id,
                            gate_id,
                            alt["required_adjustments"].get(gate_id, 50),
                            alt["zone"]
                        )
                        new_ops.append(self._serialize_operation(new_op))
            
            # Cancel original operations on failed gate
            for op in affected_ops:
                if op.gate_id == failed_gate_id:
                    op.status = "cancelled"
                    op.cancellation_reason = f"Gate failure: {failed_gate_id}"
            
            await self.db.commit()
            return {"new_operations": new_ops}
            
        elif strategy == AdaptationStrategy.PARTIAL_DELIVERY:
            # Prioritize critical areas
            critical_zones = await self.ros_client.get_critical_zones()
            new_ops = []
            
            # Allocate available water to critical zones first
            for alt in alternatives:
                if alt["zone"] in critical_zones:
                    for gate_id in alt["path"]:
                        if gate_id != failed_gate_id:
                            new_op = await self._create_reroute_operation(
                                schedule.id,
                                gate_id,
                                alt["required_adjustments"].get(gate_id, 30),  # Reduced flow
                                alt["zone"]
                            )
                            new_ops.append(self._serialize_operation(new_op))
            
            return {"new_operations": new_ops}
            
        else:
            # Emergency override - notify human operators
            return {"new_operations": [], "requires_manual_intervention": True}
    
    async def _get_schedule(self, schedule_id: UUID) -> WeeklySchedule:
        """Get schedule with error handling"""
        result = await self.db.execute(
            select(WeeklySchedule).where(WeeklySchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        return schedule
    
    async def _get_affected_operations(
        self,
        schedule_id: UUID,
        gate_id: str,
        from_time: datetime
    ) -> List[ScheduledOperation]:
        """Get operations affected by gate failure"""
        
        # Direct operations on the failed gate
        direct_result = await self.db.execute(
            select(ScheduledOperation).where(
                and_(
                    ScheduledOperation.schedule_id == schedule_id,
                    ScheduledOperation.gate_id == gate_id,
                    ScheduledOperation.operation_date >= from_time.date(),
                    ScheduledOperation.status == "scheduled"
                )
            )
        )
        direct_ops = list(direct_result.scalars().all())
        
        # Downstream operations that depend on this gate
        downstream_gates = await self.flow_client.get_downstream_gates(gate_id)
        
        if downstream_gates:
            downstream_result = await self.db.execute(
                select(ScheduledOperation).where(
                    and_(
                        ScheduledOperation.schedule_id == schedule_id,
                        ScheduledOperation.gate_id.in_(downstream_gates),
                        ScheduledOperation.operation_date >= from_time.date(),
                        ScheduledOperation.status == "scheduled"
                    )
                )
            )
            downstream_ops = list(downstream_result.scalars().all())
        else:
            downstream_ops = []
        
        return direct_ops + downstream_ops
    
    async def _get_future_operations(self, schedule_id: UUID) -> List[ScheduledOperation]:
        """Get all future scheduled operations"""
        result = await self.db.execute(
            select(ScheduledOperation).where(
                and_(
                    ScheduledOperation.schedule_id == schedule_id,
                    ScheduledOperation.operation_date >= date.today(),
                    ScheduledOperation.status == "scheduled"
                )
            )
        )
        return list(result.scalars().all())
    
    async def _adjust_operations_for_demand(
        self,
        operations: List[ScheduledOperation],
        adjusted_demands: Dict[str, Any],
        adjustment_percent: float
    ) -> List[Dict[str, Any]]:
        """Adjust gate operations for new demands"""
        
        modified_ops = []
        
        for op in operations:
            # Calculate new opening based on demand adjustment
            new_opening = op.target_opening_percent * (1 + adjustment_percent / 100)
            new_opening = max(0, min(100, new_opening))  # Clamp to 0-100
            
            # Calculate new flow
            gate_info = await self.flow_client.get_gate_info(op.gate_id)
            new_flow = new_opening * gate_info["max_flow"] / 100
            
            modified_ops.append({
                "id": str(op.id),
                "gate_id": op.gate_id,
                "target_opening": new_opening,
                "expected_flow": new_flow,
                "duration_minutes": op.duration_minutes,
                "adjustment_reason": f"Weather adjustment: {adjustment_percent:.1f}%",
            })
        
        return modified_ops
    
    async def _update_operations(self, modified_ops: List[Dict[str, Any]]):
        """Update operations in database"""
        for op_data in modified_ops:
            await self.db.execute(
                update(ScheduledOperation)
                .where(ScheduledOperation.id == op_data["id"])
                .values(
                    target_opening_percent=op_data["target_opening"],
                    expected_flow_after=op_data["expected_flow"],
                    notes=op_data.get("adjustment_reason", "")
                )
            )
        
        await self.db.commit()
    
    async def _find_gates_for_zone(self, zone_id: str) -> List[str]:
        """Find gates that deliver water to a zone"""
        delivery_gates = await self.gis_client.get_zone_delivery_gates(zone_id)
        return delivery_gates
    
    async def _calculate_gate_adjustments(
        self,
        gate_ids: List[str],
        additional_flow_m3s: float,
        is_emergency: bool
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate gate adjustments to deliver additional flow"""
        
        adjustments = {}
        flow_per_gate = additional_flow_m3s / len(gate_ids) if gate_ids else 0
        
        for gate_id in gate_ids:
            gate_info = await self.flow_client.get_gate_info(gate_id)
            current_opening = gate_info["current_opening"]
            max_flow = gate_info["max_flow"]
            
            # Calculate required opening for additional flow
            current_flow = current_opening * max_flow / 100
            required_flow = current_flow + flow_per_gate
            required_opening = required_flow * 100 / max_flow
            
            # Clamp to limits
            if is_emergency:
                required_opening = min(100, required_opening)  # Allow full open
            else:
                required_opening = min(90, required_opening)  # Safety margin
            
            adjustments[gate_id] = {
                "current_opening": current_opening,
                "target_opening": required_opening,
                "additional_flow": flow_per_gate,
                "is_feasible": required_opening <= 100,
            }
        
        return adjustments
    
    async def _create_emergency_operation(
        self,
        schedule_id: UUID,
        gate_id: str,
        adjustment: Dict[str, Any],
        urgency: str,
        reason: str
    ) -> ScheduledOperation:
        """Create emergency operation"""
        
        gate_info = await self.flow_client.get_gate_info(gate_id)
        
        # Determine operation time based on urgency
        if urgency == "emergency":
            operation_time = datetime.now() + timedelta(minutes=30)
        elif urgency == "high":
            operation_time = datetime.now() + timedelta(hours=2)
        else:
            operation_time = datetime.now() + timedelta(hours=12)
        
        operation = ScheduledOperation(
            schedule_id=schedule_id,
            gate_id=gate_id,
            gate_name=gate_info.get("name", gate_id),
            operation_date=operation_time.date(),
            planned_start_time=operation_time.time(),
            planned_end_time=(operation_time + timedelta(minutes=15)).time(),
            duration_minutes=15,
            current_opening_percent=adjustment["current_opening"],
            target_opening_percent=adjustment["target_opening"],
            operation_type="emergency",
            expected_flow_after=adjustment["target_opening"] * gate_info["max_flow"] / 100,
            priority="high" if urgency == "emergency" else "normal",
            notes=f"Emergency: {reason}",
            status="scheduled",
            created_by="system",
        )
        
        self.db.add(operation)
        await self.db.commit()
        await self.db.refresh(operation)
        
        return operation
    
    async def _create_reroute_operation(
        self,
        schedule_id: UUID,
        gate_id: str,
        target_opening: float,
        zone: str
    ) -> ScheduledOperation:
        """Create operation for rerouted flow"""
        
        gate_info = await self.flow_client.get_gate_info(gate_id)
        
        operation = ScheduledOperation(
            schedule_id=schedule_id,
            gate_id=gate_id,
            gate_name=gate_info.get("name", gate_id),
            zone_id=zone,
            operation_date=date.today(),
            planned_start_time=datetime.now().time(),
            planned_end_time=(datetime.now() + timedelta(minutes=30)).time(),
            duration_minutes=30,
            current_opening_percent=gate_info.get("current_opening", 0),
            target_opening_percent=target_opening,
            operation_type="reroute",
            expected_flow_after=target_opening * gate_info["max_flow"] / 100,
            priority="high",
            notes="Rerouted due to gate failure",
            status="scheduled",
            created_by="system",
        )
        
        self.db.add(operation)
        await self.db.commit()
        await self.db.refresh(operation)
        
        return operation
    
    def _serialize_operation(self, op: ScheduledOperation) -> Dict[str, Any]:
        """Serialize operation for API response"""
        return {
            "id": str(op.id),
            "gate_id": op.gate_id,
            "gate_name": op.gate_name,
            "date": op.operation_date.isoformat(),
            "time": op.planned_start_time.isoformat(),
            "target_opening": op.target_opening_percent,
            "expected_flow": op.expected_flow_after,
            "type": op.operation_type,
            "status": op.status,
            "team_id": op.team_id,
            "notes": op.notes,
        }
    
    async def _store_adaptation_history(
        self,
        schedule_id: UUID,
        event_type: str,
        event_data: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """Store adaptation event in history"""
        
        history_entry = {
            "id": str(uuid4()),
            "schedule_id": str(schedule_id),
            "event_type": event_type,
            "event_data": event_data,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Store in Redis with expiry
        key = f"adaptation_history:{schedule_id}"
        await self.redis.add_to_list(key, history_entry)
        await self.redis.expire(key, 86400 * 30)  # 30 days
        
        # Also store in global history
        await self.redis.add_to_list("adaptation_history:all", history_entry)
    
    async def _send_failure_notifications(
        self,
        affected_ops: List[ScheduledOperation],
        gate_id: str,
        strategy: AdaptationStrategy,
        result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Send notifications about gate failure"""
        
        notifications = []
        affected_teams = set(op.team_id for op in affected_ops if op.team_id)
        
        for team_id in affected_teams:
            notification = {
                "type": "gate_failure",
                "team_id": team_id,
                "gate_id": gate_id,
                "strategy": strategy.value,
                "message": f"Gate {gate_id} has failed. Strategy: {strategy.value}",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Send via Redis pub/sub
            await self.redis.publish(f"team_notifications:{team_id}", notification)
            notifications.append(notification)
        
        # Send system alert
        system_alert = {
            "type": "system_alert",
            "severity": "warning",
            "title": f"Gate Failure: {gate_id}",
            "message": f"Gate {gate_id} has failed. {len(affected_ops)} operations affected.",
            "metadata": {
                "gate_id": gate_id,
                "strategy": strategy.value,
                "affected_teams": list(affected_teams),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.redis.publish("system_alerts", system_alert)
        notifications.append(system_alert)
        
        return notifications
    
    async def _send_weather_notifications(
        self,
        affected_ops: List[ScheduledOperation],
        weather_data: Dict[str, Any],
        impact: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Send weather change notifications"""
        
        notifications = []
        affected_teams = set(op.team_id for op in affected_ops if op.team_id)
        
        message = f"Weather update: "
        if weather_data.get("rainfall_mm", 0) > 0:
            message += f"{weather_data['rainfall_mm']}mm rainfall. "
        if weather_data.get("temperature_change", 0) != 0:
            message += f"Temperature {'increased' if weather_data['temperature_change'] > 0 else 'decreased'} by {abs(weather_data['temperature_change'])}°C. "
        
        message += f"Irrigation adjusted by {impact['demand_adjustment_percent']:.1f}%"
        
        for team_id in affected_teams:
            notification = {
                "type": "weather_update",
                "team_id": team_id,
                "message": message,
                "impact": impact["demand_adjustment_percent"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            await self.redis.publish(f"team_notifications:{team_id}", notification)
            notifications.append(notification)
        
        return notifications
    
    async def _send_demand_change_notifications(
        self,
        zone_id: str,
        demand_change: float,
        urgency: str,
        operations: List[ScheduledOperation]
    ) -> List[Dict[str, Any]]:
        """Send demand change notifications"""
        
        notifications = []
        
        for op in operations:
            if op.team_id:
                notification = {
                    "type": "demand_change",
                    "team_id": op.team_id,
                    "zone_id": zone_id,
                    "urgency": urgency,
                    "message": f"{urgency.upper()}: Additional {demand_change}m³ required for {zone_id}",
                    "operation": {
                        "gate_id": op.gate_id,
                        "time": op.planned_start_time.isoformat(),
                        "action": f"Open to {op.target_opening_percent}%",
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
                
                await self.redis.publish(f"team_notifications:{op.team_id}", notification)
                notifications.append(notification)
        
        return notifications
    
    def _estimate_delivery_time(self, urgency: str) -> str:
        """Estimate water delivery time based on urgency"""
        if urgency == "emergency":
            return "30-60 minutes"
        elif urgency == "high":
            return "2-4 hours"
        else:
            return "12-24 hours"
    
    async def _execute_emergency_operations(self, operations: List[ScheduledOperation]):
        """Execute emergency operations immediately"""
        
        for op in operations:
            # Send direct command to Flow Monitoring
            try:
                await self.flow_client.set_gate_position(
                    op.gate_id,
                    op.target_opening_percent,
                    priority="emergency"
                )
                
                # Update operation status
                op.status = "in_progress"
                op.actual_start_time = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Failed to execute emergency operation: {e}")
                op.status = "failed"
                op.failure_reason = str(e)
        
        await self.db.commit()
    
    async def _evaluate_path_feasibility(self, path: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if alternative path can handle required flow"""
        
        gates = path["gates"]
        required_flow = path["required_flow_m3s"]
        
        # Check each gate capacity
        adjustments = {}
        is_feasible = True
        
        for gate_id in gates:
            gate_info = await self.flow_client.get_gate_info(gate_id)
            max_flow = gate_info["max_flow"]
            current_flow = gate_info["current_opening"] * max_flow / 100
            
            available_capacity = max_flow - current_flow
            
            if available_capacity < required_flow:
                is_feasible = False
                adjustments[gate_id] = 100  # Max opening
            else:
                new_flow = current_flow + required_flow
                adjustments[gate_id] = new_flow * 100 / max_flow
        
        return {
            "is_feasible": is_feasible,
            "adjustments": adjustments,
        }
    
    async def _get_fixed_operations(
        self,
        schedule_id: UUID,
        from_date: date
    ) -> List[ScheduledOperation]:
        """Get operations that cannot be changed"""
        
        result = await self.db.execute(
            select(ScheduledOperation).where(
                and_(
                    ScheduledOperation.schedule_id == schedule_id,
                    or_(
                        ScheduledOperation.status.in_(["completed", "in_progress"]),
                        ScheduledOperation.operation_date < from_date
                    )
                )
            )
        )
        
        return list(result.scalars().all())
    
    async def _get_flexible_operations(
        self,
        schedule_id: UUID,
        from_date: date
    ) -> List[ScheduledOperation]:
        """Get operations that can be reoptimized"""
        
        result = await self.db.execute(
            select(ScheduledOperation).where(
                and_(
                    ScheduledOperation.schedule_id == schedule_id,
                    ScheduledOperation.status == "scheduled",
                    ScheduledOperation.operation_date >= from_date
                )
            )
        )
        
        return list(result.scalars().all())
    
    async def _get_system_state(self) -> Dict[str, Any]:
        """Get current system state"""
        
        gate_positions = await self.flow_client.get_all_gate_positions()
        water_levels = await self.flow_client.get_water_levels()
        
        return {
            "gate_positions": gate_positions,
            "water_levels": water_levels,
            "timestamp": datetime.utcnow(),
        }
    
    async def _calculate_remaining_demands(
        self,
        schedule: WeeklySchedule,
        completed_ops: List[ScheduledOperation],
        from_date: date
    ) -> Dict[str, Any]:
        """Calculate remaining water demands"""
        
        # Get original weekly demands
        original_demands = await self.demand_aggregator.aggregate_weekly_demands(
            schedule.week_number,
            schedule.year
        )
        
        # Calculate delivered water
        delivered = {}
        for op in completed_ops:
            zone = op.zone_id or "unknown"
            if zone not in delivered:
                delivered[zone] = 0
            
            # Estimate delivered volume
            if op.actual_flow_achieved:
                delivered[zone] += op.actual_flow_achieved * op.duration_minutes * 60
            else:
                delivered[zone] += op.expected_flow_after * op.duration_minutes * 60
        
        # Calculate remaining
        remaining_demands = {}
        for zone, demand in original_demands.get("byZone", {}).items():
            remaining = demand["total"] - delivered.get(zone, 0)
            if remaining > 0:
                remaining_demands[zone] = remaining
        
        return {
            "byZone": remaining_demands,
            "totalDemandM3": sum(remaining_demands.values()),
        }
    
    async def _get_network_data(self) -> Dict[str, Any]:
        """Get network topology"""
        
        gate_positions = await self.flow_client.get_gate_positions()
        canal_network = await self.gis_client.get_canal_network_topology()
        
        return {
            "gates": {
                gate_id: {
                    **canal_network.get("gates", {}).get(gate_id, {}),
                    "current_position": position,
                }
                for gate_id, position in gate_positions.items()
            },
            "canals": canal_network.get("canals", {}),
            "connections": canal_network.get("connections", []),
        }
    
    async def _get_available_teams(self, from_date: date) -> List[Dict]:
        """Get available teams"""
        
        result = await self.db.execute(
            select(FieldTeam).where(FieldTeam.is_active == True)
        )
        teams = result.scalars().all()
        
        return [
            {
                "team_code": team.team_code,
                "team_name": team.team_name,
                "max_operations_per_day": team.max_operations_per_day,
                "base_location_lat": team.base_location_lat,
                "base_location_lng": team.base_location_lng,
            }
            for team in teams
        ]
    
    async def _build_reoptimization_constraints(
        self,
        fixed_ops: List[ScheduledOperation],
        system_state: Dict[str, Any],
        user_constraints: Optional[Dict[str, Any]]
    ) -> List[Any]:
        """Build constraints for reoptimization"""
        
        constraints = []
        
        # Add fixed operation constraints
        for op in fixed_ops:
            constraints.append({
                "type": "fixed_operation",
                "gate_id": op.gate_id,
                "time": op.operation_date,
                "opening": op.target_opening_percent,
            })
        
        # Add current state constraints
        for gate_id, position in system_state["gate_positions"].items():
            constraints.append({
                "type": "initial_state",
                "gate_id": gate_id,
                "current_opening": position,
            })
        
        # Add user constraints
        if user_constraints:
            constraints.extend(user_constraints.get("additional_constraints", []))
        
        return constraints
    
    async def _run_reoptimization(
        self,
        demands: Dict[str, Any],
        network: Dict[str, Any],
        teams: List[Dict],
        constraints: List[Any],
        fixed_ops: List[ScheduledOperation],
        from_date: date
    ) -> Dict[str, Any]:
        """Run optimization with fixed operations"""
        
        # Prepare time horizon
        time_horizon = {
            "start_date": from_date,
            "end_date": from_date + timedelta(days=7),
            "operation_days": [1, 3],  # Tuesday, Thursday
        }
        
        # Run optimization
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            self.milp_optimizer.optimize,
            demands,
            network,
            teams,
            constraints,
            time_horizon
        )
        
        return result
    
    def _compare_schedules(
        self,
        old_ops: List[ScheduledOperation],
        new_ops: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Compare old and new schedules"""
        
        changes = []
        
        # Create lookup maps
        old_map = {
            f"{op.gate_id}_{op.operation_date}": op
            for op in old_ops
        }
        
        new_map = {
            f"{op['gate_id']}_{op['time_slot'].date()}": op
            for op in new_ops
        }
        
        # Find changes
        for key, new_op in new_map.items():
            if key in old_map:
                old_op = old_map[key]
                
                if (abs(old_op.target_opening_percent - new_op["target_opening"]) > 1 or
                    old_op.team_id != new_op.get("team_id")):
                    
                    changes.append({
                        "operation_id": str(old_op.id),
                        "type": "modified",
                        "old": {
                            "opening": old_op.target_opening_percent,
                            "team": old_op.team_id,
                        },
                        "new": {
                            "opening": new_op["target_opening"],
                            "team": new_op.get("team_id"),
                        },
                    })
            else:
                changes.append({
                    "type": "added",
                    "operation": new_op,
                })
        
        # Find removed operations
        for key, old_op in old_map.items():
            if key not in new_map:
                changes.append({
                    "operation_id": str(old_op.id),
                    "type": "removed",
                })
        
        return changes
    
    async def _apply_schedule_changes(
        self,
        schedule_id: UUID,
        changes: List[Dict[str, Any]]
    ):
        """Apply changes to the schedule"""
        
        for change in changes:
            if change["type"] == "modified":
                await self.db.execute(
                    update(ScheduledOperation)
                    .where(ScheduledOperation.id == change["operation_id"])
                    .values(
                        target_opening_percent=change["new"]["opening"],
                        team_id=change["new"]["team"],
                        notes="Reoptimized",
                    )
                )
            
            elif change["type"] == "removed":
                await self.db.execute(
                    update(ScheduledOperation)
                    .where(ScheduledOperation.id == change["operation_id"])
                    .values(
                        status="cancelled",
                        cancellation_reason="Removed during reoptimization",
                    )
                )
            
            elif change["type"] == "added":
                # Create new operation
                op_data = change["operation"]
                new_op = ScheduledOperation(
                    schedule_id=schedule_id,
                    gate_id=op_data["gate_id"],
                    operation_date=op_data["time_slot"].date(),
                    planned_start_time=op_data["time_slot"].time(),
                    target_opening_percent=op_data["target_opening"],
                    team_id=op_data.get("team_id"),
                    status="scheduled",
                    notes="Added during reoptimization",
                )
                self.db.add(new_op)
        
        await self.db.commit()
    
    async def _send_reoptimization_notifications(
        self,
        changes: List[Dict[str, Any]],
        reason: str
    ):
        """Send notifications about schedule changes"""
        
        # Group changes by team
        team_changes = {}
        for change in changes:
            if change["type"] == "modified":
                team_id = change["new"].get("team")
                if team_id:
                    if team_id not in team_changes:
                        team_changes[team_id] = []
                    team_changes[team_id].append(change)
        
        # Send team notifications
        for team_id, team_changes_list in team_changes.items():
            notification = {
                "type": "schedule_update",
                "team_id": team_id,
                "message": f"Schedule updated: {reason}",
                "changes_count": len(team_changes_list),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            await self.redis.publish(f"team_notifications:{team_id}", notification)
        
        # Send system notification
        system_notification = {
            "type": "reoptimization_complete",
            "reason": reason,
            "total_changes": len(changes),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        await self.redis.publish("system_alerts", system_notification)
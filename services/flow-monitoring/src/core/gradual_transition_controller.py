#!/usr/bin/env python3
"""
Gradual Transition Controller for Hydraulic Shock Prevention
Manages smooth transitions to prevent hydraulic shocks and maintain service continuity
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
from collections import deque

logger = logging.getLogger(__name__)


class TransitionStrategy(Enum):
    """Strategies for gate transitions"""
    LINEAR = "linear"  # Constant rate of change
    EXPONENTIAL = "exponential"  # Fast start, slow finish
    S_CURVE = "s_curve"  # Slow start, fast middle, slow finish
    ADAPTIVE = "adaptive"  # Adjusts based on system response


class HydraulicCondition(Enum):
    """Hydraulic system conditions"""
    STABLE = "stable"
    MINOR_OSCILLATION = "minor_oscillation"
    MAJOR_OSCILLATION = "major_oscillation"
    SHOCK_RISK = "shock_risk"
    SHOCK_DETECTED = "shock_detected"


@dataclass
class TransitionConstraints:
    """Constraints for safe transitions"""
    max_gate_speed_percent_per_sec: float = 5.0  # 5% per second max
    max_flow_change_m3s_per_min: float = 0.5  # 0.5 m³/s per minute
    max_level_change_m_per_min: float = 0.1  # 10cm per minute
    max_velocity_m_per_s: float = 2.0  # 2 m/s max velocity
    min_transition_time_s: float = 60.0  # Minimum 1 minute
    max_transition_time_s: float = 3600.0  # Maximum 1 hour
    oscillation_damping_factor: float = 0.5  # Reduce speed on oscillation
    emergency_stop_threshold: float = 0.3  # 30cm sudden level change


@dataclass
class GateTransitionPlan:
    """Plan for transitioning a single gate"""
    gate_id: str
    start_position: float
    target_position: float
    strategy: TransitionStrategy
    duration_s: float
    steps: List['TransitionStep'] = field(default_factory=list)
    constraints_applied: List[str] = field(default_factory=list)


@dataclass
class TransitionStep:
    """Single step in a transition plan"""
    step_number: int
    time_offset_s: float
    gate_position: float
    expected_flow: float
    max_allowed_speed: float
    hold_duration_s: float = 0.0
    notes: str = ""


@dataclass
class SystemTransitionPlan:
    """Coordinated transition plan for multiple gates"""
    plan_id: str
    created_at: datetime
    total_duration_s: float
    gate_plans: Dict[str, GateTransitionPlan]
    coordination_strategy: str
    safety_buffers: Dict[str, float]  # node_id -> buffer volume
    expected_impacts: Dict[str, any]


@dataclass
class TransitionMonitoringData:
    """Real-time monitoring during transition"""
    timestamp: datetime
    gate_positions: Dict[str, float]
    water_levels: Dict[str, float]
    flow_rates: Dict[str, float]
    velocities: Dict[str, float]
    hydraulic_condition: HydraulicCondition
    anomalies: List[str] = field(default_factory=list)


class GradualTransitionController:
    """
    Controls gradual transitions to prevent hydraulic shocks
    """
    
    def __init__(self, hydraulic_solver, gate_registry, constraints: Optional[TransitionConstraints] = None):
        """
        Initialize transition controller
        
        Args:
            hydraulic_solver: Enhanced hydraulic solver instance
            gate_registry: Gate registry for equipment limits
            constraints: Transition constraints
        """
        self.hydraulic_solver = hydraulic_solver
        self.gate_registry = gate_registry
        self.constraints = constraints or TransitionConstraints()
        
        # Monitoring state
        self._active_transitions: Dict[str, GateTransitionPlan] = {}
        self._monitoring_history: deque = deque(maxlen=1000)
        self._oscillation_detectors: Dict[str, deque] = {}
        
        # Initialize oscillation detectors for each node
        for node_id in hydraulic_solver.nodes:
            self._oscillation_detectors[node_id] = deque(maxlen=10)
        
        logger.info("Gradual transition controller initialized")
    
    async def create_transition_plan(
        self,
        gate_transitions: Dict[str, float],  # gate_id -> target_position
        target_duration_s: Optional[float] = None,
        strategy: TransitionStrategy = TransitionStrategy.S_CURVE,
        priority_zones: Optional[List[str]] = None
    ) -> SystemTransitionPlan:
        """
        Create a coordinated transition plan for multiple gates
        
        Args:
            gate_transitions: Target positions for each gate
            target_duration_s: Desired transition duration
            strategy: Transition strategy to use
            priority_zones: Zones requiring special protection
            
        Returns:
            SystemTransitionPlan with detailed steps
        """
        plan_id = f"TP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        gate_plans = {}
        
        # Analyze initial conditions
        initial_state = self.hydraulic_solver.current_state
        if not initial_state:
            raise ValueError("No current hydraulic state available")
        
        # Calculate required transition time for each gate
        transition_times = {}
        for gate_id, target_pos in gate_transitions.items():
            current_pos = initial_state.gate_openings.get(gate_id, 0)
            required_time = self._calculate_minimum_transition_time(
                gate_id, current_pos, target_pos
            )
            transition_times[gate_id] = required_time
        
        # Use longest required time if not specified
        if target_duration_s is None:
            target_duration_s = max(transition_times.values())
        else:
            # Ensure target duration meets minimum requirements
            min_required = max(transition_times.values())
            if target_duration_s < min_required:
                logger.warning(f"Requested duration {target_duration_s}s is less than "
                             f"minimum required {min_required}s. Using minimum.")
                target_duration_s = min_required
        
        # Apply maximum duration constraint
        target_duration_s = min(target_duration_s, self.constraints.max_transition_time_s)
        
        # Create individual gate plans
        for gate_id, target_pos in gate_transitions.items():
            current_pos = initial_state.gate_openings.get(gate_id, 0)
            
            gate_plan = await self._create_gate_transition_plan(
                gate_id, current_pos, target_pos, target_duration_s, strategy
            )
            gate_plans[gate_id] = gate_plan
        
        # Coordinate gate movements to prevent conflicts
        gate_plans = await self._coordinate_transitions(gate_plans, priority_zones)
        
        # Calculate safety buffers
        safety_buffers = await self._calculate_safety_buffers(gate_plans, priority_zones)
        
        # Predict system impacts
        expected_impacts = await self._predict_transition_impacts(gate_plans)
        
        return SystemTransitionPlan(
            plan_id=plan_id,
            created_at=datetime.now(),
            total_duration_s=target_duration_s,
            gate_plans=gate_plans,
            coordination_strategy="upstream_first" if priority_zones else "balanced",
            safety_buffers=safety_buffers,
            expected_impacts=expected_impacts
        )
    
    async def execute_transition_plan(
        self,
        plan: SystemTransitionPlan,
        monitoring_interval_s: float = 1.0
    ) -> Dict[str, any]:
        """
        Execute a transition plan with real-time monitoring
        
        Args:
            plan: Transition plan to execute
            monitoring_interval_s: How often to check system state
            
        Returns:
            Execution summary with results
        """
        logger.info(f"Starting execution of transition plan {plan.plan_id}")
        
        # Store active transitions
        for gate_id, gate_plan in plan.gate_plans.items():
            self._active_transitions[gate_id] = gate_plan
        
        start_time = datetime.now()
        execution_results = {
            "plan_id": plan.plan_id,
            "start_time": start_time,
            "completed": False,
            "emergency_stops": [],
            "anomalies": [],
            "final_positions": {}
        }
        
        try:
            # Execute transitions with monitoring
            await self._execute_with_monitoring(
                plan, monitoring_interval_s, execution_results
            )
            
            execution_results["completed"] = True
            execution_results["end_time"] = datetime.now()
            execution_results["duration_s"] = (datetime.now() - start_time).total_seconds()
            
        except Exception as e:
            logger.error(f"Transition execution failed: {e}")
            execution_results["error"] = str(e)
            
            # Emergency stop all gates
            await self._emergency_stop_all()
            
        finally:
            # Clear active transitions
            for gate_id in plan.gate_plans:
                self._active_transitions.pop(gate_id, None)
        
        return execution_results
    
    def _calculate_minimum_transition_time(
        self,
        gate_id: str,
        current_pos: float,
        target_pos: float
    ) -> float:
        """Calculate minimum safe transition time for a gate"""
        position_change = abs(target_pos - current_pos)
        
        # Get gate properties
        gate_props = self.hydraulic_solver.hydraulics.gate_properties.get(gate_id)
        if not gate_props:
            # Use conservative estimate
            height = 2.0  # meters
        else:
            height = gate_props.height_m
        
        # Convert to percentage change
        percent_change = (position_change / height) * 100
        
        # Calculate based on maximum speed constraint
        min_time_speed = percent_change / self.constraints.max_gate_speed_percent_per_sec
        
        # Calculate based on flow change constraint
        # Estimate flow change (simplified)
        estimated_flow_change = position_change * 2.0  # m³/s rough estimate
        min_time_flow = (estimated_flow_change / self.constraints.max_flow_change_m3s_per_min) * 60
        
        # Use the most conservative estimate
        min_time = max(
            min_time_speed,
            min_time_flow,
            self.constraints.min_transition_time_s
        )
        
        return min_time
    
    async def _create_gate_transition_plan(
        self,
        gate_id: str,
        start_pos: float,
        target_pos: float,
        duration_s: float,
        strategy: TransitionStrategy
    ) -> GateTransitionPlan:
        """Create transition plan for a single gate"""
        plan = GateTransitionPlan(
            gate_id=gate_id,
            start_position=start_pos,
            target_position=target_pos,
            strategy=strategy,
            duration_s=duration_s
        )
        
        # Generate transition steps based on strategy
        num_steps = max(int(duration_s / 10), 10)  # At least 10 steps
        
        for i in range(num_steps + 1):
            progress = i / num_steps
            time_offset = duration_s * progress
            
            # Calculate position based on strategy
            if strategy == TransitionStrategy.LINEAR:
                position_factor = progress
            elif strategy == TransitionStrategy.EXPONENTIAL:
                position_factor = 1 - np.exp(-3 * progress)
            elif strategy == TransitionStrategy.S_CURVE:
                # Sigmoid function
                position_factor = 1 / (1 + np.exp(-10 * (progress - 0.5)))
            else:  # ADAPTIVE
                position_factor = progress  # Will be adjusted in real-time
            
            position = start_pos + (target_pos - start_pos) * position_factor
            
            # Calculate allowed speed for this step
            if i > 0:
                prev_position = plan.steps[-1].gate_position
                time_delta = time_offset - plan.steps[-1].time_offset_s
                speed = abs(position - prev_position) / time_delta if time_delta > 0 else 0
                
                # Apply speed limit
                gate_height = self.hydraulic_solver.hydraulics.gate_properties.get(gate_id).height_m
                max_speed = (self.constraints.max_gate_speed_percent_per_sec / 100) * gate_height
                
                if speed > max_speed:
                    # Reduce position change to meet speed limit
                    max_change = max_speed * time_delta
                    if position > prev_position:
                        position = prev_position + max_change
                    else:
                        position = prev_position - max_change
                    plan.constraints_applied.append(f"Speed limit at step {i}")
            else:
                max_speed = self.constraints.max_gate_speed_percent_per_sec
            
            step = TransitionStep(
                step_number=i,
                time_offset_s=time_offset,
                gate_position=position,
                expected_flow=0,  # Will be calculated later
                max_allowed_speed=max_speed
            )
            
            plan.steps.append(step)
        
        # Calculate expected flows for each step
        await self._calculate_expected_flows(plan)
        
        return plan
    
    async def _calculate_expected_flows(self, plan: GateTransitionPlan):
        """Calculate expected flow rates for each transition step"""
        for step in plan.steps:
            # Simple estimation - would use hydraulic solver in production
            gate_props = self.hydraulic_solver.hydraulics.gate_properties.get(plan.gate_id)
            if gate_props:
                # Rough flow estimate
                step.expected_flow = step.gate_position * gate_props.width_m * 1.0  # Simplified
    
    async def _coordinate_transitions(
        self,
        gate_plans: Dict[str, GateTransitionPlan],
        priority_zones: Optional[List[str]] = None
    ) -> Dict[str, GateTransitionPlan]:
        """Coordinate multiple gate transitions to prevent conflicts"""
        
        # Identify gate dependencies based on hydraulic network
        dependencies = self._identify_gate_dependencies()
        
        # Apply coordination rules
        for gate_id, plan in gate_plans.items():
            # Rule 1: Upstream gates move first
            upstream_gates = dependencies.get(gate_id, {}).get("upstream", [])
            for upstream_id in upstream_gates:
                if upstream_id in gate_plans:
                    # Add delay to downstream gate
                    delay = 30.0  # 30 second delay
                    for step in plan.steps:
                        step.time_offset_s += delay
                    plan.constraints_applied.append(f"Delayed for upstream gate {upstream_id}")
            
            # Rule 2: Protect priority zones
            if priority_zones and self._affects_priority_zone(gate_id, priority_zones):
                # Slow down transitions affecting priority zones
                for i, step in enumerate(plan.steps):
                    if i > 0:
                        step.hold_duration_s = 5.0  # 5 second hold between steps
                plan.constraints_applied.append("Slowed for priority zone protection")
        
        return gate_plans
    
    def _identify_gate_dependencies(self) -> Dict[str, Dict[str, List[str]]]:
        """Identify hydraulic dependencies between gates"""
        dependencies = {}
        
        for gate_id, (upstream_node, downstream_node) in self.hydraulic_solver.gates.items():
            dependencies[gate_id] = {
                "upstream": [],
                "downstream": []
            }
            
            # Find upstream gates
            for other_id, (other_up, other_down) in self.hydraulic_solver.gates.items():
                if other_id != gate_id:
                    if other_down == upstream_node:
                        dependencies[gate_id]["upstream"].append(other_id)
                    elif other_up == downstream_node:
                        dependencies[gate_id]["downstream"].append(other_id)
        
        return dependencies
    
    def _affects_priority_zone(self, gate_id: str, priority_zones: List[str]) -> bool:
        """Check if gate affects priority zones"""
        # Simplified check - would trace actual flow paths in production
        if gate_id in self.hydraulic_solver.gates:
            _, downstream = self.hydraulic_solver.gates[gate_id]
            return any(zone in downstream for zone in priority_zones)
        return False
    
    async def _calculate_safety_buffers(
        self,
        gate_plans: Dict[str, GateTransitionPlan],
        priority_zones: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Calculate water buffers needed for safe transitions"""
        buffers = {}
        
        # For each node, calculate potential flow variations
        for node_id in self.hydraulic_solver.nodes:
            max_inflow_change = 0
            max_outflow_change = 0
            
            # Check all gates affecting this node
            for gate_id, (upstream, downstream) in self.hydraulic_solver.gates.items():
                if gate_id in gate_plans:
                    plan = gate_plans[gate_id]
                    flow_change = abs(plan.steps[-1].expected_flow - plan.steps[0].expected_flow)
                    
                    if downstream == node_id:
                        max_inflow_change += flow_change
                    elif upstream == node_id:
                        max_outflow_change += flow_change
            
            # Calculate required buffer (simplified)
            total_change = max_inflow_change + max_outflow_change
            if total_change > 0:
                # Buffer = flow change * transition time / 2
                buffer_volume = total_change * max(p.duration_s for p in gate_plans.values()) / 2
                buffers[node_id] = buffer_volume
        
        return buffers
    
    async def _predict_transition_impacts(
        self,
        gate_plans: Dict[str, GateTransitionPlan]
    ) -> Dict[str, any]:
        """Predict system impacts during transition"""
        impacts = {
            "max_velocity_change": 0,
            "max_level_change": 0,
            "affected_nodes": [],
            "flow_disruption_risk": "low",
            "estimated_stabilization_time": 0
        }
        
        # Run simplified prediction
        # In production, would run full hydraulic simulation
        
        # Estimate maximum changes
        total_flow_change = sum(
            abs(plan.steps[-1].expected_flow - plan.steps[0].expected_flow)
            for plan in gate_plans.values()
        )
        
        impacts["max_velocity_change"] = total_flow_change / 10  # Rough estimate
        impacts["max_level_change"] = total_flow_change / 100  # Rough estimate
        
        # Risk assessment
        if total_flow_change > 5.0:
            impacts["flow_disruption_risk"] = "high"
        elif total_flow_change > 2.0:
            impacts["flow_disruption_risk"] = "medium"
        
        # Stabilization time estimate
        max_duration = max(p.duration_s for p in gate_plans.values())
        impacts["estimated_stabilization_time"] = max_duration * 1.5
        
        return impacts
    
    async def _execute_with_monitoring(
        self,
        plan: SystemTransitionPlan,
        monitoring_interval_s: float,
        results: Dict
    ):
        """Execute transition plan with continuous monitoring"""
        start_time = datetime.now()
        last_monitoring = start_time
        
        # Create tasks for each gate
        gate_tasks = []
        for gate_id, gate_plan in plan.gate_plans.items():
            task = asyncio.create_task(
                self._execute_gate_transition(gate_id, gate_plan, results)
            )
            gate_tasks.append(task)
        
        # Monitor while gates are transitioning
        monitoring_task = asyncio.create_task(
            self._monitor_transition(plan, monitoring_interval_s, results)
        )
        
        # Wait for all gates to complete
        await asyncio.gather(*gate_tasks)
        
        # Stop monitoring
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"Transition plan {plan.plan_id} execution completed")
    
    async def _execute_gate_transition(
        self,
        gate_id: str,
        plan: GateTransitionPlan,
        results: Dict
    ):
        """Execute transition for a single gate"""
        logger.info(f"Starting transition for gate {gate_id}")
        
        start_time = datetime.now()
        
        try:
            for i, step in enumerate(plan.steps):
                # Wait for the right time
                elapsed = (datetime.now() - start_time).total_seconds()
                wait_time = step.time_offset_s - elapsed
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Check for emergency stop
                if gate_id not in self._active_transitions:
                    logger.warning(f"Gate {gate_id} transition cancelled")
                    break
                
                # Apply gate position
                self.hydraulic_solver.current_state.gate_openings[gate_id] = step.gate_position
                
                # Hold if required
                if step.hold_duration_s > 0:
                    await asyncio.sleep(step.hold_duration_s)
                
                logger.debug(f"Gate {gate_id} at position {step.gate_position:.2f}m "
                           f"(step {i+1}/{len(plan.steps)})")
            
            results["final_positions"][gate_id] = plan.target_position
            logger.info(f"Gate {gate_id} transition completed")
            
        except Exception as e:
            logger.error(f"Error during gate {gate_id} transition: {e}")
            results["anomalies"].append({
                "gate_id": gate_id,
                "error": str(e),
                "timestamp": datetime.now()
            })
    
    async def _monitor_transition(
        self,
        plan: SystemTransitionPlan,
        interval_s: float,
        results: Dict
    ):
        """Monitor system during transition"""
        logger.info("Starting transition monitoring")
        
        try:
            while True:
                # Get current system state
                monitoring_data = await self._collect_monitoring_data()
                
                # Store in history
                self._monitoring_history.append(monitoring_data)
                
                # Check for anomalies
                anomalies = self._detect_anomalies(monitoring_data)
                if anomalies:
                    monitoring_data.anomalies.extend(anomalies)
                    results["anomalies"].extend(anomalies)
                
                # Check hydraulic condition
                condition = self._assess_hydraulic_condition(monitoring_data)
                monitoring_data.hydraulic_condition = condition
                
                # Take action based on condition
                if condition == HydraulicCondition.SHOCK_DETECTED:
                    logger.critical("Hydraulic shock detected! Emergency stop initiated")
                    await self._emergency_stop_all()
                    results["emergency_stops"].append({
                        "reason": "Hydraulic shock detected",
                        "timestamp": datetime.now(),
                        "monitoring_data": monitoring_data
                    })
                    break
                elif condition == HydraulicCondition.SHOCK_RISK:
                    logger.warning("Shock risk detected - slowing transitions")
                    await self._slow_all_transitions()
                elif condition == HydraulicCondition.MAJOR_OSCILLATION:
                    logger.warning("Major oscillations detected - damping applied")
                    await self._apply_oscillation_damping()
                
                await asyncio.sleep(interval_s)
                
        except asyncio.CancelledError:
            logger.info("Transition monitoring stopped")
    
    async def _collect_monitoring_data(self) -> TransitionMonitoringData:
        """Collect current system monitoring data"""
        state = self.hydraulic_solver.current_state
        
        # Calculate velocities (simplified)
        velocities = {}
        for section_id, flow in state.canal_flows.items():
            # Rough velocity estimate
            velocities[section_id] = abs(flow) / 5.0  # Assuming 5m² area
        
        return TransitionMonitoringData(
            timestamp=datetime.now(),
            gate_positions=state.gate_openings.copy(),
            water_levels=state.water_levels.copy(),
            flow_rates=state.gate_flows.copy(),
            velocities=velocities,
            hydraulic_condition=HydraulicCondition.STABLE
        )
    
    def _detect_anomalies(self, data: TransitionMonitoringData) -> List[str]:
        """Detect anomalies in monitoring data"""
        anomalies = []
        
        # Check for sudden level changes
        for node_id, level in data.water_levels.items():
            history = self._oscillation_detectors[node_id]
            history.append(level)
            
            if len(history) > 1:
                change = abs(level - history[-2])
                if change > self.constraints.emergency_stop_threshold:
                    anomalies.append(f"Sudden level change at {node_id}: {change:.2f}m")
        
        # Check for high velocities
        for section_id, velocity in data.velocities.items():
            if velocity > self.constraints.max_velocity_m_per_s:
                anomalies.append(f"High velocity in {section_id}: {velocity:.1f} m/s")
        
        return anomalies
    
    def _assess_hydraulic_condition(self, data: TransitionMonitoringData) -> HydraulicCondition:
        """Assess overall hydraulic condition"""
        # Check for oscillations
        oscillation_score = 0
        
        for node_id, history in self._oscillation_detectors.items():
            if len(history) >= 3:
                # Check for alternating changes (oscillation pattern)
                changes = [history[i] - history[i-1] for i in range(1, len(history))]
                sign_changes = sum(1 for i in range(1, len(changes)) 
                                 if np.sign(changes[i]) != np.sign(changes[i-1]))
                
                if sign_changes >= 2:
                    oscillation_score += 1
        
        # Determine condition
        if any("Sudden level change" in a for a in data.anomalies):
            return HydraulicCondition.SHOCK_DETECTED
        elif any(v > self.constraints.max_velocity_m_per_s * 0.9 for v in data.velocities.values()):
            return HydraulicCondition.SHOCK_RISK
        elif oscillation_score > len(self._oscillation_detectors) * 0.3:
            return HydraulicCondition.MAJOR_OSCILLATION
        elif oscillation_score > 0:
            return HydraulicCondition.MINOR_OSCILLATION
        else:
            return HydraulicCondition.STABLE
    
    async def _emergency_stop_all(self):
        """Emergency stop all active transitions"""
        logger.critical("EMERGENCY STOP - Halting all gate movements")
        self._active_transitions.clear()
        # In production, would also send stop commands to SCADA
    
    async def _slow_all_transitions(self):
        """Slow down all active transitions"""
        damping = 0.5
        for gate_id, plan in self._active_transitions.items():
            # Increase time offsets for remaining steps
            for step in plan.steps:
                if step.time_offset_s > (datetime.now() - plan.created_at).total_seconds():
                    step.time_offset_s *= (1 + damping)
    
    async def _apply_oscillation_damping(self):
        """Apply damping to reduce oscillations"""
        damping = self.constraints.oscillation_damping_factor
        for gate_id, plan in self._active_transitions.items():
            # Add holds between steps
            for step in plan.steps:
                step.hold_duration_s = max(step.hold_duration_s, 5.0)
    
    def get_active_transitions(self) -> Dict[str, GateTransitionPlan]:
        """Get currently active transitions"""
        return self._active_transitions.copy()
    
    def get_monitoring_history(self, duration_s: float = 300) -> List[TransitionMonitoringData]:
        """Get recent monitoring history"""
        cutoff_time = datetime.now() - timedelta(seconds=duration_s)
        return [data for data in self._monitoring_history 
                if data.timestamp > cutoff_time]
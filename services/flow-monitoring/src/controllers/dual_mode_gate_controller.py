"""
Dual-Mode Gate Controller for Munbon Irrigation System
Supports both automated (SCADA) and manual gate operations with seamless transitions
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
import structlog
import numpy as np

from ..schemas.gate_control import (
    GateMode, GateType, ControlStatus, GateState, GateStateResponse,
    ManualInstruction, GateTransitionValidation, SynchronizationStatus
)
from ..hydraulic_solver import HydraulicSolver
from ..calibrated_gate_flow import CalibratedGateFlow
from ..db.connections import DatabaseManager
from ..db.influxdb_client import InfluxDBClient
from ..db.timescale_client import TimescaleClient
from ..db.redis_client import RedisClient
from ..core.metrics import (
    gate_operations_counter, gate_mode_gauge, 
    gate_opening_gauge, hydraulic_solver_iterations
)

logger = structlog.get_logger()


class DualModeGateController:
    """
    Unified controller for automated and manual gate operations.
    Ensures coordination between SCADA-controlled and manually-operated gates.
    """
    
    def __init__(self, db_manager: DatabaseManager, network_file: str, geometry_file: str):
        """Initialize dual-mode controller"""
        self.db_manager = db_manager
        self.hydraulic_solver = HydraulicSolver(network_file, geometry_file)
        self.gate_flow_calculator = CalibratedGateFlow()
        
        # Gate state tracking
        self.gate_states: Dict[str, GateState] = {}
        self.gate_properties: Dict[str, Dict[str, Any]] = {}
        self.mode_transition_locks: Dict[str, asyncio.Lock] = {}
        
        # Control parameters
        self.manual_update_interval = timedelta(minutes=15)  # Expected manual update frequency
        self.automated_control_period = 1.0  # seconds
        self.transition_timeout = 300  # seconds
        
        # Synchronization tracking
        self.last_sync_time = datetime.utcnow()
        self.sync_conflicts: List[Dict[str, Any]] = []
        
        # Initialize from network
        self._load_gate_configuration()
    
    def _load_gate_configuration(self):
        """Load gate configuration from network files"""
        try:
            # Get gates from hydraulic solver
            for gate_id, props in self.hydraulic_solver.gate_properties.items():
                self.gate_properties[gate_id] = {
                    "type": props.gate_type,
                    "width": props.width,
                    "height": props.height,
                    "calibration": {
                        "K1": props.K1,
                        "K2": props.K2
                    },
                    "location": {
                        "upstream_node": self.hydraulic_solver.gates[gate_id][0],
                        "downstream_node": self.hydraulic_solver.gates[gate_id][1]
                    }
                }
                
                # Initialize gate state
                self.gate_states[gate_id] = GateState(
                    gate_id=gate_id,
                    mode=self._determine_initial_mode(gate_id),
                    control_status=ControlStatus.STANDBY,
                    opening_percentage=0.0,
                    last_updated=datetime.utcnow()
                )
                
                # Create lock for mode transitions
                self.mode_transition_locks[gate_id] = asyncio.Lock()
                
                # Set metrics
                gate_mode_gauge.labels(gate_id=gate_id).set(
                    1 if self.gate_states[gate_id].mode == GateMode.AUTOMATED else 0
                )
                
            logger.info(f"Loaded {len(self.gate_properties)} gates from network")
            
        except Exception as e:
            logger.error(f"Failed to load gate configuration: {e}")
            raise
    
    def _determine_initial_mode(self, gate_id: str) -> GateMode:
        """Determine initial operational mode for a gate"""
        # Gates with specific prefixes are automated
        automated_prefixes = ["HG-C", "CHK", "RG"]
        
        for prefix in automated_prefixes:
            if gate_id.startswith(prefix):
                return GateMode.AUTOMATED
        
        return GateMode.MANUAL
    
    async def get_all_gate_states(self) -> Dict[str, GateStateResponse]:
        """Get current state of all gates"""
        states = {}
        
        for gate_id, state in self.gate_states.items():
            # Get latest measurements
            measurements = await self._get_gate_measurements(gate_id)
            
            # Update state with measurements
            state.flow_rate = measurements.get("flow_rate")
            state.upstream_level = measurements.get("upstream_level")
            state.downstream_level = measurements.get("downstream_level")
            
            # Create response
            states[gate_id] = GateStateResponse(
                **state.dict(),
                gate_type=GateType(self.gate_properties[gate_id]["type"]),
                location=self.gate_properties[gate_id]["location"],
                calibration_params=self.gate_properties[gate_id]["calibration"],
                operational_constraints=await self._get_operational_constraints(gate_id)
            )
        
        return states
    
    async def get_gate_state(self, gate_id: str) -> Optional[GateStateResponse]:
        """Get state of a specific gate"""
        if gate_id not in self.gate_states:
            return None
        
        state = self.gate_states[gate_id]
        measurements = await self._get_gate_measurements(gate_id)
        
        state.flow_rate = measurements.get("flow_rate")
        state.upstream_level = measurements.get("upstream_level")
        state.downstream_level = measurements.get("downstream_level")
        
        return GateStateResponse(
            **state.dict(),
            gate_type=GateType(self.gate_properties[gate_id]["type"]),
            location=self.gate_properties[gate_id]["location"],
            calibration_params=self.gate_properties[gate_id]["calibration"],
            operational_constraints=await self._get_operational_constraints(gate_id)
        )
    
    async def update_manual_gate_state(
        self, 
        gate_id: str, 
        opening_percentage: float,
        operator_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Update state of a manually operated gate"""
        try:
            if gate_id not in self.gate_states:
                logger.error(f"Unknown gate: {gate_id}")
                return False
            
            state = self.gate_states[gate_id]
            
            # Record previous state
            previous_opening = state.opening_percentage
            
            # Update state
            state.opening_percentage = opening_percentage
            state.last_updated = datetime.utcnow()
            state.last_command_time = datetime.utcnow()
            
            # Calculate flow with new opening
            measurements = await self._get_gate_measurements(gate_id)
            if measurements.get("upstream_level") and measurements.get("downstream_level"):
                flow = self.gate_flow_calculator.calculate_gate_flow(
                    gate_id=gate_id,
                    gate_properties=self.gate_properties[gate_id],
                    upstream_level=measurements["upstream_level"],
                    downstream_level=measurements["downstream_level"],
                    gate_opening=opening_percentage / 100.0 * self.gate_properties[gate_id]["height"]
                )
                state.flow_rate = flow
            
            # Store update in database
            await self._store_gate_update(
                gate_id=gate_id,
                opening=opening_percentage,
                mode="manual",
                operator_id=operator_id,
                notes=notes,
                previous_opening=previous_opening
            )
            
            # Update metrics
            gate_opening_gauge.labels(gate_id=gate_id).set(opening_percentage)
            
            # Check for conflicts with automated gates
            await self._check_synchronization_conflicts()
            
            logger.info(
                f"Manual gate {gate_id} updated: {previous_opening}% -> {opening_percentage}%",
                operator=operator_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update manual gate {gate_id}: {e}")
            return False
    
    async def validate_mode_transition(
        self,
        gate_id: str,
        target_mode: GateMode,
        force: bool = False
    ) -> GateTransitionValidation:
        """Validate if mode transition is safe"""
        if gate_id not in self.gate_states:
            return GateTransitionValidation(
                is_valid=False,
                current_mode=GateMode.MANUAL,
                target_mode=target_mode,
                reason="Unknown gate"
            )
        
        current_state = self.gate_states[gate_id]
        validation = GateTransitionValidation(
            is_valid=True,
            current_mode=current_state.mode,
            target_mode=target_mode,
            warnings=[],
            recommendations=[]
        )
        
        # Check if already in target mode
        if current_state.mode == target_mode:
            validation.reason = "Already in target mode"
            return validation
        
        # Validate specific transitions
        if target_mode == GateMode.AUTOMATED:
            # Check SCADA connectivity
            if not await self._check_scada_connectivity(gate_id):
                validation.warnings.append("SCADA connectivity not confirmed")
                validation.recommendations.append("Verify SCADA communication before transition")
                if not force:
                    validation.is_valid = False
                    validation.reason = "SCADA connectivity required"
            
            # Check if gate is at a safe position
            if abs(current_state.opening_percentage - 0) > 5 and abs(current_state.opening_percentage - 100) > 5:
                validation.warnings.append(f"Gate at intermediate position ({current_state.opening_percentage}%)")
                validation.recommendations.append("Consider moving gate to fully open or closed before automation")
        
        elif target_mode == GateMode.MANUAL:
            # Check if there are active control commands
            if current_state.control_status == ControlStatus.ACTIVE:
                validation.warnings.append("Active control commands in progress")
                validation.recommendations.append("Wait for current commands to complete")
                if not force:
                    validation.is_valid = False
                    validation.reason = "Active automation in progress"
        
        # Estimate hydraulic impact
        impact = await self._estimate_transition_impact(gate_id, target_mode)
        validation.estimated_impact = impact
        
        if impact.get("flow_change", 0) > 0.5:  # More than 0.5 m³/s change
            validation.warnings.append(f"Significant flow change expected: {impact['flow_change']:.2f} m³/s")
            validation.recommendations.append("Coordinate with downstream users")
        
        return validation
    
    async def execute_mode_transition(
        self,
        gate_id: str,
        target_mode: GateMode,
        transition_time: Optional[int] = None
    ) -> bool:
        """Execute mode transition for a gate"""
        async with self.mode_transition_locks[gate_id]:
            try:
                current_state = self.gate_states[gate_id]
                
                # Update status to transitioning
                current_state.control_status = ControlStatus.TRANSITIONING
                
                # Perform transition procedures
                if target_mode == GateMode.AUTOMATED:
                    success = await self._transition_to_automated(gate_id, transition_time)
                elif target_mode == GateMode.MANUAL:
                    success = await self._transition_to_manual(gate_id, transition_time)
                elif target_mode == GateMode.HYBRID:
                    success = await self._transition_to_hybrid(gate_id, transition_time)
                else:
                    logger.error(f"Unknown target mode: {target_mode}")
                    success = False
                
                if success:
                    current_state.mode = target_mode
                    current_state.control_status = ControlStatus.STANDBY
                    gate_mode_gauge.labels(gate_id=gate_id).set(
                        1 if target_mode == GateMode.AUTOMATED else 0
                    )
                    logger.info(f"Gate {gate_id} transitioned to {target_mode} mode")
                else:
                    current_state.control_status = ControlStatus.FAULT
                    current_state.error_state = "Mode transition failed"
                
                return success
                
            except Exception as e:
                logger.error(f"Mode transition failed for gate {gate_id}: {e}")
                current_state.control_status = ControlStatus.FAULT
                current_state.error_state = str(e)
                return False
    
    async def generate_manual_instructions(self) -> List[ManualInstruction]:
        """Generate instructions for manual gate operations"""
        instructions = []
        
        try:
            # Get current system demand
            system_demand = await self._get_system_demand()
            
            # Run hydraulic solver to get optimal gate settings
            optimal_settings = await self._solve_optimal_gate_settings(system_demand)
            
            # Generate instructions for manual gates
            for gate_id, state in self.gate_states.items():
                if state.mode != GateMode.MANUAL:
                    continue
                
                optimal_opening = optimal_settings.get(gate_id, {}).get("opening", state.opening_percentage)
                
                # Only generate instruction if change is significant (>5%)
                if abs(optimal_opening - state.opening_percentage) > 5:
                    instruction = ManualInstruction(
                        gate_id=gate_id,
                        current_opening=state.opening_percentage,
                        target_opening=optimal_opening,
                        priority=abs(optimal_opening - state.opening_percentage) > 20,
                        reason=self._generate_instruction_reason(gate_id, optimal_opening, state.opening_percentage),
                        estimated_flow_change=await self._estimate_flow_change(gate_id, optimal_opening),
                        safety_checks=self._generate_safety_checks(gate_id, optimal_opening)
                    )
                    
                    # Add coordination notes if needed
                    coordination = await self._check_coordination_requirements(gate_id)
                    if coordination:
                        instruction.coordination_notes = coordination
                    
                    instructions.append(instruction)
            
            # Sort by priority and impact
            instructions.sort(key=lambda x: (not x.priority, abs(x.estimated_flow_change or 0)), reverse=True)
            
            logger.info(f"Generated {len(instructions)} manual instructions")
            return instructions
            
        except Exception as e:
            logger.error(f"Failed to generate manual instructions: {e}")
            return []
    
    async def get_synchronization_status(self) -> SynchronizationStatus:
        """Get synchronization status between automated and manual operations"""
        automated_gates = []
        manual_gates = []
        hybrid_gates = []
        
        for gate_id, state in self.gate_states.items():
            if state.mode == GateMode.AUTOMATED:
                automated_gates.append(gate_id)
            elif state.mode == GateMode.MANUAL:
                manual_gates.append(gate_id)
            elif state.mode == GateMode.HYBRID:
                hybrid_gates.append(gate_id)
        
        # Calculate sync quality
        sync_quality = await self._calculate_sync_quality()
        
        return SynchronizationStatus(
            is_synchronized=len(self.sync_conflicts) == 0,
            last_sync_time=self.last_sync_time,
            automated_gates=automated_gates,
            manual_gates=manual_gates,
            hybrid_gates=hybrid_gates,
            conflicts=self.sync_conflicts,
            warnings=await self._generate_sync_warnings(),
            sync_quality=sync_quality
        )
    
    # Helper methods
    
    async def _get_gate_measurements(self, gate_id: str) -> Dict[str, float]:
        """Get current measurements for a gate"""
        try:
            # Get from InfluxDB
            influx = self.db_manager.influxdb
            
            # Query for latest measurements
            query = f'''
            from(bucket: "{influx.bucket}")
                |> range(start: -5m)
                |> filter(fn: (r) => r["gate_id"] == "{gate_id}")
                |> last()
            '''
            
            measurements = {}
            # Parse results (simplified for brevity)
            # In real implementation, properly parse InfluxDB results
            
            return measurements
        except Exception as e:
            logger.error(f"Failed to get gate measurements: {e}")
            return {}
    
    async def _get_operational_constraints(self, gate_id: str) -> Dict[str, Any]:
        """Get operational constraints for a gate"""
        # In real implementation, fetch from database
        return {
            "max_flow_rate": 10.0,  # m³/s
            "max_opening_speed": 0.5,  # %/s
            "maintenance_schedule": None,
            "operational_hours": "24/7"
        }
    
    async def _store_gate_update(self, **kwargs):
        """Store gate update in database"""
        try:
            # Store in TimescaleDB for historical tracking
            timescale = self.db_manager.timescale
            await timescale.execute(
                """
                INSERT INTO gate_operations 
                (gate_id, opening, mode, operator_id, notes, previous_opening, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                kwargs['gate_id'], kwargs['opening'], kwargs['mode'],
                kwargs.get('operator_id'), kwargs.get('notes'), 
                kwargs.get('previous_opening'), datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to store gate update: {e}")
    
    async def _check_synchronization_conflicts(self):
        """Check for conflicts between automated and manual operations"""
        # Implementation would check for hydraulic conflicts
        # For now, clear conflicts
        self.sync_conflicts = []
        self.last_sync_time = datetime.utcnow()
    
    async def _check_scada_connectivity(self, gate_id: str) -> bool:
        """Check if SCADA connection is available for gate"""
        # In real implementation, check actual SCADA status
        # For now, return True for automated gates
        return gate_id.startswith(("HG-C", "CHK", "RG"))
    
    async def _estimate_transition_impact(self, gate_id: str, target_mode: GateMode) -> Dict[str, Any]:
        """Estimate hydraulic impact of mode transition"""
        # Simplified estimation
        current_state = self.gate_states[gate_id]
        
        return {
            "flow_change": 0.3 if target_mode == GateMode.MANUAL else 0.1,
            "affected_downstream": 2,
            "stabilization_time": 300  # seconds
        }
    
    async def _transition_to_automated(self, gate_id: str, transition_time: Optional[int]) -> bool:
        """Transition gate to automated mode"""
        try:
            # Initialize SCADA connection
            # Synchronize current position
            # Enable automated control
            await asyncio.sleep(1)  # Simulate transition
            return True
        except Exception as e:
            logger.error(f"Failed to transition to automated: {e}")
            return False
    
    async def _transition_to_manual(self, gate_id: str, transition_time: Optional[int]) -> bool:
        """Transition gate to manual mode"""
        try:
            # Disable automated control
            # Notify operators
            # Lock current position
            await asyncio.sleep(1)  # Simulate transition
            return True
        except Exception as e:
            logger.error(f"Failed to transition to manual: {e}")
            return False
    
    async def _transition_to_hybrid(self, gate_id: str, transition_time: Optional[int]) -> bool:
        """Transition gate to hybrid mode"""
        # Hybrid mode allows both manual and automated control with coordination
        try:
            await asyncio.sleep(1)  # Simulate transition
            return True
        except Exception as e:
            logger.error(f"Failed to transition to hybrid: {e}")
            return False
    
    async def _get_system_demand(self) -> Dict[str, float]:
        """Get current system water demand"""
        # In real implementation, aggregate from irrigation schedules
        return {"total_demand": 25.0}  # m³/s
    
    async def _solve_optimal_gate_settings(self, demand: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """Solve for optimal gate settings given demand"""
        # Use hydraulic solver
        # For now, return dummy settings
        settings = {}
        for gate_id in self.gate_states:
            settings[gate_id] = {"opening": 50.0}  # 50% opening
        return settings
    
    def _generate_instruction_reason(self, gate_id: str, target: float, current: float) -> str:
        """Generate reason for gate adjustment"""
        if target > current:
            return f"Increase flow to meet downstream demand"
        else:
            return f"Reduce flow to prevent oversupply"
    
    async def _estimate_flow_change(self, gate_id: str, new_opening: float) -> float:
        """Estimate flow change from gate adjustment"""
        # Simplified calculation
        current = self.gate_states[gate_id].flow_rate or 0
        # Assume linear relationship for simplicity
        new_flow = current * (new_opening / max(self.gate_states[gate_id].opening_percentage, 1))
        return new_flow - current
    
    def _generate_safety_checks(self, gate_id: str, target_opening: float) -> List[str]:
        """Generate safety checks for gate operation"""
        checks = [
            "Verify no personnel near gate",
            "Check upstream water level",
            "Confirm downstream channel capacity"
        ]
        
        if target_opening > 80:
            checks.append("Alert downstream users of increased flow")
        elif target_opening < 20:
            checks.append("Verify minimum flow requirements")
        
        return checks
    
    async def _check_coordination_requirements(self, gate_id: str) -> Optional[str]:
        """Check if coordination with other gates is required"""
        # Check for gates on same channel
        props = self.gate_properties[gate_id]
        downstream_node = props["location"]["downstream_node"]
        
        # Find other gates affecting same node
        coordinated_gates = []
        for other_id, other_props in self.gate_properties.items():
            if other_id != gate_id:
                if (other_props["location"]["upstream_node"] == downstream_node or
                    other_props["location"]["downstream_node"] == downstream_node):
                    coordinated_gates.append(other_id)
        
        if coordinated_gates:
            return f"Coordinate with gates: {', '.join(coordinated_gates)}"
        
        return None
    
    async def _calculate_sync_quality(self) -> float:
        """Calculate synchronization quality metric"""
        # Based on:
        # - Time since last sync
        # - Number of conflicts
        # - Manual gate update frequency
        
        quality = 1.0
        
        # Reduce for conflicts
        quality -= len(self.sync_conflicts) * 0.1
        
        # Reduce for stale sync
        time_since_sync = (datetime.utcnow() - self.last_sync_time).total_seconds()
        if time_since_sync > 3600:  # More than 1 hour
            quality -= 0.2
        
        return max(0.0, min(1.0, quality))
    
    async def _generate_sync_warnings(self) -> List[str]:
        """Generate synchronization warnings"""
        warnings = []
        
        # Check for stale manual updates
        for gate_id, state in self.gate_states.items():
            if state.mode == GateMode.MANUAL:
                if state.last_updated and (datetime.utcnow() - state.last_updated) > self.manual_update_interval * 2:
                    warnings.append(f"Manual gate {gate_id} not updated for {(datetime.utcnow() - state.last_updated).total_seconds() / 3600:.1f} hours")
        
        return warnings
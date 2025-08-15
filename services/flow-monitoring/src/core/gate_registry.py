#!/usr/bin/env python3
"""
Gate Registry Module for Munbon Irrigation Network
Manages gate classification (auto/manual) and equipment status
"""

import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ControlMode(Enum):
    """Gate control modes"""
    AUTO = "auto"
    MANUAL = "manual"
    TRANSITIONING = "transitioning"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


class EquipmentStatus(Enum):
    """Equipment health status"""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ActuatorType(Enum):
    """Types of gate actuators"""
    ELECTRIC = "electric"
    HYDRAULIC = "hydraulic"
    PNEUMATIC = "pneumatic"
    MANUAL_WHEEL = "manual_wheel"
    MANUAL_LEVER = "manual_lever"


@dataclass
class ControlEquipment:
    """Equipment details for automated gates"""
    actuator_type: ActuatorType
    position_sensor: str  # encoder, potentiometer, limit_switches
    communication_protocol: str  # modbus_tcp, modbus_rtu, profinet
    ip_address: Optional[str] = None
    plc_address: Optional[str] = None
    response_time_ms: int = 5000
    max_speed_percent_per_sec: float = 5.0  # Max movement speed


@dataclass
class ManualOperationDetails:
    """Details for manual gate operation"""
    operation_method: str  # handwheel, lever, chain
    turns_to_open: Optional[int] = None
    force_required: str = "normal"  # light, normal, heavy
    access_road: Optional[str] = None
    gps_coordinates: Optional[Dict[str, float]] = None
    special_tools_required: bool = False
    safety_notes: Optional[str] = None


@dataclass
class MaintenanceSchedule:
    """Maintenance scheduling information"""
    frequency: str  # daily, weekly, monthly, quarterly, annual
    last_maintenance: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None
    maintenance_team: Optional[str] = None
    typical_duration_hours: float = 2.0


@dataclass
class AutomatedGate:
    """Configuration for automated gates"""
    gate_id: str
    location: str
    control_mode: ControlMode
    scada_tag: str
    control_equipment: ControlEquipment
    equipment_status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    fallback_mode: ControlMode = ControlMode.MANUAL
    maintenance_schedule: Optional[MaintenanceSchedule] = None
    last_communication: Optional[datetime] = None
    consecutive_failures: int = 0
    notes: str = ""


@dataclass
class ManualGate:
    """Configuration for manual gates"""
    gate_id: str
    location: str
    operation_details: ManualOperationDetails
    field_team_zone: str
    control_mode: ControlMode = ControlMode.MANUAL
    last_operation: Optional[datetime] = None
    typical_operation_time_min: int = 30
    notes: str = ""


@dataclass
class ModeTransitionRule:
    """Rules for automatic mode transitions"""
    trigger: str  # communication_timeout, sensor_fault, etc.
    from_mode: ControlMode
    to_mode: ControlMode
    condition: Dict[str, any] = field(default_factory=dict)
    priority: int = 1
    notification_required: bool = True


class GateRegistry:
    """Central registry for all gates in the irrigation network"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.automated_gates: Dict[str, AutomatedGate] = {}
        self.manual_gates: Dict[str, ManualGate] = {}
        self.transition_rules: List[ModeTransitionRule] = []
        
        # Quick lookup indices
        self._gate_to_mode: Dict[str, ControlMode] = {}
        self._location_to_gate: Dict[str, str] = {}
        self._scada_tag_to_gate: Dict[str, str] = {}
        
        # Initialize default transition rules
        self._init_default_transition_rules()
        
        # Load from config if provided
        if config_file:
            self.load_from_file(config_file)
    
    def _init_default_transition_rules(self):
        """Initialize default mode transition rules"""
        self.transition_rules = [
            # Communication failures
            ModeTransitionRule(
                trigger="communication_timeout",
                from_mode=ControlMode.AUTO,
                to_mode=ControlMode.MANUAL,
                condition={"timeout_seconds": 30, "consecutive_failures": 3},
                priority=1
            ),
            # Sensor failures
            ModeTransitionRule(
                trigger="position_sensor_fault",
                from_mode=ControlMode.AUTO,
                to_mode=ControlMode.MANUAL,
                condition={"sensor_reading": "invalid"},
                priority=1
            ),
            # Actuator failures
            ModeTransitionRule(
                trigger="actuator_fault",
                from_mode=ControlMode.AUTO,
                to_mode=ControlMode.FAILED,
                condition={"movement_detected": False, "command_sent": True},
                priority=2
            ),
            # Maintenance mode
            ModeTransitionRule(
                trigger="scheduled_maintenance",
                from_mode=ControlMode.AUTO,
                to_mode=ControlMode.MAINTENANCE,
                condition={"maintenance_window": True},
                priority=3
            ),
            # Recovery conditions
            ModeTransitionRule(
                trigger="fault_cleared",
                from_mode=ControlMode.MANUAL,
                to_mode=ControlMode.AUTO,
                condition={"all_checks_passed": True, "operator_approved": True},
                priority=1,
                notification_required=True
            ),
        ]
    
    def register_automated_gate(self, gate: AutomatedGate):
        """Register an automated gate"""
        self.automated_gates[gate.gate_id] = gate
        self._gate_to_mode[gate.gate_id] = gate.control_mode
        self._location_to_gate[gate.location] = gate.gate_id
        self._scada_tag_to_gate[gate.scada_tag] = gate.gate_id
        logger.info(f"Registered automated gate {gate.gate_id} at {gate.location}")
    
    def register_manual_gate(self, gate: ManualGate):
        """Register a manual gate"""
        self.manual_gates[gate.gate_id] = gate
        self._gate_to_mode[gate.gate_id] = gate.control_mode
        self._location_to_gate[gate.location] = gate.gate_id
        logger.info(f"Registered manual gate {gate.gate_id} at {gate.location}")
    
    def get_gate_mode(self, gate_id: str) -> Optional[ControlMode]:
        """Get current control mode for a gate"""
        return self._gate_to_mode.get(gate_id)
    
    def is_automated(self, gate_id: str) -> bool:
        """Check if gate has automation capability"""
        return gate_id in self.automated_gates
    
    def get_gate_by_location(self, location: str) -> Optional[str]:
        """Find gate ID by location string"""
        return self._location_to_gate.get(location)
    
    def get_gate_by_scada_tag(self, scada_tag: str) -> Optional[str]:
        """Find gate ID by SCADA tag"""
        return self._scada_tag_to_gate.get(scada_tag)
    
    def get_automated_gates_list(self) -> List[str]:
        """Get list of all automated gate IDs"""
        return list(self.automated_gates.keys())
    
    def get_manual_gates_list(self) -> List[str]:
        """Get list of all manual gate IDs"""
        return list(self.manual_gates.keys())
    
    def get_gates_by_mode(self, mode: ControlMode) -> List[str]:
        """Get all gates currently in specified mode"""
        gates = []
        for gate_id, gate_mode in self._gate_to_mode.items():
            if gate_mode == mode:
                gates.append(gate_id)
        return gates
    
    def get_gates_by_team_zone(self, team_zone: str) -> List[str]:
        """Get manual gates assigned to a specific field team zone"""
        gates = []
        for gate_id, gate in self.manual_gates.items():
            if gate.field_team_zone == team_zone:
                gates.append(gate_id)
        return gates
    
    def update_gate_mode(self, gate_id: str, new_mode: ControlMode, reason: str = ""):
        """Update control mode for a gate"""
        if gate_id in self.automated_gates:
            old_mode = self.automated_gates[gate_id].control_mode
            self.automated_gates[gate_id].control_mode = new_mode
            self._gate_to_mode[gate_id] = new_mode
            logger.info(f"Gate {gate_id} mode changed from {old_mode.value} to {new_mode.value}: {reason}")
        elif gate_id in self.manual_gates:
            if new_mode != ControlMode.MANUAL:
                logger.warning(f"Cannot change manual gate {gate_id} to {new_mode.value}")
            else:
                self.manual_gates[gate_id].control_mode = new_mode
                self._gate_to_mode[gate_id] = new_mode
        else:
            logger.error(f"Gate {gate_id} not found in registry")
    
    def update_equipment_status(self, gate_id: str, status: EquipmentStatus):
        """Update equipment status for automated gate"""
        if gate_id in self.automated_gates:
            self.automated_gates[gate_id].equipment_status = status
            logger.info(f"Gate {gate_id} equipment status updated to {status.value}")
            
            # Check if status change should trigger mode transition
            if status == EquipmentStatus.FAILED:
                self.update_gate_mode(gate_id, ControlMode.FAILED, "Equipment failure detected")
        else:
            logger.warning(f"Gate {gate_id} is not an automated gate")
    
    def record_communication(self, gate_id: str, success: bool = True):
        """Record communication attempt with automated gate"""
        if gate_id not in self.automated_gates:
            return
        
        gate = self.automated_gates[gate_id]
        gate.last_communication = datetime.now()
        
        if success:
            gate.consecutive_failures = 0
        else:
            gate.consecutive_failures += 1
            logger.warning(f"Gate {gate_id} communication failure #{gate.consecutive_failures}")
            
            # Check if failures exceed threshold
            for rule in self.transition_rules:
                if rule.trigger == "communication_timeout":
                    threshold = rule.condition.get("consecutive_failures", 3)
                    if gate.consecutive_failures >= threshold:
                        self.update_gate_mode(gate_id, rule.to_mode, 
                                            f"Communication failures exceeded threshold ({threshold})")
    
    def get_transition_rules(self, trigger: str) -> List[ModeTransitionRule]:
        """Get transition rules for a specific trigger"""
        return [rule for rule in self.transition_rules if rule.trigger == trigger]
    
    def check_transition_conditions(self, gate_id: str) -> Optional[ModeTransitionRule]:
        """Check if any transition rules apply to current gate state"""
        if gate_id not in self._gate_to_mode:
            return None
        
        current_mode = self._gate_to_mode[gate_id]
        
        # Check each rule
        for rule in self.transition_rules:
            if rule.from_mode == current_mode:
                # Here you would implement specific condition checks
                # For now, returning None (no transition needed)
                pass
        
        return None
    
    def get_gate_summary(self) -> Dict:
        """Get summary statistics of gate registry"""
        return {
            "total_gates": len(self._gate_to_mode),
            "automated_gates": {
                "total": len(self.automated_gates),
                "operational": len([g for g in self.automated_gates.values() 
                                  if g.equipment_status == EquipmentStatus.OPERATIONAL]),
                "failed": len([g for g in self.automated_gates.values() 
                             if g.equipment_status == EquipmentStatus.FAILED]),
                "by_mode": {
                    mode.value: len([g for g in self.automated_gates.values() 
                                   if g.control_mode == mode])
                    for mode in ControlMode
                }
            },
            "manual_gates": {
                "total": len(self.manual_gates),
                "by_team_zone": {}
            }
        }
        
        # Count by team zone
        team_zones = {}
        for gate in self.manual_gates.values():
            zone = gate.field_team_zone
            team_zones[zone] = team_zones.get(zone, 0) + 1
        
        summary = self.get_gate_summary()
        summary["manual_gates"]["by_team_zone"] = team_zones
        
        return summary
    
    def export_to_dict(self) -> Dict:
        """Export registry to dictionary format"""
        return {
            "automated_gates": [asdict(gate) for gate in self.automated_gates.values()],
            "manual_gates": [asdict(gate) for gate in self.manual_gates.values()],
            "transition_rules": [asdict(rule) for rule in self.transition_rules],
            "summary": self.get_gate_summary()
        }
    
    def load_from_file(self, filename: str):
        """Load registry from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Load automated gates
            for gate_data in data.get("automated_gates", []):
                # Convert nested objects
                gate_data["control_mode"] = ControlMode(gate_data["control_mode"])
                gate_data["equipment_status"] = EquipmentStatus(gate_data["equipment_status"])
                gate_data["fallback_mode"] = ControlMode(gate_data["fallback_mode"])
                
                # Handle equipment
                equip = gate_data["control_equipment"]
                equip["actuator_type"] = ActuatorType(equip["actuator_type"])
                gate_data["control_equipment"] = ControlEquipment(**equip)
                
                # Handle maintenance schedule
                if gate_data.get("maintenance_schedule"):
                    gate_data["maintenance_schedule"] = MaintenanceSchedule(**gate_data["maintenance_schedule"])
                
                # Create and register gate
                gate = AutomatedGate(**gate_data)
                self.register_automated_gate(gate)
            
            # Load manual gates
            for gate_data in data.get("manual_gates", []):
                gate_data["control_mode"] = ControlMode(gate_data["control_mode"])
                gate_data["operation_details"] = ManualOperationDetails(**gate_data["operation_details"])
                
                gate = ManualGate(**gate_data)
                self.register_manual_gate(gate)
            
            logger.info(f"Loaded gate registry from {filename}: "
                       f"{len(self.automated_gates)} automated, {len(self.manual_gates)} manual gates")
            
        except Exception as e:
            logger.error(f"Failed to load gate registry from {filename}: {e}")
            raise
    
    def save_to_file(self, filename: str):
        """Save registry to JSON file"""
        try:
            data = self.export_to_dict()
            
            # Convert datetime objects to strings
            def convert_dates(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, dict):
                    return {k: convert_dates(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_dates(item) for item in obj]
                return obj
            
            data = convert_dates(data)
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved gate registry to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save gate registry to {filename}: {e}")
            raise
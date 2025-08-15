"""
Unit tests for Gate Registry
Tests gate classification, mode transitions, and equipment status tracking
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from core.gate_registry import (
    GateRegistry, ControlMode, EquipmentStatus, ActuatorType,
    AutomatedGate, ManualGate, ControlEquipment, ManualOperationDetails,
    ModeTransitionRule
)


class TestGateRegistry:
    """Test suite for gate registry functionality"""
    
    def test_registry_initialization(self):
        """Test empty registry initialization"""
        registry = GateRegistry()
        
        assert len(registry.automated_gates) == 0
        assert len(registry.manual_gates) == 0
        assert len(registry.transition_rules) > 0  # Default rules
    
    def test_add_automated_gate(self):
        """Test adding automated gate to registry"""
        registry = GateRegistry()
        
        control_equipment = ControlEquipment(
            actuator_type=ActuatorType.ELECTRIC,
            position_sensor="encoder",
            communication_protocol="modbus_tcp",
            ip_address="192.168.1.100",
            plc_address="MB100",
            response_time_ms=2000,
            max_speed_percent_per_sec=5.0
        )
        
        gate = AutomatedGate(
            gate_id="AUTO_1",
            location="Main Canal Gate 1",
            control_mode=ControlMode.AUTO,
            scada_tag="SCADA.GATE.AUTO_1",
            control_equipment=control_equipment,
            equipment_status=EquipmentStatus.OPERATIONAL
        )
        
        registry.add_automated_gate(gate)
        
        assert "AUTO_1" in registry.automated_gates
        assert registry.automated_gates["AUTO_1"].control_mode == ControlMode.AUTO
        assert registry._gate_to_mode["AUTO_1"] == ControlMode.AUTO
        assert registry._scada_tag_to_gate["SCADA.GATE.AUTO_1"] == "AUTO_1"
    
    def test_add_manual_gate(self):
        """Test adding manual gate to registry"""
        registry = GateRegistry()
        
        operation_details = ManualOperationDetails(
            operation_method="handwheel",
            turns_to_open=50,
            force_required="normal",
            access_road="Service Road A",
            gps_coordinates={"lat": 14.123, "lon": 100.456},
            special_tools_required=False,
            safety_notes="Ensure proper lockout/tagout"
        )
        
        gate = ManualGate(
            gate_id="MANUAL_1",
            location="Secondary Canal Gate 1",
            control_mode=ControlMode.MANUAL,
            operation_details=operation_details,
            field_team_zone="Zone_A",
            typical_operation_time_min=30
        )
        
        registry.add_manual_gate(gate)
        
        assert "MANUAL_1" in registry.manual_gates
        assert registry.manual_gates["MANUAL_1"].field_team_zone == "Zone_A"
        assert registry._gate_to_mode["MANUAL_1"] == ControlMode.MANUAL
    
    def test_update_gate_mode(self, gate_registry):
        """Test updating gate control mode"""
        # Start with AUTO mode
        assert gate_registry.get_gate_mode("G_RES_J1") == ControlMode.AUTO
        
        # Update to MANUAL
        success = gate_registry.update_gate_mode(
            "G_RES_J1", 
            ControlMode.MANUAL,
            "SCADA communication lost"
        )
        
        assert success is True
        assert gate_registry.get_gate_mode("G_RES_J1") == ControlMode.MANUAL
        assert gate_registry._gate_to_mode["G_RES_J1"] == ControlMode.MANUAL
    
    def test_is_automated_check(self, gate_registry):
        """Test checking if gate is automated"""
        assert gate_registry.is_automated("G_RES_J1") is True
        assert gate_registry.is_automated("G_J1_Z1") is False
        assert gate_registry.is_automated("UNKNOWN") is False
    
    def test_get_gates_by_mode(self, gate_registry):
        """Test getting gates filtered by mode"""
        auto_gates = gate_registry.get_gates_by_mode(ControlMode.AUTO)
        manual_gates = gate_registry.get_gates_by_mode(ControlMode.MANUAL)
        
        assert "G_RES_J1" in auto_gates
        assert "G_J1_Z1" in manual_gates
        assert len(auto_gates) == 1
        assert len(manual_gates) == 1
    
    def test_record_communication(self, gate_registry):
        """Test recording SCADA communication attempts"""
        gate_id = "G_RES_J1"
        
        # Record successful communication
        gate_registry.record_communication(gate_id, success=True)
        gate = gate_registry.automated_gates[gate_id]
        
        assert gate.consecutive_failures == 0
        assert gate.last_communication is not None
        
        # Record multiple failures
        for _ in range(3):
            gate_registry.record_communication(gate_id, success=False)
        
        assert gate.consecutive_failures == 3
    
    def test_automatic_mode_transition_on_failure(self, gate_registry):
        """Test automatic mode transition after communication failures"""
        gate_id = "G_RES_J1"
        
        # Simulate communication timeout
        gate = gate_registry.automated_gates[gate_id]
        gate.last_communication = datetime.now() - timedelta(seconds=60)
        
        # Record failures to trigger transition
        for _ in range(3):
            gate_registry.record_communication(gate_id, success=False)
        
        # Check for automatic transition
        transitions = gate_registry.check_transition_rules()
        
        assert len(transitions) > 0
        assert any(t["gate_id"] == gate_id for t in transitions)
        assert any(t["to_mode"] == ControlMode.MANUAL for t in transitions)
    
    def test_update_equipment_status(self, gate_registry):
        """Test updating equipment status"""
        gate_id = "G_RES_J1"
        
        gate_registry.update_equipment_status(
            gate_id,
            EquipmentStatus.DEGRADED,
            "Position sensor showing drift"
        )
        
        gate = gate_registry.automated_gates[gate_id]
        assert gate.equipment_status == EquipmentStatus.DEGRADED
        assert "drift" in gate.notes.lower()
    
    def test_get_gate_summary(self, gate_registry):
        """Test getting registry summary"""
        summary = gate_registry.get_gate_summary()
        
        assert summary["total_gates"] == 2
        assert summary["automated_count"] == 1
        assert summary["manual_count"] == 1
        assert summary["gates_by_status"]["operational"] > 0
    
    def test_custom_transition_rule(self):
        """Test adding custom transition rules"""
        registry = GateRegistry()
        
        # Add custom rule for maintenance mode
        rule = ModeTransitionRule(
            trigger="scheduled_maintenance",
            from_mode=ControlMode.AUTO,
            to_mode=ControlMode.MAINTENANCE,
            condition={"hour_of_day": 2},  # 2 AM maintenance
            priority=2,
            notification_required=True
        )
        
        registry.add_transition_rule(rule)
        
        assert rule in registry.transition_rules
    
    def test_save_and_load_config(self, tmp_path):
        """Test saving and loading registry configuration"""
        registry = GateRegistry()
        
        # Add some gates
        registry.automated_gates["TEST_AUTO"] = Mock(spec=AutomatedGate)
        registry.manual_gates["TEST_MANUAL"] = Mock(spec=ManualGate)
        
        # Save to file
        config_file = tmp_path / "gate_config.json"
        registry.save_to_file(str(config_file))
        
        assert config_file.exists()
        
        # Load into new registry
        new_registry = GateRegistry(str(config_file))
        
        assert "TEST_AUTO" in new_registry.automated_gates
        assert "TEST_MANUAL" in new_registry.manual_gates
    
    def test_get_gate_by_location(self, gate_registry):
        """Test finding gate by location"""
        location = "Reservoir to Junction 1"
        gate_id = gate_registry.get_gate_by_location(location)
        
        assert gate_id == "G_RES_J1"
    
    def test_get_operational_statistics(self, gate_registry):
        """Test getting operational statistics"""
        stats = gate_registry.get_operational_statistics()
        
        assert "uptime_percentage" in stats
        assert "avg_response_time_ms" in stats
        assert "total_mode_transitions" in stats
        assert "gates_needing_maintenance" in stats
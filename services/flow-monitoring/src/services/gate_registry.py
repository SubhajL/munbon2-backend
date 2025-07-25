"""
Gate Registry Service
Centralized source of truth for gate configurations and types
Used by all instances to understand gate automation status
"""

import json
from typing import Dict, List, Optional, Set
from pathlib import Path
from core import get_logger

logger = get_logger(__name__)


class GateRegistry:
    """Manages gate configurations and automation status"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logger.bind(service="gate_registry")
        
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "gate_configuration.json"
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.gates = self.config["gates"]
        self._build_indices()
    
    def _build_indices(self):
        """Build lookup indices for efficient queries"""
        self.automated_gates: Set[str] = set()
        self.manual_gates: Set[str] = set()
        self.gates_by_zone: Dict[int, List[str]] = {}
        self.scada_to_gate: Dict[str, str] = {}
        
        for gate_id, gate_info in self.gates.items():
            # Type index
            if gate_info["type"] == "automated":
                self.automated_gates.add(gate_id)
                if "scada_id" in gate_info:
                    self.scada_to_gate[gate_info["scada_id"]] = gate_id
            else:
                self.manual_gates.add(gate_id)
            
            # Zone index
            zone = gate_info.get("zone", 0)
            if zone not in self.gates_by_zone:
                self.gates_by_zone[zone] = []
            self.gates_by_zone[zone].append(gate_id)
    
    def get_gate_info(self, gate_id: str) -> Optional[Dict]:
        """Get complete information for a gate"""
        return self.gates.get(gate_id)
    
    def is_automated(self, gate_id: str) -> bool:
        """Check if a gate is automated"""
        return gate_id in self.automated_gates
    
    def is_manual(self, gate_id: str) -> bool:
        """Check if a gate is manual"""
        return gate_id in self.manual_gates
    
    def get_gate_type(self, gate_id: str) -> Optional[str]:
        """Get gate type (automated/manual)"""
        gate_info = self.gates.get(gate_id)
        return gate_info["type"] if gate_info else None
    
    def get_automated_gates(self) -> List[str]:
        """Get list of all automated gates"""
        return list(self.automated_gates)
    
    def get_manual_gates(self) -> List[str]:
        """Get list of all manual gates"""
        return list(self.manual_gates)
    
    def get_gates_by_zone(self, zone: int) -> List[str]:
        """Get all gates in a specific zone"""
        return self.gates_by_zone.get(zone, [])
    
    def get_gates_for_field_team(self, team: str, day: str) -> List[Dict]:
        """Get gates assigned to a field team for a specific day"""
        # This would integrate with scheduler for actual assignments
        # For now, return manual gates that need operation
        manual_gates = []
        
        for gate_id in self.manual_gates:
            gate_info = self.gates[gate_id]
            manual_gates.append({
                "gate_id": gate_id,
                "name": gate_info["name"],
                "location": gate_info["location"],
                "physical_markers": gate_info.get("physical_markers", ""),
                "operation_time": gate_info.get("manual_operation", {}).get("time_to_operate_minutes", 15),
                "tool_required": gate_info.get("manual_operation", {}).get("tool_required", "standard_wheel")
            })
        
        return manual_gates
    
    def get_gate_by_scada_id(self, scada_id: str) -> Optional[str]:
        """Get gate ID from SCADA ID"""
        return self.scada_to_gate.get(scada_id)
    
    def can_fallback_to_manual(self, gate_id: str) -> bool:
        """Check if automated gate can be operated manually"""
        gate_info = self.gates.get(gate_id)
        if not gate_info:
            return False
        
        return gate_info.get("fallback_manual", False)
    
    def get_gate_calibration(self, gate_id: str) -> Optional[Dict]:
        """Get calibration parameters for a gate"""
        gate_info = self.gates.get(gate_id)
        if not gate_info:
            return None
        
        return gate_info.get("calibration")
    
    def get_gate_physical_markers(self, gate_id: str) -> Optional[str]:
        """Get physical marker description for field teams"""
        gate_info = self.gates.get(gate_id)
        if not gate_info:
            return None
        
        return gate_info.get("physical_markers")
    
    def get_operational_summary(self) -> Dict:
        """Get summary of gate operations"""
        return {
            "total_gates": len(self.gates),
            "automated_gates": len(self.automated_gates),
            "manual_gates": len(self.manual_gates),
            "gates_with_fallback": sum(
                1 for g in self.gates.values() 
                if g.get("fallback_manual", False)
            ),
            "zones": sorted(self.gates_by_zone.keys()),
            "automation_percentage": (len(self.automated_gates) / len(self.gates) * 100) if self.gates else 0
        }
    
    def get_gates_near_location(self, lat: float, lon: float, radius_km: float = 5.0) -> List[Dict]:
        """Find gates within radius of a location"""
        from math import radians, sin, cos, sqrt, atan2
        
        nearby_gates = []
        
        for gate_id, gate_info in self.gates.items():
            gate_loc = gate_info.get("location", {})
            if not gate_loc:
                continue
            
            # Haversine formula for distance
            R = 6371  # Earth's radius in km
            lat1, lon1 = radians(lat), radians(lon)
            lat2, lon2 = radians(gate_loc["lat"]), radians(gate_loc["lon"])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance = R * c
            
            if distance <= radius_km:
                nearby_gates.append({
                    "gate_id": gate_id,
                    "name": gate_info["name"],
                    "type": gate_info["type"],
                    "distance_km": round(distance, 2),
                    "location": gate_loc
                })
        
        # Sort by distance
        nearby_gates.sort(key=lambda x: x["distance_km"])
        return nearby_gates


# Singleton instance
_gate_registry = None

def get_gate_registry() -> GateRegistry:
    """Get the singleton gate registry instance"""
    global _gate_registry
    if _gate_registry is None:
        _gate_registry = GateRegistry()
    return _gate_registry
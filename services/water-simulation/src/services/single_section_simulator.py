"""
Specialized simulation service for single section water delivery
Tracks water movement through canals and delivery to target section
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

from ..core.simulation_engine import SimulationEngine


@dataclass
class WaterFront:
    """Track water front position in canal network"""
    current_position: str  # Current node/gate ID
    distance_traveled_km: float
    volume_delivered_m3: float
    path_index: int  # Current index in delivery path
    velocity_ms: float  # Current velocity


class SingleSectionSimulator:
    """Specialized simulator for single section delivery scenarios"""
    
    def __init__(self, engine: SimulationEngine):
        self.engine = engine
        self.water_front = None
        self.delivery_path = []
        self.target_section = None
        self.canal_segments = {}
        
    async def initialize_single_section_simulation(self, scenario_metadata: Dict):
        """Initialize simulation for single section delivery"""
        # Extract metadata
        self.target_section = scenario_metadata["target_section"]
        self.delivery_path = scenario_metadata["delivery_path"]
        canal_volumes = scenario_metadata["canal_volumes"]
        
        # Build canal segment lookup
        for segment in canal_volumes["canal_segments"]:
            key = f"{segment['from']}_{segment['to']}"
            self.canal_segments[key] = segment
        
        # Initialize water front at source
        if self.delivery_path:
            self.water_front = WaterFront(
                current_position=self.delivery_path[0]["from"],
                distance_traveled_km=0.0,
                volume_delivered_m3=0.0,
                path_index=0,
                velocity_ms=0.75  # Default 0.75 m/s
            )
        
        # Set all sections to zero demand except target
        await self._set_all_demands_to_zero_except_target()
    
    async def simulate_water_delivery(self, time_step_seconds: float) -> Dict:
        """
        Simulate water movement for one time step
        
        Returns:
            Update dictionary with water front position and delivery status
        """
        if not self.water_front or self.water_front.path_index >= len(self.delivery_path):
            return {"status": "completed", "water_delivered": True}
        
        # Current segment
        current_segment = self.delivery_path[self.water_front.path_index]
        
        # Calculate distance moved in this time step
        distance_moved_km = (self.water_front.velocity_ms * time_step_seconds) / 1000
        
        # Update water front position
        segment_remaining_km = current_segment.get("distance_km", 1.0) - \
                             (self.water_front.distance_traveled_km % current_segment.get("distance_km", 1.0))
        
        if distance_moved_km >= segment_remaining_km:
            # Water front reaches next node
            self.water_front.distance_traveled_km += segment_remaining_km
            self.water_front.path_index += 1
            
            if self.water_front.path_index < len(self.delivery_path):
                self.water_front.current_position = self.delivery_path[self.water_front.path_index]["from"]
                
                # Open gate if next segment goes through a gate
                next_segment = self.delivery_path[self.water_front.path_index]
                if next_segment["type"] == "gate":
                    await self._open_gate_for_delivery(next_segment["to"])
            else:
                # Reached target section
                self.water_front.current_position = self.target_section["delivery_gate"]
                return await self._deliver_water_to_section()
        else:
            # Still in current segment
            self.water_front.distance_traveled_km += distance_moved_km
        
        # Calculate volume delivered based on flow rate
        flow_rate_m3s = await self._calculate_current_flow_rate()
        volume_delivered = flow_rate_m3s * time_step_seconds
        self.water_front.volume_delivered_m3 += volume_delivered
        
        # Update canal water levels along the path
        await self._update_canal_water_levels()
        
        return {
            "status": "in_progress",
            "water_front": {
                "position": self.water_front.current_position,
                "distance_km": self.water_front.distance_traveled_km,
                "path_progress": self.water_front.path_index / len(self.delivery_path),
                "volume_delivered_m3": self.water_front.volume_delivered_m3
            }
        }
    
    async def _set_all_demands_to_zero_except_target(self):
        """Override all section demands to zero except target"""
        # This is handled by demand overrides in the scenario
        # Here we just ensure the simulation engine recognizes it
        for section_id in self.engine.section_details:
            if section_id != self.target_section["section_id"]:
                # The demand will be overridden to zero via SectionDemand table
                pass
    
    async def _open_gate_for_delivery(self, gate_id: str):
        """Open gate to allow water flow"""
        if gate_id in self.engine.gate_properties:
            # Calculate required opening based on target flow
            target_flow_m3s = 10.0  # Target flow rate
            
            # Get current water levels
            upstream_node = self.engine._find_upstream_node(gate_id)
            downstream_node = self.engine._find_downstream_node(gate_id)
            
            if upstream_node and downstream_node:
                upstream_level = self.engine.current_state["water_levels"].get(upstream_node, 3.0)
                downstream_level = self.engine.current_state["water_levels"].get(downstream_node, 2.5)
                
                # Calculate required opening
                head_diff = upstream_level - downstream_level
                if head_diff > 0:
                    # Simplified calculation - in reality would use gate equations
                    required_opening = min(
                        target_flow_m3s / (2.5 * head_diff),  # Simplified
                        self.engine.gate_properties[gate_id].get("max_opening_m", 2.0)
                    )
                    
                    # Update gate position
                    self.engine.current_state["gate_positions"][gate_id] = required_opening
    
    async def _calculate_current_flow_rate(self) -> float:
        """Calculate current flow rate at water front position"""
        # Base flow rate
        base_flow_m3s = 10.0
        
        # Adjust based on canal characteristics if available
        if self.water_front.path_index < len(self.delivery_path):
            current_segment = self.delivery_path[self.water_front.path_index]
            segment_key = f"{current_segment['from']}_{current_segment['to']}"
            
            if segment_key in self.canal_segments:
                canal_info = self.canal_segments[segment_key]
                cross_section = canal_info.get("cross_section_m2", 10.0)
                
                # Flow = velocity × area
                flow_m3s = self.water_front.velocity_ms * cross_section * 0.7  # 70% fill
                return min(flow_m3s, base_flow_m3s * 1.5)  # Cap at 150% base
        
        return base_flow_m3s
    
    async def _update_canal_water_levels(self):
        """Update water levels in canals that have been filled"""
        # For each segment up to current position, set appropriate water levels
        for i in range(min(self.water_front.path_index + 1, len(self.delivery_path))):
            segment = self.delivery_path[i]
            
            if segment["type"] == "canal":
                # Set water level for canal nodes
                # Simplified - in reality would calculate based on flow
                if segment["from"] in self.engine.current_state["water_levels"]:
                    self.engine.current_state["water_levels"][segment["from"]] = 3.0  # Operating level
                if segment["to"] in self.engine.current_state["water_levels"]:
                    self.engine.current_state["water_levels"][segment["to"]] = 2.8
    
    async def _deliver_water_to_section(self) -> Dict:
        """Deliver water to target section"""
        section_id = self.target_section["section_id"]
        required_volume = self.target_section["water_volume_m3"]
        
        # Check if enough water has been delivered
        if self.water_front.volume_delivered_m3 >= required_volume:
            return {
                "status": "completed",
                "water_delivered": True,
                "target_section": section_id,
                "volume_delivered_m3": self.water_front.volume_delivered_m3,
                "delivery_complete": True
            }
        else:
            # Continue delivering
            return {
                "status": "delivering",
                "water_delivered": False,
                "target_section": section_id,
                "volume_delivered_m3": self.water_front.volume_delivered_m3,
                "percent_complete": (self.water_front.volume_delivered_m3 / required_volume) * 100
            }
    
    def get_water_tracking_state(self) -> Dict:
        """Get current water tracking state for storage"""
        if not self.water_front:
            return {}
        
        total_distance = sum(seg.get("distance_km", 1.0) for seg in self.delivery_path)
        
        # Find gates passed
        gates_passed = []
        for i in range(self.water_front.path_index):
            segment = self.delivery_path[i]
            if segment["type"] == "gate":
                gates_passed.append(segment["to"])
        
        # Current segment info
        current_segment = None
        if self.water_front.path_index < len(self.delivery_path):
            segment = self.delivery_path[self.water_front.path_index]
            current_segment = {
                "from": segment["from"],
                "to": segment["to"],
                "type": segment["type"]
            }
        
        # Estimate arrival time
        remaining_distance = total_distance - self.water_front.distance_traveled_km
        remaining_hours = remaining_distance / (self.water_front.velocity_ms * 3.6)
        estimated_arrival = datetime.now() + timedelta(hours=remaining_hours)
        
        return {
            "current_position": self.water_front.current_position,
            "distance_traveled_km": self.water_front.distance_traveled_km,
            "total_distance_km": total_distance,
            "progress_percent": (self.water_front.distance_traveled_km / total_distance) * 100,
            "estimated_arrival_time": estimated_arrival.isoformat(),
            "gates_passed": gates_passed,
            "current_segment": current_segment,
            "velocity_ms": self.water_front.velocity_ms,
            "volume_delivered_m3": self.water_front.volume_delivered_m3
        }
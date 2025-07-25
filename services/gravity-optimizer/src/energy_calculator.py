"""
Energy calculator for hydraulic grade line and energy profiles
Calculates pressure head, velocity head, and total energy along flow paths
"""

import numpy as np
from typing import List, Dict, Optional
import logging
from models import (
    EnergyPoint, PathProfile, OptimalGateSetting,
    HydraulicState
)
from hydraulic_engine import HydraulicEngine

logger = logging.getLogger(__name__)

class EnergyCalculator:
    def __init__(self):
        self.hydraulic_engine = HydraulicEngine()
        self.gravity = 9.81  # m/s²
    
    async def calculate_profiles(
        self,
        gate_settings: Dict[str, OptimalGateSetting],
        network_topology: Dict[str, any]
    ) -> Dict[str, List[EnergyPoint]]:
        """Calculate energy profiles for all active flow paths"""
        
        profiles = {}
        
        # Identify active paths based on gate settings
        active_paths = self._identify_active_paths(gate_settings)
        
        for path_id, nodes in active_paths.items():
            # Get hydraulic states
            states = await self._get_path_states(nodes, gate_settings)
            
            # Calculate energy profile
            profile = self._calculate_energy_profile(nodes, states)
            profiles[path_id] = profile
        
        return profiles
    
    async def calculate_path_profile(
        self,
        nodes: List[str],
        current_state: Dict[str, HydraulicState]
    ) -> PathProfile:
        """Calculate detailed energy profile for a specific path"""
        
        energy_points = []
        hgl_points = []
        total_distance = 0.0
        min_pressure_head = float('inf')
        critical_points = []
        
        # Node elevations
        elevations = {
            "Source": 221.0,
            "M(0,0)": 220.9,
            "M(0,2)": 220.7,
            "Zone_2": 220.5,
            "M(0,5)": 220.6,
            "Zone_5": 220.3
        }
        
        # Calculate for each node
        for i, node in enumerate(nodes):
            state = current_state.get(node)
            if not state:
                continue
            
            elevation = elevations.get(node, 220.0)
            water_level = state.water_level_m
            depth = state.depth_m
            velocity = state.velocity_ms
            
            # Energy components
            pressure_head = depth
            velocity_head = velocity**2 / (2 * self.gravity)
            total_energy = elevation + pressure_head + velocity_head
            specific_energy = pressure_head + velocity_head
            
            # Check for critical conditions
            if state.froude_number > 0.95 and state.froude_number < 1.05:
                critical_points.append(node)
            
            min_pressure_head = min(min_pressure_head, pressure_head)
            
            # Create energy point
            point = EnergyPoint(
                location=node,
                distance_m=total_distance,
                elevation_m=elevation,
                water_depth_m=depth,
                pressure_head_m=pressure_head,
                velocity_head_m=velocity_head,
                total_energy_m=total_energy,
                specific_energy_m=specific_energy
            )
            
            energy_points.append(point)
            hgl_points.append(water_level)
            
            # Update distance for next segment
            if i < len(nodes) - 1:
                # Estimate distance (would use actual canal lengths)
                total_distance += 1000  # Default 1km between nodes
        
        # Calculate total head loss
        if len(energy_points) >= 2:
            total_head_loss = energy_points[0].total_energy_m - energy_points[-1].total_energy_m
        else:
            total_head_loss = 0.0
        
        return PathProfile(
            energy_points=energy_points,
            hgl_points=hgl_points,
            total_head_loss=total_head_loss,
            critical_points=critical_points,
            min_pressure_head=min_pressure_head
        )
    
    def _identify_active_paths(self, gate_settings: Dict[str, OptimalGateSetting]) -> Dict[str, List[str]]:
        """Identify active flow paths based on open gates"""
        
        # Simplified path identification
        paths = {}
        
        # Check main distribution paths
        if "Source->M(0,0)" in gate_settings and gate_settings["Source->M(0,0)"].flow_m3s > 0:
            
            if "M(0,0)->M(0,2)" in gate_settings and gate_settings["M(0,0)->M(0,2)"].flow_m3s > 0:
                paths["Zone_2_Path"] = ["Source", "M(0,0)", "M(0,2)", "Zone_2"]
            
            if "M(0,0)->M(0,5)" in gate_settings and gate_settings["M(0,0)->M(0,5)"].flow_m3s > 0:
                paths["Zone_5_Path"] = ["Source", "M(0,0)", "M(0,5)", "Zone_5"]
        
        return paths
    
    async def _get_path_states(
        self,
        nodes: List[str],
        gate_settings: Dict[str, OptimalGateSetting]
    ) -> Dict[str, HydraulicState]:
        """Get hydraulic states for path nodes"""
        
        states = {}
        
        for i, node in enumerate(nodes):
            # Get water level from gate settings or estimate
            water_level = self._estimate_water_level(node, gate_settings)
            
            # Get flow from upstream gate
            flow = 0.0
            if i > 0:
                gate_id = f"{nodes[i-1]}->{node}"
                if gate_id in gate_settings:
                    flow = gate_settings[gate_id].flow_m3s
            
            # Estimate velocity (simplified)
            velocity = flow / 3.0 if flow > 0 else 0.0  # Assume 3m² area
            
            # Calculate other parameters
            elevation = self._get_elevation(node)
            depth = water_level - elevation
            froude = self.hydraulic_engine.calculate_froude_number(velocity, depth)
            
            states[node] = HydraulicState(
                node_id=node,
                water_level_m=water_level,
                flow_m3s=flow,
                velocity_ms=velocity,
                depth_m=depth,
                froude_number=froude,
                specific_energy_m=depth + velocity**2/(2*self.gravity)
            )
        
        return states
    
    def _calculate_energy_profile(
        self,
        nodes: List[str],
        states: Dict[str, HydraulicState]
    ) -> List[EnergyPoint]:
        """Calculate energy profile for a path"""
        
        points = []
        distance = 0.0
        
        for i, node in enumerate(nodes):
            if node not in states:
                continue
            
            state = states[node]
            elevation = self._get_elevation(node)
            
            point = EnergyPoint(
                location=node,
                distance_m=distance,
                elevation_m=elevation,
                water_depth_m=state.depth_m,
                pressure_head_m=state.depth_m,
                velocity_head_m=state.velocity_ms**2 / (2 * self.gravity),
                total_energy_m=elevation + state.depth_m + state.velocity_ms**2 / (2 * self.gravity),
                specific_energy_m=state.specific_energy_m
            )
            
            points.append(point)
            
            # Update distance
            if i < len(nodes) - 1:
                distance += 1000  # Default segment length
        
        return points
    
    def _estimate_water_level(self, node: str, gate_settings: Dict[str, OptimalGateSetting]) -> float:
        """Estimate water level at a node based on gate settings"""
        
        # Check if node is mentioned in gate settings
        for gate_id, setting in gate_settings.items():
            if node in gate_id.split("->")[0]:
                return setting.upstream_level_m
            elif node in gate_id.split("->")[1]:
                return setting.downstream_level_m
        
        # Default estimate
        elevation = self._get_elevation(node)
        return elevation + 1.0  # Default 1m depth
    
    def _get_elevation(self, node: str) -> float:
        """Get node elevation"""
        elevations = {
            "Source": 221.0,
            "M(0,0)": 220.9,
            "M(0,2)": 220.7,
            "Zone_2": 220.5,
            "M(0,5)": 220.6,
            "Zone_5": 220.3,
            "Zone_1": 219.0,
            "Zone_3": 217.0,
            "Zone_4": 216.5,
            "Zone_6": 215.5
        }
        return elevations.get(node, 220.0)
    
    def calculate_energy_recovery_potential(
        self,
        upstream_level: float,
        downstream_level: float,
        flow_m3s: float,
        efficiency: float = 0.85
    ) -> Dict[str, float]:
        """Calculate potential energy recovery at a gate (micro-hydro)"""
        
        # Available head
        head = upstream_level - downstream_level
        
        # Theoretical power: P = ρ * g * Q * H
        theoretical_power = 1000 * self.gravity * flow_m3s * head  # Watts
        
        # Actual recoverable power
        actual_power = theoretical_power * efficiency
        
        # Annual energy production (assuming 80% availability)
        annual_energy = actual_power * 24 * 365 * 0.8 / 1000  # kWh
        
        return {
            "head_m": head,
            "flow_m3s": flow_m3s,
            "theoretical_power_kW": theoretical_power / 1000,
            "recoverable_power_kW": actual_power / 1000,
            "annual_energy_kWh": annual_energy,
            "co2_savings_tons_year": annual_energy * 0.0005  # Approximate CO2 factor
        }
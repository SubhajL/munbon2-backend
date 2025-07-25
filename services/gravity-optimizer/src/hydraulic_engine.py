"""
Hydraulic calculations engine for gravity flow
Implements Manning's equation, energy equations, and hydraulic grade line calculations
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
from models import (
    CanalCharacteristics, FrictionLossResult, FlowRegime,
    HydraulicState, CanalSection
)

logger = logging.getLogger(__name__)

class HydraulicEngine:
    def __init__(self):
        self.gravity = 9.81  # m/s²
        self.water_density = 1000  # kg/m³
        self.kinematic_viscosity = 1.0e-6  # m²/s at 20°C
        
        # Network data (would come from database in production)
        self.canal_data = self._load_canal_data()
        self.node_elevations = self._load_node_elevations()
    
    def _load_canal_data(self) -> Dict[str, CanalSection]:
        """Load canal geometry data"""
        # Mock data - would query PostGIS in production
        return {
            "Source->M(0,0)": CanalSection(
                canal_id="Source->M(0,0)",
                upstream_node="Source",
                downstream_node="M(0,0)",
                length_m=500,
                bed_slope=0.0002,
                bottom_width_m=4.0,
                side_slope=1.5,
                manning_n=0.025,
                max_depth_m=3.0
            ),
            "M(0,0)->M(0,2)": CanalSection(
                canal_id="M(0,0)->M(0,2)",
                upstream_node="M(0,0)",
                downstream_node="M(0,2)",
                length_m=1200,
                bed_slope=0.0001,
                bottom_width_m=3.5,
                side_slope=1.5,
                manning_n=0.025,
                max_depth_m=2.5
            ),
            "M(0,2)->Zone_2": CanalSection(
                canal_id="M(0,2)->Zone_2",
                upstream_node="M(0,2)",
                downstream_node="Zone_2",
                length_m=800,
                bed_slope=0.00015,
                bottom_width_m=3.0,
                side_slope=1.5,
                manning_n=0.025,
                max_depth_m=2.0
            )
        }
    
    def _load_node_elevations(self) -> Dict[str, float]:
        """Load node elevation data"""
        return {
            "Source": 221.0,
            "M(0,0)": 220.9,
            "M(0,2)": 220.7,
            "Zone_2": 220.5,
            "M(0,5)": 220.6,
            "Zone_5": 220.3
        }
    
    async def get_current_state(self, nodes: List[str]) -> Dict[str, HydraulicState]:
        """Get current hydraulic state for nodes"""
        states = {}
        
        # Mock implementation - would query real-time data
        mock_levels = {
            "Source": 221.5,
            "M(0,0)": 219.2,
            "M(0,2)": 218.9,
            "Zone_2": 218.5
        }
        
        for node in nodes:
            if node in mock_levels:
                elevation = self.node_elevations.get(node, 220.0)
                water_level = mock_levels.get(node, elevation + 0.5)
                depth = water_level - elevation
                
                states[node] = HydraulicState(
                    node_id=node,
                    water_level_m=water_level,
                    flow_m3s=3.5,  # Mock flow
                    velocity_ms=1.2,  # Mock velocity
                    depth_m=depth,
                    froude_number=self.calculate_froude_number(1.2, depth),
                    specific_energy_m=depth + (1.2**2)/(2*self.gravity)
                )
        
        return states
    
    async def get_canal_characteristics(self, canal_id: str) -> CanalCharacteristics:
        """Get canal characteristics"""
        if canal_id not in self.canal_data:
            raise ValueError(f"Canal {canal_id} not found")
        
        canal = self.canal_data[canal_id]
        
        # Mock current conditions
        return CanalCharacteristics(
            canal_id=canal_id,
            length_m=canal.length_m,
            bed_slope=canal.bed_slope,
            bottom_width_m=canal.bottom_width_m,
            side_slope=canal.side_slope,
            manning_n=canal.manning_n,
            current_flow_m3s=3.5,
            current_depth_m=1.2
        )
    
    async def calculate_friction_loss(
        self,
        canal_id: str,
        flow_m3s: float,
        canal_data: CanalCharacteristics
    ) -> FrictionLossResult:
        """Calculate friction losses using Manning's equation"""
        
        # Calculate flow area and hydraulic radius
        depth = self.calculate_normal_depth(
            flow_m3s,
            canal_data.bottom_width_m,
            canal_data.side_slope,
            canal_data.bed_slope,
            canal_data.manning_n
        )
        
        area = self.calculate_flow_area(
            depth,
            canal_data.bottom_width_m,
            canal_data.side_slope
        )
        
        wetted_perimeter = self.calculate_wetted_perimeter(
            depth,
            canal_data.bottom_width_m,
            canal_data.side_slope
        )
        
        hydraulic_radius = area / wetted_perimeter
        velocity = flow_m3s / area
        
        # Manning's equation: hf = (n²V²L)/(R^(4/3))
        # Or: Sf = (nV)²/(R^(4/3))
        friction_slope = (canal_data.manning_n * velocity)**2 / (hydraulic_radius**(4/3))
        friction_loss = friction_slope * canal_data.length_m
        
        # Calculate Reynolds number
        reynolds = velocity * hydraulic_radius * 4 / self.kinematic_viscosity
        
        # Determine flow regime
        froude = self.calculate_froude_number(velocity, depth)
        if froude < 1:
            regime = FlowRegime.SUBCRITICAL
        elif froude > 1:
            regime = FlowRegime.SUPERCRITICAL
        else:
            regime = FlowRegime.CRITICAL
        
        return FrictionLossResult(
            friction_loss=friction_loss,
            friction_slope=friction_slope,
            velocity=velocity,
            hydraulic_radius=hydraulic_radius,
            reynolds_number=reynolds,
            flow_regime=regime
        )
    
    def calculate_normal_depth(
        self,
        flow_m3s: float,
        bottom_width: float,
        side_slope: float,
        bed_slope: float,
        manning_n: float
    ) -> float:
        """Calculate normal depth using Manning's equation (iterative)"""
        
        # Initial guess
        depth = 1.0
        tolerance = 0.001
        max_iterations = 100
        
        for i in range(max_iterations):
            area = self.calculate_flow_area(depth, bottom_width, side_slope)
            perimeter = self.calculate_wetted_perimeter(depth, bottom_width, side_slope)
            hydraulic_radius = area / perimeter
            
            # Manning's equation: Q = (1/n) * A * R^(2/3) * S^(1/2)
            q_calc = (1/manning_n) * area * (hydraulic_radius**(2/3)) * (bed_slope**0.5)
            
            # Newton-Raphson iteration
            error = q_calc - flow_m3s
            if abs(error) < tolerance:
                break
            
            # Derivative approximation
            delta_d = 0.001
            area_plus = self.calculate_flow_area(depth + delta_d, bottom_width, side_slope)
            perimeter_plus = self.calculate_wetted_perimeter(depth + delta_d, bottom_width, side_slope)
            r_plus = area_plus / perimeter_plus
            q_plus = (1/manning_n) * area_plus * (r_plus**(2/3)) * (bed_slope**0.5)
            
            dq_dd = (q_plus - q_calc) / delta_d
            depth = depth - error / dq_dd
            
            # Ensure positive depth
            depth = max(0.01, depth)
        
        return depth
    
    def calculate_flow_area(self, depth: float, bottom_width: float, side_slope: float) -> float:
        """Calculate flow area for trapezoidal channel"""
        return depth * (bottom_width + side_slope * depth)
    
    def calculate_wetted_perimeter(self, depth: float, bottom_width: float, side_slope: float) -> float:
        """Calculate wetted perimeter for trapezoidal channel"""
        return bottom_width + 2 * depth * np.sqrt(1 + side_slope**2)
    
    def calculate_froude_number(self, velocity: float, depth: float) -> float:
        """Calculate Froude number"""
        return velocity / np.sqrt(self.gravity * depth)
    
    async def calculate_required_upstream_level(
        self,
        target_section: str,
        target_elevation: float,
        required_flow_m3s: float,
        path_nodes: List[str]
    ) -> float:
        """Calculate required upstream water level to deliver flow by gravity"""
        
        total_losses = 0.0
        current_elevation = target_elevation
        
        # Work backwards from target to source
        for i in range(len(path_nodes) - 1, 0, -1):
            upstream_node = path_nodes[i-1]
            downstream_node = path_nodes[i]
            canal_id = f"{upstream_node}->{downstream_node}"
            
            if canal_id in self.canal_data:
                canal = self.canal_data[canal_id]
                
                # Calculate friction loss for this section
                canal_chars = await self.get_canal_characteristics(canal_id)
                losses = await self.calculate_friction_loss(
                    canal_id,
                    required_flow_m3s,
                    canal_chars
                )
                
                total_losses += losses.friction_loss
                
                # Add minor losses (10% of friction losses as approximation)
                total_losses += 0.1 * losses.friction_loss
        
        # Required upstream level = target elevation + minimum depth + total losses
        min_depth = 0.3  # minimum operating depth
        required_level = target_elevation + min_depth + total_losses
        
        return required_level
    
    def calculate_gate_flow(
        self,
        opening_m: float,
        upstream_level: float,
        downstream_level: float,
        gate_width: float,
        discharge_coefficient: float = 0.61
    ) -> float:
        """Calculate flow through a gate using standard gate equation"""
        
        # Effective head
        h_upstream = upstream_level
        h_downstream = downstream_level
        
        # Check if free or submerged flow
        if downstream_level < opening_m:
            # Free flow
            flow = discharge_coefficient * gate_width * opening_m * np.sqrt(2 * self.gravity * h_upstream)
        else:
            # Submerged flow
            submergence_ratio = (h_downstream - opening_m) / (h_upstream - opening_m)
            reduction_factor = np.sqrt(1 - submergence_ratio)
            flow = discharge_coefficient * gate_width * opening_m * np.sqrt(2 * self.gravity * h_upstream) * reduction_factor
        
        return flow
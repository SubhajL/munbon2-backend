import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from ..models.channel import Channel, ChannelSection, FlowCondition
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class DepthRequirement:
    """Minimum depth requirements for a channel section"""
    section_id: str
    flow_rate: float
    min_depth_hydraulic: float  # Based on hydraulic requirements
    min_depth_sediment: float   # To prevent sedimentation
    min_depth_operation: float  # For gate operation
    critical_depth: float       # Critical flow depth
    recommended_depth: float    # Recommended operational depth
    froude_number: float
    flow_regime: str           # subcritical, critical, supercritical


class MinimumDepthCalculator:
    """Calculate minimum required flow depths for proper canal operation"""
    
    def __init__(self):
        self.gravity = settings.gravity
        self.min_velocity = settings.min_flow_velocity
        self.safety_factor = settings.depth_safety_factor
        self.min_operational_depth = settings.min_flow_depth
        
    def calculate_section_requirements(
        self,
        section: ChannelSection,
        flow_rate: float,
        upstream_depth: Optional[float] = None
    ) -> DepthRequirement:
        """
        Calculate minimum depth requirements for a channel section
        
        Args:
            section: Channel section geometry
            flow_rate: Design flow rate in m³/s
            upstream_depth: Upstream water depth (for backwater effects)
        
        Returns:
            DepthRequirement with all calculated depths
        """
        # Calculate critical depth
        critical_depth = self._calculate_critical_depth(
            flow_rate, section.bed_width, section.side_slope
        )
        
        # Calculate normal depth using Manning's equation
        slope = abs(section.start_elevation - section.end_elevation) / section.length
        normal_depth = self._calculate_normal_depth(
            flow_rate, section.bed_width, section.side_slope,
            section.manning_n, slope
        )
        
        # Calculate depth for minimum velocity (sediment transport)
        min_depth_sediment = self._calculate_depth_for_min_velocity(
            flow_rate, section.bed_width, section.side_slope,
            self.min_velocity
        )
        
        # Operational minimum (gate clearance, measurement accuracy)
        min_depth_operation = self.min_operational_depth
        
        # Calculate Froude number
        area = self._calculate_area(normal_depth, section.bed_width, section.side_slope)
        top_width = section.bed_width + 2 * section.side_slope * normal_depth
        hydraulic_depth = area / top_width
        velocity = flow_rate / area
        froude_number = velocity / np.sqrt(self.gravity * hydraulic_depth)
        
        # Determine flow regime
        if froude_number < 0.9:
            flow_regime = "subcritical"
        elif froude_number > 1.1:
            flow_regime = "supercritical"
        else:
            flow_regime = "critical"
        
        # Apply safety factor to get recommended depth
        hydraulic_requirements = [normal_depth, critical_depth * 1.1]  # 10% above critical
        if upstream_depth:
            # Consider backwater effects
            backwater_depth = self._estimate_backwater_depth(
                section, flow_rate, upstream_depth
            )
            hydraulic_requirements.append(backwater_depth)
        
        min_depth_hydraulic = max(hydraulic_requirements)
        
        # Overall recommended depth
        recommended_depth = max(
            min_depth_hydraulic * self.safety_factor,
            min_depth_sediment,
            min_depth_operation
        )
        
        return DepthRequirement(
            section_id=section.section_id,
            flow_rate=flow_rate,
            min_depth_hydraulic=min_depth_hydraulic,
            min_depth_sediment=min_depth_sediment,
            min_depth_operation=min_depth_operation,
            critical_depth=critical_depth,
            recommended_depth=recommended_depth,
            froude_number=froude_number,
            flow_regime=flow_regime
        )
    
    def calculate_channel_requirements(
        self,
        channel: Channel,
        flow_rate: float,
        check_transitions: bool = True
    ) -> Dict[str, DepthRequirement]:
        """
        Calculate minimum depths for all sections in a channel
        
        Args:
            channel: Channel with multiple sections
            flow_rate: Design flow rate
            check_transitions: Check for hydraulic jumps at transitions
        
        Returns:
            Dictionary of section_id -> DepthRequirement
        """
        requirements = {}
        upstream_depth = None
        
        for i, section in enumerate(channel.sections):
            req = self.calculate_section_requirements(
                section, flow_rate, upstream_depth
            )
            requirements[section.section_id] = req
            
            if check_transitions and i < len(channel.sections) - 1:
                # Check for potential hydraulic jump at transition
                next_section = channel.sections[i + 1]
                jump_location = self._check_hydraulic_jump(
                    section, next_section, flow_rate, req
                )
                if jump_location:
                    logger.warning(
                        f"Potential hydraulic jump between {section.section_id} "
                        f"and {next_section.section_id}"
                    )
            
            # Update upstream depth for next section
            upstream_depth = req.recommended_depth
        
        return requirements
    
    def calculate_gate_submergence_depth(
        self,
        gate_opening: float,
        flow_rate: float,
        channel_width: float,
        discharge_coefficient: float = 0.6
    ) -> float:
        """
        Calculate minimum downstream depth to ensure gate remains submerged
        
        Args:
            gate_opening: Gate opening height in meters
            flow_rate: Flow through gate in m³/s
            channel_width: Width of gate/channel in meters
            discharge_coefficient: Gate discharge coefficient
        
        Returns:
            Minimum required downstream depth
        """
        # For submerged flow, downstream depth should be > 0.67 * upstream depth
        # This ensures modular flow conditions
        
        # Calculate required upstream depth for free flow
        free_flow_area = gate_opening * channel_width
        free_flow_velocity = flow_rate / (discharge_coefficient * free_flow_area)
        upstream_depth = gate_opening + free_flow_velocity ** 2 / (2 * self.gravity)
        
        # Minimum downstream depth for submerged conditions
        min_downstream_depth = max(
            0.67 * upstream_depth,  # Submergence ratio
            gate_opening * 1.5,     # Physical clearance
            self.min_operational_depth  # Operational minimum
        )
        
        return min_downstream_depth
    
    def _calculate_critical_depth(
        self,
        flow_rate: float,
        bed_width: float,
        side_slope: float
    ) -> float:
        """Calculate critical depth for trapezoidal channel"""
        # For trapezoidal channel: Q²/g = A³/T
        # Where A = area, T = top width
        
        # Iterative solution
        depth = (flow_rate ** 2 / (self.gravity * bed_width ** 2)) ** (1/3)  # Initial guess
        
        for _ in range(20):
            area = self._calculate_area(depth, bed_width, side_slope)
            top_width = bed_width + 2 * side_slope * depth
            
            f = flow_rate ** 2 / self.gravity - area ** 3 / top_width
            
            if abs(f) < 1e-6:
                break
            
            # Derivatives
            dA_dy = bed_width + 2 * side_slope * depth
            dT_dy = 2 * side_slope
            df_dy = -3 * area ** 2 * dA_dy / top_width + area ** 3 * dT_dy / top_width ** 2
            
            depth = depth - f / df_dy
            depth = max(0.01, depth)
        
        return depth
    
    def _calculate_normal_depth(
        self,
        flow_rate: float,
        bed_width: float,
        side_slope: float,
        manning_n: float,
        slope: float
    ) -> float:
        """Calculate normal depth using Manning's equation"""
        if slope <= 0:
            slope = settings.min_bed_slope
            
        # Initial guess
        depth = (flow_rate * manning_n / (bed_width * slope ** 0.5)) ** 0.6
        
        # Newton-Raphson iteration
        for _ in range(20):
            area = self._calculate_area(depth, bed_width, side_slope)
            perimeter = self._calculate_wetted_perimeter(depth, bed_width, side_slope)
            hydraulic_radius = area / perimeter
            
            # Manning's equation
            calc_flow = (1/manning_n) * area * hydraulic_radius ** (2/3) * slope ** 0.5
            
            if abs(calc_flow - flow_rate) < 0.001:
                break
            
            # Derivatives
            dA_dy = bed_width + 2 * side_slope * depth
            dP_dy = 2 * np.sqrt(1 + side_slope ** 2)
            dR_dy = (dA_dy * perimeter - area * dP_dy) / perimeter ** 2
            dQ_dy = (1/manning_n) * slope ** 0.5 * (
                dA_dy * hydraulic_radius ** (2/3) +
                area * (2/3) * hydraulic_radius ** (-1/3) * dR_dy
            )
            
            depth = depth - (calc_flow - flow_rate) / dQ_dy
            depth = max(0.01, depth)
        
        return depth
    
    def _calculate_depth_for_min_velocity(
        self,
        flow_rate: float,
        bed_width: float,
        side_slope: float,
        min_velocity: float
    ) -> float:
        """Calculate depth required to maintain minimum velocity"""
        # Q = A * V, so A = Q / V
        required_area = flow_rate / min_velocity
        
        # For trapezoidal: A = y(b + zy)
        # Solve quadratic equation: zy² + by - A = 0
        if side_slope > 0:
            discriminant = bed_width ** 2 + 4 * side_slope * required_area
            depth = (-bed_width + np.sqrt(discriminant)) / (2 * side_slope)
        else:
            # Rectangular channel
            depth = required_area / bed_width
        
        return max(depth, self.min_operational_depth)
    
    def _estimate_backwater_depth(
        self,
        section: ChannelSection,
        flow_rate: float,
        downstream_depth: float
    ) -> float:
        """Estimate backwater effect using simplified approach"""
        # Simplified backwater calculation
        # More detailed calculation would use standard step method
        
        slope = abs(section.start_elevation - section.end_elevation) / section.length
        normal_depth = self._calculate_normal_depth(
            flow_rate, section.bed_width, section.side_slope,
            section.manning_n, slope
        )
        
        # If downstream depth > normal depth, backwater effect exists
        if downstream_depth > normal_depth:
            # Approximate backwater profile
            backwater_depth = downstream_depth * np.exp(-section.length / (1000 * downstream_depth))
            return max(backwater_depth, normal_depth)
        
        return normal_depth
    
    def _check_hydraulic_jump(
        self,
        upstream_section: ChannelSection,
        downstream_section: ChannelSection,
        flow_rate: float,
        upstream_req: DepthRequirement
    ) -> Optional[Tuple[str, float]]:
        """Check for potential hydraulic jump at section transition"""
        if upstream_req.flow_regime != "supercritical":
            return None
        
        # Calculate conjugate depth
        fr1 = upstream_req.froude_number
        y1 = upstream_req.recommended_depth
        
        # Simplified for rectangular section
        y2 = y1 / 2 * (np.sqrt(1 + 8 * fr1 ** 2) - 1)
        
        # Check if jump is likely
        downstream_slope = abs(
            downstream_section.start_elevation - downstream_section.end_elevation
        ) / downstream_section.length
        
        if downstream_slope < upstream_section.manning_n:  # Milder slope
            return ("transition", y2)
        
        return None
    
    def _calculate_area(self, depth: float, bed_width: float, side_slope: float) -> float:
        """Calculate flow area for trapezoidal channel"""
        return depth * (bed_width + side_slope * depth)
    
    def _calculate_wetted_perimeter(
        self, depth: float, bed_width: float, side_slope: float
    ) -> float:
        """Calculate wetted perimeter for trapezoidal channel"""
        return bed_width + 2 * depth * np.sqrt(1 + side_slope ** 2)
    
    def validate_depth_requirements(
        self,
        requirements: Dict[str, DepthRequirement],
        available_depths: Dict[str, float]
    ) -> Dict[str, List[str]]:
        """
        Validate if available depths meet requirements
        
        Returns:
            Dictionary of section_id -> list of warnings/errors
        """
        issues = {}
        
        for section_id, req in requirements.items():
            available = available_depths.get(section_id, 0)
            section_issues = []
            
            if available < req.recommended_depth:
                section_issues.append(
                    f"Insufficient depth: {available:.2f}m < {req.recommended_depth:.2f}m required"
                )
            
            if available < req.min_depth_sediment:
                section_issues.append(
                    f"Risk of sedimentation: velocity below {self.min_velocity:.1f} m/s"
                )
            
            if req.froude_number > 0.9 and req.froude_number < 1.1:
                section_issues.append("Flow near critical conditions - unstable")
            
            if section_issues:
                issues[section_id] = section_issues
        
        return issues
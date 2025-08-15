import numpy as np
from typing import List, Dict, Tuple, Optional
from ..models.channel import Channel, ChannelSection, FlowCondition, NetworkTopology
from ..models.optimization import ElevationFeasibility, ZoneDeliveryRequest
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)


class ElevationFeasibilityChecker:
    """Check if water can reach all zones by gravity from the source"""
    
    def __init__(self, network: NetworkTopology):
        self.network = network
        self.gravity = settings.gravity
        self.min_depth = settings.min_flow_depth
        self.safety_factor = settings.depth_safety_factor
        
    def check_zone_feasibility(
        self, 
        zone_id: str, 
        zone_elevation: float,
        required_flow: float,
        source_water_level: float = None
    ) -> ElevationFeasibility:
        """
        Check if a specific zone can receive water by gravity
        
        Args:
            zone_id: Zone identifier
            zone_elevation: Zone ground elevation in MSL meters
            required_flow: Required flow rate in m³/s
            source_water_level: Current source water level (if None, uses ground + min depth)
        
        Returns:
            ElevationFeasibility object with detailed results
        """
        if source_water_level is None:
            source_water_level = settings.source_elevation + self.min_depth * self.safety_factor
            
        # Find path from source to zone
        path = self._find_flow_path(self.network.source_node_id, zone_id)
        if not path:
            return ElevationFeasibility(
                zone_id=zone_id,
                is_feasible=False,
                min_required_source_level=float('inf'),
                available_head=0,
                total_head_loss=float('inf'),
                critical_sections=[],
                recommended_flow_rate=0,
                warnings=["No path found from source to zone"]
            )
        
        # Calculate head losses along path
        total_head_loss = 0
        critical_sections = []
        min_available_head = float('inf')
        
        current_elevation = source_water_level
        for i in range(len(path) - 1):
            channel = self._get_channel_between_nodes(path[i], path[i+1])
            if not channel:
                continue
                
            # Calculate head loss in channel
            channel_loss, section_heads = self._calculate_channel_head_loss(
                channel, required_flow, current_elevation
            )
            total_head_loss += channel_loss
            current_elevation -= channel_loss
            
            # Check for critical sections
            for section_id, head in section_heads.items():
                if head < self.min_depth * self.safety_factor:
                    critical_sections.append(section_id)
                min_available_head = min(min_available_head, head)
        
        # Calculate results
        available_head = current_elevation - zone_elevation
        is_feasible = available_head >= self.min_depth * self.safety_factor
        
        # Calculate minimum required source level
        min_required_source = zone_elevation + self.min_depth * self.safety_factor + total_head_loss
        
        # Determine recommended flow rate based on velocity constraints
        recommended_flow = self._calculate_recommended_flow(path, required_flow)
        
        warnings = []
        if not is_feasible:
            warnings.append(f"Insufficient head at zone. Available: {available_head:.2f}m, Required: {self.min_depth * self.safety_factor:.2f}m")
        if critical_sections:
            warnings.append(f"Critical sections with low head: {', '.join(critical_sections)}")
        if recommended_flow < required_flow:
            warnings.append(f"Recommended flow ({recommended_flow:.2f} m³/s) less than required ({required_flow:.2f} m³/s)")
            
        return ElevationFeasibility(
            zone_id=zone_id,
            is_feasible=is_feasible,
            min_required_source_level=min_required_source,
            available_head=available_head,
            total_head_loss=total_head_loss,
            critical_sections=critical_sections,
            recommended_flow_rate=recommended_flow,
            warnings=warnings
        )
    
    def check_all_zones_feasibility(
        self, 
        zone_requests: List[ZoneDeliveryRequest],
        source_water_level: Optional[float] = None
    ) -> List[ElevationFeasibility]:
        """Check feasibility for all zones"""
        results = []
        
        for request in zone_requests:
            zone_elevation = self._get_zone_elevation(request.zone_id)
            result = self.check_zone_feasibility(
                request.zone_id,
                zone_elevation,
                request.required_flow_rate,
                source_water_level
            )
            results.append(result)
            
        return results
    
    def _find_flow_path(self, start_node_id: str, end_zone_id: str) -> List[str]:
        """Find hydraulic path from source to zone using BFS"""
        from collections import deque
        
        visited = set()
        queue = deque([(start_node_id, [start_node_id])])
        
        while queue:
            current_node_id, path = queue.popleft()
            
            if current_node_id in visited:
                continue
                
            visited.add(current_node_id)
            
            # Check if we reached the target zone
            if self._node_serves_zone(current_node_id, end_zone_id):
                return path
            
            # Explore downstream nodes
            downstream_nodes = self.network.get_downstream_nodes(current_node_id)
            for next_node_id in downstream_nodes:
                if next_node_id not in visited:
                    queue.append((next_node_id, path + [next_node_id]))
        
        return []  # No path found
    
    def _get_channel_between_nodes(self, node1_id: str, node2_id: str) -> Optional[Channel]:
        """Get channel connecting two nodes"""
        node1 = next((n for n in self.network.nodes if n.node_id == node1_id), None)
        node2 = next((n for n in self.network.nodes if n.node_id == node2_id), None)
        
        if not node1 or not node2:
            return None
            
        for channel_id in node1.connected_channels:
            if channel_id in node2.connected_channels:
                return next((c for c in self.network.channels if c.channel_id == channel_id), None)
                
        return None
    
    def _calculate_channel_head_loss(
        self, 
        channel: Channel, 
        flow_rate: float,
        upstream_water_level: float
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate head loss through a channel using Manning's equation
        
        Returns:
            Total head loss and dict of section_id -> available head
        """
        total_loss = 0
        section_heads = {}
        current_water_level = upstream_water_level
        
        for section in channel.sections:
            # Calculate hydraulic parameters
            depth, velocity = self._manning_flow_depth(
                flow_rate,
                section.bed_width,
                section.side_slope,
                section.manning_n,
                self._calculate_slope(section)
            )
            
            # Calculate friction loss using Manning's equation
            hydraulic_radius = self._calculate_hydraulic_radius(
                depth, section.bed_width, section.side_slope
            )
            friction_slope = (section.manning_n * velocity / (hydraulic_radius ** (2/3))) ** 2
            friction_loss = friction_slope * section.length
            
            # Add minor losses (10% of friction losses as approximation)
            minor_loss = 0.1 * friction_loss
            
            section_loss = friction_loss + minor_loss
            total_loss += section_loss
            
            # Track water level
            current_water_level = current_water_level - section_loss - (section.start_elevation - section.end_elevation)
            section_heads[section.section_id] = current_water_level - section.end_elevation
            
        return total_loss, section_heads
    
    def _manning_flow_depth(
        self,
        flow_rate: float,
        bed_width: float,
        side_slope: float,
        manning_n: float,
        slope: float
    ) -> Tuple[float, float]:
        """
        Calculate flow depth using Manning's equation
        Iterative solution for trapezoidal channel
        """
        # Initial guess based on rectangular channel
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
                
            # Derivative for Newton-Raphson
            dA_dy = bed_width + 2 * side_slope * depth
            dP_dy = 2 * np.sqrt(1 + side_slope ** 2)
            dR_dy = (dA_dy * perimeter - area * dP_dy) / (perimeter ** 2)
            dQ_dy = (1/manning_n) * (dA_dy * hydraulic_radius ** (2/3) + 
                                     area * (2/3) * hydraulic_radius ** (-1/3) * dR_dy) * slope ** 0.5
            
            # Update depth
            depth = depth - (calc_flow - flow_rate) / dQ_dy
            depth = max(0.01, depth)  # Prevent negative depth
        
        velocity = flow_rate / area
        return depth, velocity
    
    def _calculate_area(self, depth: float, bed_width: float, side_slope: float) -> float:
        """Calculate flow area for trapezoidal channel"""
        return depth * (bed_width + side_slope * depth)
    
    def _calculate_wetted_perimeter(self, depth: float, bed_width: float, side_slope: float) -> float:
        """Calculate wetted perimeter for trapezoidal channel"""
        return bed_width + 2 * depth * np.sqrt(1 + side_slope ** 2)
    
    def _calculate_hydraulic_radius(self, depth: float, bed_width: float, side_slope: float) -> float:
        """Calculate hydraulic radius"""
        area = self._calculate_area(depth, bed_width, side_slope)
        perimeter = self._calculate_wetted_perimeter(depth, bed_width, side_slope)
        return area / perimeter
    
    def _calculate_slope(self, section: ChannelSection) -> float:
        """Calculate bed slope of a section"""
        return (section.start_elevation - section.end_elevation) / section.length
    
    def _calculate_recommended_flow(self, path: List[str], required_flow: float) -> float:
        """Calculate recommended flow based on velocity constraints"""
        min_recommended_flow = required_flow
        
        for i in range(len(path) - 1):
            channel = self._get_channel_between_nodes(path[i], path[i+1])
            if not channel:
                continue
                
            for section in channel.sections:
                # Check maximum velocity constraint
                max_flow_for_velocity = self._flow_for_max_velocity(
                    section, settings.max_flow_velocity
                )
                min_recommended_flow = min(min_recommended_flow, max_flow_for_velocity)
        
        return min_recommended_flow
    
    def _flow_for_max_velocity(self, section: ChannelSection, max_velocity: float) -> float:
        """Calculate maximum flow rate for given velocity constraint"""
        # Approximate using rectangular channel
        slope = self._calculate_slope(section)
        depth = (max_velocity * section.manning_n / slope ** 0.5) ** 1.5
        area = self._calculate_area(depth, section.bed_width, section.side_slope)
        return area * max_velocity
    
    def _get_zone_elevation(self, zone_id: str) -> float:
        """Get minimum elevation for a zone"""
        zone_key = zone_id.lower().replace("-", "_")
        if zone_key in settings.zone_elevations:
            return settings.zone_elevations[zone_key]["min"]
        return 220.0  # Default high elevation
    
    def _node_serves_zone(self, node_id: str, zone_id: str) -> bool:
        """Check if a node serves a specific zone"""
        # This would be implemented based on network topology
        # For now, simple name matching
        return zone_id.lower() in node_id.lower()
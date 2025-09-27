"""
Single section water delivery scenario builder
Focuses on delivering water to one section while considering canal volumes
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID

from ..core.models import Scenario, SectionDemand
from ..integrations.gis_client import GISClient
from ..integrations.flow_client import FlowMonitoringClient


class SingleSectionScenarioBuilder:
    """Build scenarios focused on single section water delivery"""
    
    def __init__(self, gis_client: GISClient, flow_client: FlowMonitoringClient):
        self.gis = gis_client
        self.flow = flow_client
    
    async def create_single_section_scenario(
        self,
        section_id: str,
        water_depth_cm: float,
        scenario_name: Optional[str] = None,
        base_date: Optional[datetime] = None,
        duration_days: int = 7
    ) -> Dict:
        """
        Create scenario for single section water delivery
        
        Args:
            section_id: Target section (e.g., "01-06-02-42")
            water_depth_cm: Required water depth in centimeters
            scenario_name: Optional scenario name
            base_date: Start date for simulation
            duration_days: Simulation duration
            
        Returns:
            Scenario configuration with delivery path details
        """
        if not scenario_name:
            scenario_name = f"Single Section Delivery: {section_id} ({water_depth_cm}cm)"
        
        if not base_date:
            base_date = datetime.now()
        
        # Get section details
        section_info = await self.gis.get_section_details(section_id)
        
        # Calculate water demand from depth
        area_hectares = section_info.get("area_hectares", 0)
        if not area_hectares:
            area_rai = section_info.get("area_rai", 0)
            area_hectares = area_rai / 6.25
        
        # Convert depth to volume: area (m²) × depth (m)
        area_m2 = area_hectares * 10000
        water_volume_m3 = area_m2 * (water_depth_cm / 100)
        
        # Get delivery path
        delivery_path = await self._trace_delivery_path(section_id)
        
        # Calculate canal volumes along path
        canal_volumes = await self._calculate_canal_volumes(delivery_path)
        
        # Total water needed = section demand + canal filling
        total_water_needed = water_volume_m3 + canal_volumes["total_volume_m3"]
        
        return {
            "scenario": {
                "name": scenario_name,
                "description": f"Deliver {water_depth_cm}cm to section {section_id}",
                "base_date": base_date,
                "duration_days": duration_days,
                "time_step_minutes": 60,  # Hourly steps
                "optimization_objective": "water_efficiency"
            },
            "target_section": {
                "section_id": section_id,
                "area_hectares": area_hectares,
                "water_depth_cm": water_depth_cm,
                "water_volume_m3": water_volume_m3,
                "delivery_gate": section_info.get("delivery_gate")
            },
            "delivery_path": delivery_path,
            "canal_volumes": canal_volumes,
            "total_water_required_m3": total_water_needed,
            "section_demands": [
                {
                    "section_id": section_id,
                    "week_number": 1,
                    "base_demand_m3": water_volume_m3,
                    "priority_override": 10.0,  # Highest priority
                    "delivery_window_hours": 24  # Deliver within 24 hours
                }
            ]
        }
    
    async def _trace_delivery_path(self, section_id: str) -> List[Dict]:
        """
        Trace water delivery path from source to section
        
        Returns:
            List of path segments with gates and canals
        """
        section_info = await self.gis.get_section_details(section_id)
        delivery_gate = section_info.get("delivery_gate")
        
        if not delivery_gate:
            raise ValueError(f"No delivery gate found for section {section_id}")
        
        # Get network topology
        topology = await self.gis.get_gate_network_topology()
        
        # Build adjacency for path finding
        adjacency = {}
        for edge in topology["edges"]:
            from_node = edge["from"]
            to_node = edge["to"]
            
            if from_node not in adjacency:
                adjacency[from_node] = []
            adjacency[from_node].append({
                "to": to_node,
                "canal_id": edge.get("canal_id"),
                "distance_km": edge.get("distance_km", 1.0)
            })
        
        # Find path from source to delivery gate
        sources = self._find_source_nodes(topology["nodes"])
        
        # Use BFS to find shortest path
        path = None
        for source in sources:
            candidate_path = self._find_path_bfs(adjacency, source, delivery_gate)
            if candidate_path and (not path or len(candidate_path) < len(path)):
                path = candidate_path
        
        if not path:
            raise ValueError(f"No path found from source to gate {delivery_gate}")
        
        # Convert path to detailed segments
        segments = []
        for i in range(len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            
            # Find edge details
            edge_info = None
            for edge in adjacency.get(from_node, []):
                if edge["to"] == to_node:
                    edge_info = edge
                    break
            
            segment = {
                "from": from_node,
                "to": to_node,
                "type": "canal" if not to_node.startswith("GATE") else "gate",
                "canal_id": edge_info.get("canal_id") if edge_info else None,
                "distance_km": edge_info.get("distance_km", 1.0) if edge_info else 1.0
            }
            
            segments.append(segment)
        
        return segments
    
    async def _calculate_canal_volumes(self, path_segments: List[Dict]) -> Dict:
        """
        Calculate water volumes needed to fill canals along path
        
        Returns:
            Canal volume details including total volume
        """
        volumes = []
        total_volume = 0.0
        total_distance = 0.0
        
        for segment in path_segments:
            if segment["type"] == "canal" and segment["canal_id"]:
                # Get canal properties
                try:
                    props = await self.flow.get_canal_properties(segment["canal_id"])
                    
                    # Calculate volume
                    length_m = props.get("length_km", segment["distance_km"]) * 1000
                    cross_section_area = props.get("cross_section_area_m2", 10.0)
                    
                    # Assume canal needs to be filled to operating depth
                    # This could be refined with actual water level data
                    operating_fill_ratio = 0.7  # 70% of full capacity
                    volume = length_m * cross_section_area * operating_fill_ratio
                    
                    volumes.append({
                        "canal_id": segment["canal_id"],
                        "from": segment["from"],
                        "to": segment["to"],
                        "length_km": props.get("length_km", segment["distance_km"]),
                        "cross_section_m2": cross_section_area,
                        "volume_m3": volume
                    })
                    
                    total_volume += volume
                    total_distance += props.get("length_km", segment["distance_km"])
                    
                except Exception as e:
                    # Use default estimates if canal properties not available
                    length_km = segment["distance_km"]
                    default_area = 10.0  # m²
                    volume = length_km * 1000 * default_area * 0.7
                    
                    volumes.append({
                        "canal_id": segment["canal_id"],
                        "from": segment["from"],
                        "to": segment["to"],
                        "length_km": length_km,
                        "cross_section_m2": default_area,
                        "volume_m3": volume,
                        "estimated": True
                    })
                    
                    total_volume += volume
                    total_distance += length_km
        
        return {
            "canal_segments": volumes,
            "total_volume_m3": total_volume,
            "total_distance_km": total_distance,
            "travel_time_hours": self._estimate_travel_time(total_distance)
        }
    
    def _find_source_nodes(self, nodes: List[Dict]) -> List[str]:
        """Find water source nodes (reservoirs, main canals)"""
        sources = []
        for node in nodes:
            if node["type"] in ["reservoir", "source", "main_canal"]:
                sources.append(node["id"])
        return sources
    
    def _find_path_bfs(self, adjacency: Dict, start: str, end: str) -> Optional[List[str]]:
        """Find shortest path using breadth-first search"""
        from collections import deque
        
        if start == end:
            return [start]
        
        visited = {start}
        queue = deque([(start, [start])])
        
        while queue:
            node, path = queue.popleft()
            
            for neighbor in adjacency.get(node, []):
                next_node = neighbor["to"]
                if next_node not in visited:
                    visited.add(next_node)
                    new_path = path + [next_node]
                    
                    if next_node == end:
                        return new_path
                    
                    queue.append((next_node, new_path))
        
        return None
    
    def _estimate_travel_time(self, distance_km: float) -> float:
        """
        Estimate water travel time based on distance
        
        Assumes average flow velocity of 0.5-1.0 m/s in canals
        """
        avg_velocity_ms = 0.75  # m/s
        avg_velocity_kmh = avg_velocity_ms * 3.6  # km/h
        
        return distance_km / avg_velocity_kmh
    
    async def create_zero_demand_overrides(
        self,
        scenario_id: UUID,
        exclude_section: str,
        zone_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Create zero demand overrides for all sections except target
        
        Args:
            scenario_id: Scenario ID to attach demands to
            exclude_section: Section to exclude (has actual demand)
            zone_id: Optional zone to limit scope
            
        Returns:
            List of demand configurations with zero demand
        """
        # Get all sections
        if zone_id:
            sections = await self.gis.get_sections_in_zone(zone_id)
        else:
            # Get all zones and their sections
            sections = []
            for zone in range(1, 10):  # Adjust range as needed
                try:
                    zone_sections = await self.gis.get_sections_in_zone(zone)
                    sections.extend(zone_sections)
                except Exception:
                    break
        
        # Create zero demands for all except target
        zero_demands = []
        for section in sections:
            section_id = section["section_id"]
            if section_id != exclude_section:
                zero_demands.append({
                    "section_id": section_id,
                    "week_number": 1,
                    "base_demand_m3": 0,
                    "priority_override": 0,
                    "min_delivery_m3": 0,
                    "max_delivery_m3": 0
                })
        
        return zero_demands
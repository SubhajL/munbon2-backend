"""
Flow simulation service for hydraulic network calculations
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from collections import defaultdict

from src.clients.flow_client import FlowMonitoringClient
from src.clients.gis_client import GISClient

logger = logging.getLogger(__name__)


@dataclass
class HydraulicNode:
    """Represents a hydraulic node in the network"""
    node_id: str
    node_type: str  # 'gate', 'junction', 'reservoir', 'demand_point'
    elevation_m: float
    storage_area_m2: Optional[float] = None
    initial_level_m: float = 0.0
    min_level_m: float = 0.0
    max_level_m: float = 10.0
    

@dataclass
class HydraulicLink:
    """Represents a hydraulic link (canal/channel)"""
    link_id: str
    from_node: str
    to_node: str
    length_m: float
    manning_n: float = 0.025
    bed_slope: float = 0.0001
    cross_section_area_m2: float = 10.0
    wetted_perimeter_m: float = 8.0
    

class FlowSimulator:
    """Simulates hydraulic flow through irrigation network"""
    
    def __init__(
        self,
        flow_client: FlowMonitoringClient,
        gis_client: GISClient
    ):
        self.flow = flow_client
        self.gis = gis_client
        
        # Network representation
        self.nodes: Dict[str, HydraulicNode] = {}
        self.links: Dict[str, HydraulicLink] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)
        
        # Simulation state
        self.water_levels: Dict[str, float] = {}
        self.flows: Dict[str, float] = {}
        self.gate_flows: Dict[str, float] = {}
        
    async def initialize_network(self, topology: Dict[str, Any]) -> None:
        """Initialize hydraulic network from topology"""
        # Create nodes
        for node_data in topology.get("nodes", []):
            node = HydraulicNode(
                node_id=node_data["id"],
                node_type=node_data["type"],
                elevation_m=node_data.get("elevation", 0),
                storage_area_m2=node_data.get("storage_area", 1000),
                initial_level_m=node_data.get("initial_level", 2.0)
            )
            self.nodes[node.node_id] = node
            self.water_levels[node.node_id] = node.initial_level_m
        
        # Create links
        for edge_data in topology.get("edges", []):
            # Get canal properties
            canal_props = await self.flow.get_canal_properties(
                edge_data.get("canal_id", "DEFAULT")
            )
            
            link = HydraulicLink(
                link_id=edge_data.get("canal_id", f"{edge_data['from']}-{edge_data['to']}"),
                from_node=edge_data["from"],
                to_node=edge_data["to"],
                length_m=canal_props.get("length_km", 1) * 1000,
                manning_n=canal_props.get("manning_n", 0.025),
                bed_slope=canal_props.get("bed_slope", 0.0001),
                cross_section_area_m2=canal_props.get("cross_section_area_m2", 10),
                wetted_perimeter_m=canal_props.get("wetted_perimeter_m", 8)
            )
            
            self.links[link.link_id] = link
            self.adjacency[link.from_node].append(link.to_node)
    
    async def simulate_network_flow(
        self,
        gate_positions: Dict[str, float],
        external_inflows: Dict[str, float],
        demands: Dict[str, float],
        time_step_seconds: float = 3600
    ) -> Dict[str, Any]:
        """Simulate flow through entire network"""
        # Calculate gate flows
        await self._calculate_gate_flows(gate_positions)
        
        # Solve network flow balance
        self._solve_network_flows(external_inflows, demands)
        
        # Update water levels
        self._update_water_levels(time_step_seconds)
        
        # Check constraints
        violations = self._check_constraints()
        
        return {
            "water_levels": dict(self.water_levels),
            "flows": dict(self.flows),
            "gate_flows": dict(self.gate_flows),
            "constraint_violations": violations,
            "mass_balance_error": self._calculate_mass_balance_error()
        }
    
    async def _calculate_gate_flows(self, gate_positions: Dict[str, float]) -> None:
        """Calculate flow through all gates"""
        for gate_id, opening in gate_positions.items():
            if gate_id in self.nodes:
                # Find upstream and downstream nodes
                upstream_nodes = [n for n, adj in self.adjacency.items() if gate_id in adj]
                downstream_nodes = self.adjacency.get(gate_id, [])
                
                if upstream_nodes and downstream_nodes:
                    upstream_level = self.water_levels.get(upstream_nodes[0], 0)
                    downstream_level = self.water_levels.get(downstream_nodes[0], 0)
                    
                    # Calculate gate flow
                    flow_data = await self.flow.calculate_gate_flow(
                        gate_id, opening, upstream_level, downstream_level
                    )
                    
                    self.gate_flows[gate_id] = flow_data["flow_m3s"]
    
    def _solve_network_flows(
        self,
        external_inflows: Dict[str, float],
        demands: Dict[str, float]
    ) -> None:
        """Solve steady-state flow balance in network"""
        # Initialize flows
        self.flows = {}
        
        # Simple approach: distribute flow based on continuity
        # In production, use more sophisticated hydraulic solver
        
        # Process network from upstream to downstream
        processed = set()
        to_process = self._find_source_nodes()
        
        while to_process:
            node_id = to_process.pop(0)
            if node_id in processed:
                continue
            
            processed.add(node_id)
            
            # Calculate node balance
            inflow = self._calculate_node_inflow(node_id, external_inflows)
            outflow_demand = demands.get(node_id, 0)
            
            # Distribute to downstream nodes
            downstream = self.adjacency.get(node_id, [])
            if downstream:
                available_flow = max(0, inflow - outflow_demand)
                flow_per_link = available_flow / len(downstream) if downstream else 0
                
                for ds_node in downstream:
                    link_id = f"{node_id}-{ds_node}"
                    self.flows[link_id] = flow_per_link
                    
                    if ds_node not in processed:
                        to_process.append(ds_node)
    
    def _update_water_levels(self, time_step_seconds: float) -> None:
        """Update water levels based on flow balance"""
        new_levels = {}
        
        for node_id, node in self.nodes.items():
            if node.storage_area_m2 and node.storage_area_m2 > 0:
                # Calculate net flow
                inflow = self._calculate_total_inflow(node_id)
                outflow = self._calculate_total_outflow(node_id)
                net_flow = inflow - outflow
                
                # Update level based on continuity
                volume_change = net_flow * time_step_seconds
                level_change = volume_change / node.storage_area_m2
                
                new_level = self.water_levels[node_id] + level_change
                
                # Apply constraints
                new_level = max(node.min_level_m, min(node.max_level_m, new_level))
                new_levels[node_id] = new_level
            else:
                # Non-storage node, maintain level
                new_levels[node_id] = self.water_levels.get(node_id, 0)
        
        self.water_levels = new_levels
    
    def _calculate_node_inflow(
        self,
        node_id: str,
        external_inflows: Dict[str, float]
    ) -> float:
        """Calculate total inflow to a node"""
        inflow = external_inflows.get(node_id, 0)
        
        # Add inflows from upstream links
        for link_id, link in self.links.items():
            if link.to_node == node_id:
                inflow += self.flows.get(link_id, 0)
        
        # Add gate inflows
        if node_id in self.gate_flows:
            inflow += self.gate_flows[node_id]
        
        return inflow
    
    def _calculate_total_inflow(self, node_id: str) -> float:
        """Calculate total inflow including all sources"""
        return self._calculate_node_inflow(node_id, {})
    
    def _calculate_total_outflow(self, node_id: str) -> float:
        """Calculate total outflow from a node"""
        outflow = 0
        
        # Outflows to downstream links
        for link_id, link in self.links.items():
            if link.from_node == node_id:
                outflow += self.flows.get(link_id, 0)
        
        # Gate outflows
        for gate_id, flow in self.gate_flows.items():
            if gate_id == node_id:
                outflow += flow
        
        return outflow
    
    def _find_source_nodes(self) -> List[str]:
        """Find source nodes (no incoming edges)"""
        has_incoming = set()
        for link in self.links.values():
            has_incoming.add(link.to_node)
        
        return [n for n in self.nodes if n not in has_incoming]
    
    def _check_constraints(self) -> List[Dict[str, Any]]:
        """Check for constraint violations"""
        violations = []
        
        # Check water level constraints
        for node_id, node in self.nodes.items():
            level = self.water_levels[node_id]
            
            if level < node.min_level_m:
                violations.append({
                    "type": "min_level",
                    "node_id": node_id,
                    "current": level,
                    "limit": node.min_level_m
                })
            elif level > node.max_level_m:
                violations.append({
                    "type": "max_level",
                    "node_id": node_id,
                    "current": level,
                    "limit": node.max_level_m
                })
        
        # Check flow capacity constraints
        for link_id, link in self.links.items():
            flow = self.flows.get(link_id, 0)
            
            # Calculate capacity using Manning's equation
            hydraulic_radius = link.cross_section_area_m2 / link.wetted_perimeter_m
            capacity = (1/link.manning_n) * link.cross_section_area_m2 * \
                      (hydraulic_radius ** (2/3)) * (link.bed_slope ** 0.5)
            
            if flow > capacity:
                violations.append({
                    "type": "flow_capacity",
                    "link_id": link_id,
                    "current": flow,
                    "capacity": capacity
                })
        
        return violations
    
    def _calculate_mass_balance_error(self) -> float:
        """Calculate overall mass balance error"""
        total_inflow = sum(self.flows.values())
        total_outflow = sum(self.gate_flows.values())
        
        if total_inflow > 0:
            return abs(total_inflow - total_outflow) / total_inflow
        return 0.0
    
    async def simulate_transient_flow(
        self,
        initial_conditions: Dict[str, float],
        gate_schedule: List[Tuple[float, Dict[str, float]]],
        simulation_duration_hours: float,
        time_step_seconds: float = 60
    ) -> List[Dict[str, Any]]:
        """Simulate transient (time-varying) flow conditions"""
        results = []
        
        # Set initial conditions
        self.water_levels = initial_conditions.copy()
        
        # Convert schedule to dict for efficient lookup
        schedule_dict = {t: gates for t, gates in gate_schedule}
        schedule_times = sorted(schedule_dict.keys())
        
        current_time = 0
        current_gates = schedule_dict.get(0, {})
        next_schedule_idx = 1
        
        while current_time < simulation_duration_hours * 3600:
            # Update gate positions if scheduled
            if (next_schedule_idx < len(schedule_times) and 
                current_time >= schedule_times[next_schedule_idx] * 3600):
                current_gates = schedule_dict[schedule_times[next_schedule_idx]]
                next_schedule_idx += 1
            
            # Simulate one time step
            step_result = await self.simulate_network_flow(
                current_gates,
                {},  # No external inflows for now
                {},  # No demands for now
                time_step_seconds
            )
            
            step_result["time_hours"] = current_time / 3600
            results.append(step_result)
            
            current_time += time_step_seconds
        
        return results
    
    def calculate_travel_time(
        self,
        from_node: str,
        to_node: str,
        flow_velocity_ms: float = 1.0
    ) -> Optional[float]:
        """Calculate water travel time between nodes"""
        # Simple BFS to find path
        visited = set()
        queue = [(from_node, 0)]
        
        while queue:
            node, distance = queue.pop(0)
            
            if node == to_node:
                return distance / flow_velocity_ms / 3600  # Convert to hours
            
            if node in visited:
                continue
            
            visited.add(node)
            
            for next_node in self.adjacency.get(node, []):
                if next_node not in visited:
                    # Find link
                    link = None
                    for l in self.links.values():
                        if l.from_node == node and l.to_node == next_node:
                            link = l
                            break
                    
                    if link:
                        queue.append((next_node, distance + link.length_m))
        
        return None
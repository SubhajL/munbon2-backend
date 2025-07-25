"""
Contingency routing system for blocked or failed paths
Finds alternative routes when primary paths are unavailable
"""

import networkx as nx
from typing import List, Dict, Set, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class BlockageType(Enum):
    GATE_FAILURE = "gate_failure"
    CHANNEL_BLOCKAGE = "channel_blockage"
    MAINTENANCE = "maintenance"
    SEDIMENT = "sediment"
    STRUCTURAL_DAMAGE = "structural_damage"

@dataclass
class Blockage:
    location: str
    type: BlockageType
    severity: float  # 0-1 (0 = minor, 1 = complete blockage)
    estimated_duration_hours: float
    affected_segments: List[str]

@dataclass
class AlternativeRoute:
    route_id: str
    path: List[str]
    total_length_m: float
    elevation_change_m: float
    capacity_m3s: float
    efficiency_ratio: float  # vs primary route
    required_gate_operations: List[Dict[str, str]]
    feasibility_score: float

class ContingencyRouter:
    def __init__(self):
        # Build network graph
        self.network = self._build_network_graph()
        
        # Primary routes (normal operation)
        self.primary_routes = {
            "Zone_1": ["Source", "M(0,0)", "M(0,1)", "Zone_1"],
            "Zone_2": ["Source", "M(0,0)", "M(0,2)", "Zone_2"],
            "Zone_3": ["Source", "M(0,0)", "M(0,3)", "Zone_3"],
            "Zone_4": ["Source", "M(0,0)", "M(0,4)", "Zone_4"],
            "Zone_5": ["Source", "M(0,0)", "M(0,5)", "Zone_5"],
            "Zone_6": ["Source", "M(0,0)", "M(0,6)", "Zone_6"]
        }
        
        # Cross-connections (emergency use)
        self.cross_connections = {
            ("M(0,2)", "M(0,3)"): {"capacity": 1.5, "normally_closed": True},
            ("M(0,4)", "M(0,5)"): {"capacity": 1.0, "normally_closed": True},
            ("Zone_2", "Zone_3"): {"capacity": 0.8, "normally_closed": True},
            ("Zone_5", "Zone_6"): {"capacity": 0.8, "normally_closed": True}
        }
    
    def _build_network_graph(self) -> nx.DiGraph:
        """Build directed graph of canal network"""
        
        G = nx.DiGraph()
        
        # Add main distribution channels
        main_edges = [
            ("Source", "M(0,0)", {"capacity": 10.0, "length": 500}),
            ("M(0,0)", "M(0,1)", {"capacity": 4.0, "length": 1000}),
            ("M(0,0)", "M(0,2)", {"capacity": 4.0, "length": 1200}),
            ("M(0,0)", "M(0,3)", {"capacity": 3.5, "length": 1500}),
            ("M(0,0)", "M(0,4)", {"capacity": 3.5, "length": 1800}),
            ("M(0,0)", "M(0,5)", {"capacity": 3.0, "length": 2000}),
            ("M(0,0)", "M(0,6)", {"capacity": 3.0, "length": 2200}),
        ]
        
        # Add zone connections
        zone_edges = [
            ("M(0,1)", "Zone_1", {"capacity": 3.5, "length": 800}),
            ("M(0,2)", "Zone_2", {"capacity": 3.5, "length": 800}),
            ("M(0,3)", "Zone_3", {"capacity": 3.0, "length": 1000}),
            ("M(0,4)", "Zone_4", {"capacity": 3.0, "length": 1000}),
            ("M(0,5)", "Zone_5", {"capacity": 2.5, "length": 1200}),
            ("M(0,6)", "Zone_6", {"capacity": 2.5, "length": 1200}),
        ]
        
        G.add_edges_from(main_edges)
        G.add_edges_from(zone_edges)
        
        # Add node attributes (elevations)
        elevations = {
            "Source": 221.0,
            "M(0,0)": 220.9,
            "M(0,1)": 220.7,
            "M(0,2)": 220.7,
            "M(0,3)": 220.5,
            "M(0,4)": 220.3,
            "M(0,5)": 220.2,
            "M(0,6)": 220.1,
            "Zone_1": 219.0,
            "Zone_2": 217.5,
            "Zone_3": 217.0,
            "Zone_4": 216.5,
            "Zone_5": 215.5,
            "Zone_6": 215.5
        }
        
        nx.set_node_attributes(G, elevations, "elevation")
        
        return G
    
    def find_alternative_routes(
        self,
        source: str,
        destination: str,
        blockages: List[Blockage],
        required_flow_m3s: float
    ) -> List[AlternativeRoute]:
        """Find alternative routes avoiding blockages"""
        
        # Create modified graph with blockages
        working_graph = self._create_working_graph(blockages)
        
        # Add cross-connections if needed
        self._add_emergency_connections(working_graph)
        
        # Find all simple paths
        try:
            all_paths = list(nx.all_simple_paths(
                working_graph,
                source,
                destination,
                cutoff=10  # Max path length
            ))
        except nx.NetworkXNoPath:
            logger.warning(f"No path found from {source} to {destination}")
            return []
        
        # Evaluate each path
        alternatives = []
        for path in all_paths:
            route = self._evaluate_route(path, required_flow_m3s, working_graph)
            if route and route.feasibility_score > 0.5:
                alternatives.append(route)
        
        # Sort by feasibility score
        alternatives.sort(key=lambda x: x.feasibility_score, reverse=True)
        
        return alternatives[:5]  # Return top 5 alternatives
    
    def _create_working_graph(self, blockages: List[Blockage]) -> nx.DiGraph:
        """Create graph with blockages applied"""
        
        working_graph = self.network.copy()
        
        for blockage in blockages:
            if blockage.type == BlockageType.GATE_FAILURE:
                # Remove edges through failed gate
                for segment in blockage.affected_segments:
                    if "->" in segment:
                        parts = segment.split("->")
                        if working_graph.has_edge(parts[0], parts[1]):
                            if blockage.severity >= 1.0:
                                working_graph.remove_edge(parts[0], parts[1])
                            else:
                                # Reduce capacity
                                current_capacity = working_graph[parts[0]][parts[1]]['capacity']
                                new_capacity = current_capacity * (1 - blockage.severity)
                                working_graph[parts[0]][parts[1]]['capacity'] = new_capacity
            
            elif blockage.type == BlockageType.CHANNEL_BLOCKAGE:
                # Similar to gate failure
                for segment in blockage.affected_segments:
                    if "->" in segment:
                        parts = segment.split("->")
                        if working_graph.has_edge(parts[0], parts[1]):
                            if blockage.severity >= 0.8:
                                working_graph.remove_edge(parts[0], parts[1])
                            else:
                                current_capacity = working_graph[parts[0]][parts[1]]['capacity']
                                new_capacity = current_capacity * (1 - blockage.severity)
                                working_graph[parts[0]][parts[1]]['capacity'] = new_capacity
        
        return working_graph
    
    def _add_emergency_connections(self, graph: nx.DiGraph):
        """Add emergency cross-connections to graph"""
        
        for (node1, node2), props in self.cross_connections.items():
            if not graph.has_edge(node1, node2):
                # Estimate length based on node positions
                length = 1500  # Default emergency connection length
                graph.add_edge(
                    node1,
                    node2,
                    capacity=props['capacity'],
                    length=length,
                    emergency=True
                )
    
    def _evaluate_route(
        self,
        path: List[str],
        required_flow_m3s: float,
        graph: nx.DiGraph
    ) -> Optional[AlternativeRoute]:
        """Evaluate feasibility and efficiency of a route"""
        
        if len(path) < 2:
            return None
        
        # Calculate route properties
        total_length = 0
        min_capacity = float('inf')
        gate_operations = []
        uses_emergency = False
        
        for i in range(len(path) - 1):
            if graph.has_edge(path[i], path[i+1]):
                edge_data = graph[path[i]][path[i+1]]
                total_length += edge_data.get('length', 1000)
                min_capacity = min(min_capacity, edge_data.get('capacity', 0))
                
                if edge_data.get('emergency', False):
                    uses_emergency = True
                    gate_operations.append({
                        "gate_id": f"{path[i]}->{path[i+1]}",
                        "action": "open_emergency",
                        "normal_state": "closed"
                    })
                else:
                    gate_operations.append({
                        "gate_id": f"{path[i]}->{path[i+1]}",
                        "action": "open",
                        "normal_state": "open"
                    })
        
        # Check capacity constraint
        if min_capacity < required_flow_m3s:
            return None
        
        # Calculate elevation change
        start_elev = graph.nodes[path[0]].get('elevation', 220)
        end_elev = graph.nodes[path[-1]].get('elevation', 215)
        elevation_change = start_elev - end_elev
        
        # Calculate efficiency vs primary route
        primary_path = self.primary_routes.get(path[-1], [])
        if primary_path:
            primary_length = sum(
                graph[primary_path[i]][primary_path[i+1]].get('length', 1000)
                for i in range(len(primary_path) - 1)
                if graph.has_edge(primary_path[i], primary_path[i+1])
            )
            efficiency_ratio = primary_length / total_length if total_length > 0 else 0
        else:
            efficiency_ratio = 0.8  # Default
        
        # Calculate feasibility score
        feasibility_score = self._calculate_feasibility_score(
            min_capacity,
            required_flow_m3s,
            elevation_change,
            efficiency_ratio,
            uses_emergency
        )
        
        route_id = "->".join(path)
        
        return AlternativeRoute(
            route_id=route_id,
            path=path,
            total_length_m=total_length,
            elevation_change_m=elevation_change,
            capacity_m3s=min_capacity,
            efficiency_ratio=efficiency_ratio,
            required_gate_operations=gate_operations,
            feasibility_score=feasibility_score
        )
    
    def _calculate_feasibility_score(
        self,
        capacity: float,
        required_flow: float,
        elevation_change: float,
        efficiency_ratio: float,
        uses_emergency: bool
    ) -> float:
        """Calculate route feasibility score"""
        
        score = 1.0
        
        # Capacity score
        capacity_ratio = capacity / required_flow if required_flow > 0 else 1
        if capacity_ratio < 1:
            score *= capacity_ratio
        elif capacity_ratio > 2:
            score *= 0.95  # Slight penalty for oversized route
        
        # Elevation score (prefer gravity flow)
        if elevation_change < 0:
            score *= 0.5  # Major penalty for uphill flow
        elif elevation_change < 1:
            score *= 0.8  # Small penalty for minimal drop
        
        # Efficiency score
        score *= efficiency_ratio
        
        # Emergency connection penalty
        if uses_emergency:
            score *= 0.7
        
        return max(0, min(1, score))
    
    def simulate_blockage_impact(
        self,
        blockages: List[Blockage],
        current_deliveries: Dict[str, float]
    ) -> Dict[str, Dict[str, any]]:
        """Simulate impact of blockages on current deliveries"""
        
        impact_analysis = {}
        
        for zone, required_flow in current_deliveries.items():
            # Find alternatives
            alternatives = self.find_alternative_routes(
                "Source",
                zone,
                blockages,
                required_flow
            )
            
            if alternatives:
                best_alternative = alternatives[0]
                impact = "manageable"
                recovery_time = 2.0  # hours to switch routes
            else:
                best_alternative = None
                impact = "severe"
                recovery_time = float('inf')
            
            impact_analysis[zone] = {
                "impact_level": impact,
                "alternative_available": best_alternative is not None,
                "best_alternative": best_alternative,
                "recovery_time_hours": recovery_time,
                "flow_reduction_percent": 0 if best_alternative else 100
            }
        
        return impact_analysis
    
    def generate_emergency_protocol(
        self,
        blockage: Blockage
    ) -> Dict[str, any]:
        """Generate emergency response protocol for a blockage"""
        
        protocol = {
            "blockage_id": f"BLK-{blockage.location}-{blockage.type.value}",
            "severity": blockage.severity,
            "immediate_actions": [],
            "gate_adjustments": [],
            "notification_list": [],
            "estimated_resolution": blockage.estimated_duration_hours
        }
        
        # Immediate actions based on blockage type
        if blockage.type == BlockageType.GATE_FAILURE:
            protocol["immediate_actions"].extend([
                "Dispatch maintenance team to failed gate",
                "Switch to manual operation if possible",
                "Open upstream emergency spillway if needed"
            ])
            protocol["notification_list"].extend([
                "Gate maintenance supervisor",
                "Affected zone managers",
                "Control room operators"
            ])
        
        elif blockage.type == BlockageType.CHANNEL_BLOCKAGE:
            protocol["immediate_actions"].extend([
                "Assess blockage extent using drone/visual inspection",
                "Reduce upstream flows to prevent overflow",
                "Prepare excavation equipment if needed"
            ])
            protocol["notification_list"].extend([
                "Channel maintenance team",
                "Emergency response coordinator",
                "Downstream users"
            ])
        
        # Find affected zones
        affected_zones = self._find_affected_zones(blockage)
        
        # Generate gate adjustments
        for zone in affected_zones:
            alternatives = self.find_alternative_routes(
                "Source",
                zone,
                [blockage],
                2.0  # Assume moderate flow requirement
            )
            
            if alternatives:
                for gate_op in alternatives[0].required_gate_operations:
                    protocol["gate_adjustments"].append(gate_op)
        
        return protocol
    
    def _find_affected_zones(self, blockage: Blockage) -> List[str]:
        """Find zones affected by a blockage"""
        
        affected = []
        
        for zone, primary_path in self.primary_routes.items():
            # Check if blockage affects primary path
            for segment in blockage.affected_segments:
                if "->" in segment:
                    parts = segment.split("->")
                    for i in range(len(primary_path) - 1):
                        if (primary_path[i] == parts[0] and 
                            primary_path[i+1] == parts[1]):
                            affected.append(zone)
                            break
        
        return affected
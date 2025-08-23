"""
Delivery Path Optimizer Service
Implements graph-based algorithms for optimal water delivery routing
"""

import json
import heapq
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
import networkx as nx
from datetime import datetime, timedelta

from core import get_logger
from config import settings
from db import DatabaseManager

logger = get_logger(__name__)


@dataclass
class Node:
    """Represents a node in the delivery network"""
    id: str
    type: str  # 'source', 'gate', 'junction', 'section'
    elevation_m: float
    max_flow_m3s: Optional[float] = None
    current_flow_m3s: Optional[float] = None
    location: Optional[Dict[str, float]] = None


@dataclass
class Edge:
    """Represents an edge (canal/pipe) in the delivery network"""
    from_node: str
    to_node: str
    distance_km: float
    capacity_m3s: float
    loss_rate: float = 0.02  # 2% per km default
    flow_velocity_ms: float = 1.5  # m/s default


class DeliveryOptimizer:
    """Optimizes water delivery paths using graph algorithms"""
    
    def __init__(self):
        self.logger = logger.bind(service="delivery_optimizer")
        self.db = DatabaseManager()
        self.network = nx.DiGraph()
        self._network_loaded = False
        self._flow_monitoring_data = None
    
    async def load_network(self, force_reload: bool = False) -> bool:
        """Load canal network from Flow Monitoring Service data"""
        if self._network_loaded and not force_reload:
            return True
        
        try:
            # Load network data from file
            network_file = settings.flow_monitoring_network_file
            if not network_file:
                network_file = "/Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring/src/munbon_network_final.json"
            
            with open(network_file, 'r') as f:
                network_data = json.load(f)
            
            self._flow_monitoring_data = network_data
            
            # Build NetworkX graph
            self._build_network_graph(network_data)
            
            self._network_loaded = True
            self.logger.info(
                "Network loaded successfully",
                nodes=self.network.number_of_nodes(),
                edges=self.network.number_of_edges()
            )
            return True
            
        except Exception as e:
            self.logger.error("Failed to load network", error=str(e))
            return False
    
    def _build_network_graph(self, network_data: Dict) -> None:
        """Build NetworkX graph from network data"""
        self.network.clear()
        
        # Add nodes (gates)
        for gate in network_data.get("gates", []):
            node_data = {
                'type': 'gate',
                'name': gate.get('name', ''),
                'gate_type': gate.get('type', 'unknown'),
                'elevation_m': gate.get('elevation', 0),
                'max_flow_m3s': gate.get('max_flow', 10),
                'current_flow_m3s': gate.get('current_flow', 0),
                'location': {
                    'lat': gate.get('coordinates', {}).get('lat', 0),
                    'lon': gate.get('coordinates', {}).get('lon', 0)
                }
            }
            
            # Add special attributes for source/terminus nodes
            if gate.get('id') == 'M(0,0)':
                node_data['type'] = 'source'
            elif 'Zone_' in gate.get('name', ''):
                node_data['type'] = 'section'
            
            self.network.add_node(gate['id'], **node_data)
        
        # Add edges (connections)
        for conn in network_data.get("connections", []):
            from_id = conn['from']
            to_id = conn['to']
            
            # Calculate edge attributes
            from_node = next((g for g in network_data['gates'] if g['id'] == from_id), None)
            to_node = next((g for g in network_data['gates'] if g['id'] == to_id), None)
            
            if from_node and to_node:
                # Estimate distance (simplified - should use actual canal length)
                distance_km = self._calculate_distance(
                    from_node['coordinates']['lat'],
                    from_node['coordinates']['lon'],
                    to_node['coordinates']['lat'],
                    to_node['coordinates']['lon']
                )
                
                # Capacity is minimum of gate capacities
                capacity = min(
                    from_node.get('max_flow', 10),
                    to_node.get('max_flow', 10)
                )
                
                # Calculate weight based on distance and elevation
                elevation_diff = from_node.get('elevation', 0) - to_node.get('elevation', 0)
                
                # Penalize uphill flow
                weight = distance_km
                if elevation_diff < 0:  # Uphill
                    weight *= 2.0
                
                self.network.add_edge(
                    from_id,
                    to_id,
                    distance_km=distance_km,
                    capacity_m3s=capacity,
                    weight=weight,
                    elevation_diff=elevation_diff,
                    loss_rate=0.02  # 2% per km
                )
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    async def find_optimal_path(
        self,
        source: str,
        target: str,
        volume_m3: float,
        constraints: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Find optimal delivery path using Dijkstra's algorithm"""
        if not self._network_loaded:
            await self.load_network()
        
        if source not in self.network or target not in self.network:
            self.logger.error(
                "Source or target not in network",
                source=source,
                target=target
            )
            return None
        
        try:
            # Apply constraints if provided
            if constraints:
                working_graph = self._apply_constraints(constraints)
            else:
                working_graph = self.network
            
            # Find shortest path
            path = nx.shortest_path(
                working_graph,
                source=source,
                target=target,
                weight='weight'
            )
            
            # Calculate path metrics
            metrics = self._calculate_path_metrics(path, volume_m3)
            
            return {
                "path": path,
                "nodes": len(path),
                "total_distance_km": metrics["distance"],
                "travel_time_hours": metrics["travel_time"],
                "delivery_time_hours": metrics["delivery_time"],
                "expected_loss_m3": metrics["loss_m3"],
                "loss_percent": metrics["loss_percent"],
                "feasible": metrics["feasible"],
                "bottlenecks": metrics["bottlenecks"]
            }
            
        except nx.NetworkXNoPath:
            self.logger.warning(
                "No path found",
                source=source,
                target=target
            )
            return None
    
    async def find_all_paths(
        self,
        source: str,
        target: str,
        max_paths: int = 3
    ) -> List[Dict]:
        """Find multiple alternative paths"""
        if not self._network_loaded:
            await self.load_network()
        
        try:
            # Use k-shortest paths algorithm
            paths = list(nx.shortest_simple_paths(
                self.network,
                source=source,
                target=target,
                weight='weight'
            ))[:max_paths]
            
            results = []
            for path in paths:
                metrics = self._calculate_path_metrics(path, 1000)  # Use 1000 m³ as reference
                results.append({
                    "path": path,
                    "distance_km": metrics["distance"],
                    "travel_time_hours": metrics["travel_time"],
                    "capacity_m3s": metrics["min_capacity"],
                    "feasible": metrics["feasible"]
                })
            
            return results
            
        except Exception as e:
            self.logger.error("Failed to find paths", error=str(e))
            return []
    
    async def optimize_zone_delivery(
        self,
        zone: int,
        demands: Dict[str, float]
    ) -> Dict[str, Dict]:
        """Optimize delivery for all sections in a zone"""
        if not self._network_loaded:
            await self.load_network()
        
        # Find all section nodes in the zone
        zone_sections = [
            node for node in self.network.nodes()
            if f"Zone_{zone}" in node and "Section" in node
        ]
        
        # Source is always M(0,0)
        source = "M(0,0)"
        
        delivery_plans = {}
        total_flow_required = sum(demands.values()) / 3600  # Convert m³ to m³/s
        
        for section in zone_sections:
            if section not in demands:
                continue
            
            # Find optimal path
            path_result = await self.find_optimal_path(
                source,
                section,
                demands[section]
            )
            
            if path_result:
                delivery_plans[section] = {
                    "demand_m3": demands[section],
                    "path": path_result["path"],
                    "delivery_time_hours": path_result["delivery_time_hours"],
                    "loss_m3": path_result["expected_loss_m3"],
                    "gross_demand_m3": demands[section] + path_result["expected_loss_m3"]
                }
        
        # Check overall capacity constraints
        capacity_check = self._check_zone_capacity(zone, total_flow_required)
        
        return {
            "zone": zone,
            "delivery_plans": delivery_plans,
            "total_demand_m3": sum(demands.values()),
            "total_gross_demand_m3": sum(
                plan["gross_demand_m3"] 
                for plan in delivery_plans.values()
            ),
            "capacity_check": capacity_check,
            "optimization_timestamp": datetime.utcnow().isoformat()
        }
    
    def _apply_constraints(self, constraints: Dict) -> nx.DiGraph:
        """Apply constraints to create a working graph"""
        working_graph = self.network.copy()
        
        # Remove blocked gates
        if "blocked_gates" in constraints:
            for gate in constraints["blocked_gates"]:
                if gate in working_graph:
                    working_graph.remove_node(gate)
        
        # Apply flow limits
        if "flow_limits" in constraints:
            for edge, limit in constraints["flow_limits"].items():
                from_node, to_node = edge.split("->")
                if working_graph.has_edge(from_node, to_node):
                    working_graph[from_node][to_node]["capacity_m3s"] = limit
        
        # Apply time windows (simplified)
        if "time_window" in constraints:
            # Would implement time-based routing here
            pass
        
        return working_graph
    
    def _calculate_path_metrics(
        self,
        path: List[str],
        volume_m3: float
    ) -> Dict:
        """Calculate detailed metrics for a path"""
        total_distance = 0
        total_loss = 0
        min_capacity = float('inf')
        bottlenecks = []
        
        for i in range(len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            
            edge_data = self.network[from_node][to_node]
            
            # Distance
            distance = edge_data.get('distance_km', 0)
            total_distance += distance
            
            # Loss
            loss_rate = edge_data.get('loss_rate', 0.02)
            segment_loss = volume_m3 * loss_rate * distance
            total_loss += segment_loss
            
            # Capacity
            capacity = edge_data.get('capacity_m3s', 10)
            if capacity < min_capacity:
                min_capacity = capacity
                
            # Check for bottlenecks
            required_flow = volume_m3 / 3600  # Convert to m³/s
            if required_flow > capacity * 0.8:  # 80% threshold
                bottlenecks.append({
                    "segment": f"{from_node}->{to_node}",
                    "capacity_m3s": capacity,
                    "required_m3s": required_flow,
                    "utilization_percent": (required_flow / capacity) * 100
                })
        
        # Calculate times
        avg_velocity = 1.5  # m/s
        travel_time = total_distance / (avg_velocity * 3.6)  # Convert to hours
        
        # Delivery time based on flow rate
        flow_rate = min(min_capacity, volume_m3 / 3600)
        delivery_time = volume_m3 / (flow_rate * 3600)
        
        return {
            "distance": total_distance,
            "travel_time": travel_time,
            "delivery_time": delivery_time,
            "loss_m3": total_loss,
            "loss_percent": (total_loss / volume_m3) * 100,
            "min_capacity": min_capacity,
            "feasible": len(bottlenecks) == 0,
            "bottlenecks": bottlenecks
        }
    
    def _check_zone_capacity(self, zone: int, required_flow_m3s: float) -> Dict:
        """Check if zone infrastructure can handle required flow"""
        # Find main gate for zone
        zone_gates = [
            node for node, data in self.network.nodes(data=True)
            if f"Zone_{zone}" in data.get('name', '') and data.get('type') == 'gate'
        ]
        
        total_capacity = sum(
            self.network.nodes[gate].get('max_flow_m3s', 0)
            for gate in zone_gates
        )
        
        utilization = (required_flow_m3s / total_capacity * 100) if total_capacity > 0 else 100
        
        return {
            "zone_gates": zone_gates,
            "total_capacity_m3s": total_capacity,
            "required_flow_m3s": required_flow_m3s,
            "utilization_percent": utilization,
            "sufficient": utilization <= 80  # 80% threshold
        }
    
    async def analyze_network_efficiency(self) -> Dict:
        """Analyze overall network efficiency"""
        if not self._network_loaded:
            await self.load_network()
        
        # Calculate network metrics
        metrics = {
            "total_nodes": self.network.number_of_nodes(),
            "total_edges": self.network.number_of_edges(),
            "average_degree": sum(dict(self.network.degree()).values()) / self.network.number_of_nodes(),
            "is_connected": nx.is_weakly_connected(self.network),
            "bottleneck_analysis": self._identify_bottlenecks(),
            "redundancy_analysis": self._analyze_redundancy()
        }
        
        return metrics
    
    def _identify_bottlenecks(self) -> List[Dict]:
        """Identify potential bottlenecks in the network"""
        bottlenecks = []
        
        # Check edge capacities vs typical flow
        for u, v, data in self.network.edges(data=True):
            capacity = data.get('capacity_m3s', 10)
            
            # Count downstream nodes
            downstream = len(nx.descendants(self.network, v))
            
            # Estimate required capacity (0.1 m³/s per downstream node)
            required = downstream * 0.1
            
            if required > capacity * 0.8:
                bottlenecks.append({
                    "edge": f"{u}->{v}",
                    "capacity_m3s": capacity,
                    "downstream_nodes": downstream,
                    "estimated_requirement_m3s": required,
                    "severity": "high" if required > capacity else "medium"
                })
        
        return sorted(bottlenecks, key=lambda x: x["downstream_nodes"], reverse=True)[:10]
    
    def _analyze_redundancy(self) -> Dict:
        """Analyze network redundancy for reliability"""
        source = "M(0,0)"
        critical_nodes = []
        
        # Sample of important delivery points
        targets = [
            node for node in self.network.nodes()
            if "Zone_" in node and "Section_" in node
        ][:10]  # Analyze first 10 sections
        
        for target in targets:
            try:
                # Check if multiple paths exist
                paths = list(nx.node_disjoint_paths(self.network, source, target))
                if len(paths) < 2:
                    critical_nodes.append({
                        "target": target,
                        "paths_available": len(paths),
                        "redundancy": "none" if len(paths) == 1 else "low"
                    })
            except:
                pass
        
        return {
            "critical_sections": critical_nodes,
            "average_redundancy": 2.0 if len(critical_nodes) < len(targets) / 2 else 1.0
        }
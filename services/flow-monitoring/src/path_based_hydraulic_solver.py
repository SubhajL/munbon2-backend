#!/usr/bin/env python3
"""
Path-based Hydraulic Solver for Irrigation Networks
Properly handles flow routing through multiple gates
"""

import numpy as np
from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque
import json

class PathBasedHydraulicSolver:
    """
    Solves hydraulic network considering full paths from source to destinations
    """
    
    def __init__(self, network_file: str):
        """Initialize solver with network structure"""
        
        # Load network
        with open(network_file, 'r') as f:
            network_data = json.load(f)
        
        # Build graph structure
        self.nodes = set()
        self.edges = []  # List of (parent, child) tuples
        self.graph = defaultdict(list)  # Adjacency list
        self.reverse_graph = defaultdict(list)  # For upstream traversal
        
        # Extract edges
        for edge in network_data.get('edges', []):
            parent = edge['parent']
            child = edge['child']
            self.edges.append((parent, child))
            self.graph[parent].append(child)
            self.reverse_graph[child].append(parent)
            self.nodes.add(parent)
            self.nodes.add(child)
        
        # Gate properties
        self.gate_capacity = {}  # Maximum flow capacity
        self.gate_opening = {}   # Current opening (0-1)
        self.gate_flow = {}      # Current flow
        
        # Initialize gates
        for parent, child in self.edges:
            gate_id = f"{parent}->{child}"
            # Default capacity 5 m³/s
            self.gate_capacity[gate_id] = 5.0
            self.gate_opening[gate_id] = 0.0
            self.gate_flow[gate_id] = 0.0
        
        # Water levels
        self.water_levels = {node: 218.0 for node in self.nodes}
        self.water_levels['Source'] = 221.0  # Dam level
        
        # Canal properties (simplified)
        self.canal_inverts = {node: 217.0 for node in self.nodes}
        self.canal_inverts['Source'] = 221.0
        
    def find_all_paths(self, start: str, end: str) -> List[List[str]]:
        """Find all paths from start to end node"""
        
        paths = []
        
        def dfs(current: str, target: str, path: List[str], visited: Set[str]):
            if current == target:
                paths.append(path.copy())
                return
            
            visited.add(current)
            
            for neighbor in self.graph[current]:
                if neighbor not in visited:
                    path.append(neighbor)
                    dfs(neighbor, target, path, visited)
                    path.pop()
            
            visited.remove(current)
        
        dfs(start, end, [start], set())
        return paths
    
    def find_shortest_path(self, start: str, end: str) -> List[str]:
        """Find shortest path using BFS"""
        
        if start == end:
            return [start]
        
        queue = deque([(start, [start])])
        visited = {start}
        
        while queue:
            current, path = queue.popleft()
            
            for neighbor in self.graph[current]:
                if neighbor == end:
                    return path + [neighbor]
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return []  # No path found
    
    def get_path_gates(self, path: List[str]) -> List[str]:
        """Get all gates along a path"""
        
        gates = []
        for i in range(len(path) - 1):
            gate_id = f"{path[i]}->{path[i+1]}"
            gates.append(gate_id)
        return gates
    
    def calculate_path_flow(self, path: List[str]) -> float:
        """
        Calculate maximum flow through a path
        Limited by the most restrictive gate
        """
        
        gates = self.get_path_gates(path)
        if not gates:
            return 0.0
        
        # Flow is limited by most restrictive gate
        max_flow = float('inf')
        
        for gate_id in gates:
            # Gate flow based on opening and capacity
            gate_max = self.gate_capacity[gate_id] * self.gate_opening[gate_id]
            
            # Also consider hydraulic capacity
            upstream, downstream = gate_id.split('->')
            h_up = self.water_levels.get(upstream, 218.0)
            h_down = self.water_levels.get(downstream, 218.0)
            
            # Simple orifice equation
            if h_up > h_down and self.gate_opening[gate_id] > 0:
                # Q = Cd * A * sqrt(2g * dH)
                Cd = 0.6
                width = 2.0  # m
                opening_height = self.gate_opening[gate_id] * 1.2  # Convert to meters
                area = width * opening_height
                dH = h_up - h_down
                
                hydraulic_flow = Cd * area * np.sqrt(2 * 9.81 * dH)
                gate_flow = min(gate_max, hydraulic_flow)
            else:
                gate_flow = 0.0
            
            max_flow = min(max_flow, gate_flow)
        
        return max_flow
    
    def solve_for_targets(self, targets: Dict[str, float]) -> Dict:
        """
        Solve gate settings to achieve target flows
        targets: {destination_node: desired_flow}
        """
        
        print("\n=== PATH-BASED HYDRAULIC SOLVER ===")
        print(f"Targets: {targets}")
        
        # Find paths to each target
        path_info = {}
        
        for destination, target_flow in targets.items():
            # Find shortest path from Source
            path = self.find_shortest_path('Source', destination)
            
            if not path:
                print(f"WARNING: No path found to {destination}")
                continue
            
            gates = self.get_path_gates(path)
            
            path_info[destination] = {
                'path': path,
                'gates': gates,
                'target_flow': target_flow,
                'current_flow': 0.0
            }
            
            print(f"\nPath to {destination}:")
            print(f"  Route: {' → '.join(path)}")
            print(f"  Gates: {len(gates)}")
            print(f"  Target: {target_flow} m³/s")
        
        # Iterative solution
        max_iterations = 50
        tolerance = 0.1  # m³/s
        
        print("\n\nIterative Solution:")
        print("-" * 80)
        
        for iteration in range(max_iterations):
            # Step 1: Calculate current flows through paths
            total_error = 0.0
            
            for dest, info in path_info.items():
                info['current_flow'] = self.calculate_path_flow(info['path'])
                error = abs(info['target_flow'] - info['current_flow'])
                total_error += error
            
            # Print progress every 5 iterations
            if iteration % 5 == 0:
                print(f"\nIteration {iteration}:")
                for dest, info in path_info.items():
                    print(f"  {dest}: Current={info['current_flow']:.2f}, "
                          f"Target={info['target_flow']:.2f}, "
                          f"Error={abs(info['target_flow'] - info['current_flow']):.2f}")
            
            # Check convergence
            if total_error < tolerance:
                print(f"\nConverged after {iteration + 1} iterations!")
                break
            
            # Step 2: Adjust gate openings
            for dest, info in path_info.items():
                error = info['target_flow'] - info['current_flow']
                
                if abs(error) < 0.05:  # Close enough
                    continue
                
                # Adjust gates along this path
                for gate_id in info['gates']:
                    current_opening = self.gate_opening[gate_id]
                    
                    if error > 0:  # Need more flow
                        # Increase opening
                        adjustment = min(0.1, error / info['target_flow'] * 0.2)
                        new_opening = min(1.0, current_opening + adjustment)
                    else:  # Too much flow
                        # Decrease opening
                        adjustment = min(0.1, abs(error) / info['target_flow'] * 0.2)
                        new_opening = max(0.0, current_opening - adjustment)
                    
                    self.gate_opening[gate_id] = new_opening
            
            # Step 3: Update water levels (simplified)
            # In reality, would solve full hydraulic network
            for node in self.nodes:
                if node == 'Source':
                    continue
                
                # Simple approach: level drops with distance from source
                depth = 1.0 - 0.1 * len(self.find_shortest_path('Source', node))
                self.water_levels[node] = self.canal_inverts[node] + max(0.1, depth)
        
        # Generate results
        results = {
            'converged': total_error < tolerance,
            'iterations': iteration + 1,
            'total_error': total_error,
            'paths': {},
            'gate_settings': {}
        }
        
        print("\n\n=== FINAL RESULTS ===")
        
        for dest, info in path_info.items():
            results['paths'][dest] = {
                'route': info['path'],
                'gates': info['gates'],
                'target_flow': info['target_flow'],
                'achieved_flow': info['current_flow']
            }
            
            print(f"\n{dest}:")
            print(f"  Route: {' → '.join(info['path'])}")
            print(f"  Target flow: {info['target_flow']} m³/s")
            print(f"  Achieved flow: {info['current_flow']:.2f} m³/s")
            print(f"  Gate settings along path:")
            
            for gate_id in info['gates']:
                opening_pct = self.gate_opening[gate_id] * 100
                print(f"    {gate_id}: {opening_pct:.1f}% open")
                results['gate_settings'][gate_id] = {
                    'opening': self.gate_opening[gate_id],
                    'percent': opening_pct
                }
        
        return results
    
    def find_affected_paths(self, gate_id: str) -> List[Tuple[str, List[str]]]:
        """Find all delivery paths that use this gate"""
        
        affected = []
        
        # Check all possible destinations
        for node in self.nodes:
            if node == 'Source' or 'Zone' not in str(node):
                continue
            
            # Find path from source
            path = self.find_shortest_path('Source', node)
            gates = self.get_path_gates(path)
            
            if gate_id in gates:
                affected.append((node, path))
        
        return affected


def demonstrate_path_based_solver():
    """Demonstrate proper path-based hydraulic solving"""
    
    # Create sample network data
    network_data = {
        "edges": [
            {"parent": "Source", "child": "M(0,0)"},
            {"parent": "M(0,0)", "child": "M(0,1)"},
            {"parent": "M(0,0)", "child": "M(0,2)"},
            {"parent": "M(0,1)", "child": "RMC_Zone1"},
            {"parent": "M(0,2)", "child": "M(0,3)"},
            {"parent": "M(0,3)", "child": "M(0,5)"},
            {"parent": "M(0,5)", "child": "LMC_Zone2"},
            {"parent": "M(0,3)", "child": "M(0,3; 1,0)"},
            {"parent": "M(0,3; 1,0)", "child": "Branch_Zone3"}
        ]
    }
    
    # Save network
    with open('demo_network.json', 'w') as f:
        json.dump(network_data, f)
    
    # Create solver
    solver = PathBasedHydraulicSolver('demo_network.json')
    
    # Define targets
    targets = {
        'RMC_Zone1': 1.5,      # 1.5 m³/s to Zone 1
        'LMC_Zone2': 2.0,      # 2.0 m³/s to Zone 2  
        'Branch_Zone3': 1.0    # 1.0 m³/s to Zone 3
    }
    
    # Solve
    results = solver.solve_for_targets(targets)
    
    # Show impact analysis
    print("\n\n=== IMPACT ANALYSIS ===")
    print("If we close gate M(0,3)->M(0,5), affected destinations:")
    
    affected = solver.find_affected_paths("M(0,3)->M(0,5)")
    for dest, path in affected:
        print(f"  {dest}: {' → '.join(path)}")
    
    # Save results
    with open('path_based_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n\nResults saved to path_based_results.json")


if __name__ == "__main__":
    demonstrate_path_based_solver()
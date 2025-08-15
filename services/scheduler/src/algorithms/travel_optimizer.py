from typing import List, Dict, Tuple, Optional
import numpy as np
from scipy.spatial.distance import cdist
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import networkx as nx

from ..core.logger import get_logger

logger = get_logger(__name__)


class TravelOptimizer:
    """Optimize travel routes for field teams using TSP algorithms"""
    
    def __init__(self):
        self.earth_radius_km = 6371.0
        
    def optimize_team_route(
        self,
        team_operations: List[Dict],
        base_location: Tuple[float, float],
        time_windows: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Optimize route for a single team's operations"""
        
        if len(team_operations) == 0:
            return {"route": [], "distance": 0, "duration": 0}
        
        # Extract locations
        locations = [base_location]  # Start from base
        operation_indices = {}
        
        for i, op in enumerate(team_operations):
            lat = op.get("latitude", 0)
            lon = op.get("longitude", 0)
            locations.append((lat, lon))
            operation_indices[i + 1] = op  # +1 because base is index 0
        
        # Calculate distance matrix
        distance_matrix = self._calculate_distance_matrix(locations)
        
        # Solve TSP
        if time_windows:
            route, distance = self._solve_vrptw(
                distance_matrix, time_windows, operation_indices
            )
        else:
            route, distance = self._solve_tsp(distance_matrix)
        
        # Build route details
        route_details = self._build_route_details(
            route, operation_indices, locations, distance_matrix
        )
        
        return route_details
    
    def _calculate_distance_matrix(self, locations: List[Tuple[float, float]]) -> np.ndarray:
        """Calculate distance matrix using Haversine formula"""
        n = len(locations)
        matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = self._haversine_distance(locations[i], locations[j])
        
        return matrix
    
    def _haversine_distance(self, loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Calculate distance between two GPS coordinates in km"""
        lat1, lon1 = np.radians(loc1)
        lat2, lon2 = np.radians(loc2)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return self.earth_radius_km * c
    
    def _solve_tsp(self, distance_matrix: np.ndarray) -> Tuple[List[int], float]:
        """Solve TSP using OR-Tools"""
        
        # Create routing model
        manager = pywrapcp.RoutingIndexManager(
            len(distance_matrix), 1, 0  # num_nodes, num_vehicles, depot
        )
        routing = pywrapcp.RoutingModel(manager)
        
        # Distance callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node] * 1000)  # Convert to meters
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # Search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = 10
        
        # Solve
        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            route = self._extract_route(manager, routing, solution)
            distance = solution.ObjectiveValue() / 1000.0  # Convert back to km
            return route, distance
        else:
            logger.warning("No TSP solution found, using nearest neighbor")
            return self._nearest_neighbor_tsp(distance_matrix)
    
    def _solve_vrptw(
        self,
        distance_matrix: np.ndarray,
        time_windows: Dict,
        operation_indices: Dict
    ) -> Tuple[List[int], float]:
        """Solve Vehicle Routing Problem with Time Windows"""
        
        # Create routing model
        manager = pywrapcp.RoutingIndexManager(
            len(distance_matrix), 1, 0
        )
        routing = pywrapcp.RoutingModel(manager)
        
        # Distance and time callbacks
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node] * 1000)
        
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # Assume 40 km/h average speed
            travel_time = distance_matrix[from_node][to_node] / 40.0 * 60  # minutes
            service_time = 15 if to_node > 0 else 0  # 15 min per operation
            return int(travel_time + service_time)
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        time_callback_index = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_callback_index,
            30,    # allow waiting time
            480,   # maximum time (8 hours)
            False, # don't force start cumul to zero
            "Time"
        )
        
        time_dimension = routing.GetDimensionOrDie("Time")
        
        # Add time window constraints
        for node, tw in time_windows.items():
            if node > 0:  # Skip depot
                index = manager.NodeToIndex(node)
                time_dimension.CumulVar(index).SetRange(
                    int(tw["start"]), int(tw["end"])
                )
        
        # Solve
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.time_limit.seconds = 30
        
        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            route = self._extract_route(manager, routing, solution)
            distance = solution.ObjectiveValue() / 1000.0
            return route, distance
        else:
            return self._solve_tsp(distance_matrix)  # Fallback to TSP
    
    def _extract_route(self, manager, routing, solution) -> List[int]:
        """Extract route from OR-Tools solution"""
        route = []
        index = routing.Start(0)
        
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route.append(node)
            index = solution.Value(routing.NextVar(index))
        
        return route
    
    def _nearest_neighbor_tsp(self, distance_matrix: np.ndarray) -> Tuple[List[int], float]:
        """Simple nearest neighbor heuristic for TSP"""
        n = len(distance_matrix)
        unvisited = set(range(1, n))
        route = [0]  # Start at depot
        current = 0
        total_distance = 0
        
        while unvisited:
            # Find nearest unvisited
            distances = [(distance_matrix[current][j], j) for j in unvisited]
            dist, nearest = min(distances)
            
            route.append(nearest)
            total_distance += dist
            current = nearest
            unvisited.remove(nearest)
        
        # Return to depot
        route.append(0)
        total_distance += distance_matrix[current][0]
        
        return route, total_distance
    
    def _build_route_details(
        self,
        route: List[int],
        operation_indices: Dict,
        locations: List[Tuple],
        distance_matrix: np.ndarray
    ) -> Dict[str, Any]:
        """Build detailed route information"""
        
        route_operations = []
        total_distance = 0
        current_time = 0  # minutes from start
        
        for i in range(len(route) - 1):
            from_idx = route[i]
            to_idx = route[i + 1]
            
            # Calculate travel
            distance = distance_matrix[from_idx][to_idx]
            travel_time = distance / 40.0 * 60  # 40 km/h average
            
            total_distance += distance
            current_time += travel_time
            
            if to_idx > 0 and to_idx in operation_indices:
                operation = operation_indices[to_idx].copy()
                operation["arrival_time"] = current_time
                operation["sequence"] = len(route_operations) + 1
                route_operations.append(operation)
                
                # Add service time
                current_time += 15  # 15 minutes per operation
        
        # Create GeoJSON route
        route_geojson = self._create_route_geojson(route, locations)
        
        return {
            "operations": route_operations,
            "total_distance_km": round(total_distance, 2),
            "total_duration_minutes": round(current_time, 0),
            "route_geometry": route_geojson,
            "efficiency_score": self._calculate_efficiency(route, distance_matrix),
        }
    
    def _create_route_geojson(self, route: List[int], locations: List[Tuple]) -> Dict:
        """Create GeoJSON LineString for the route"""
        coordinates = []
        
        for idx in route:
            lat, lon = locations[idx]
            coordinates.append([lon, lat])  # GeoJSON uses lon, lat order
        
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            },
            "properties": {
                "type": "field_team_route"
            }
        }
    
    def _calculate_efficiency(self, route: List[int], distance_matrix: np.ndarray) -> float:
        """Calculate route efficiency score (0-100)"""
        # Compare to minimum spanning tree
        n = len(distance_matrix)
        if n <= 2:
            return 100.0
        
        # Create graph
        G = nx.Graph()
        for i in range(n):
            for j in range(i + 1, n):
                G.add_edge(i, j, weight=distance_matrix[i][j])
        
        # MST weight (lower bound)
        mst_weight = sum(data["weight"] for _, _, data in nx.minimum_spanning_tree(G).edges(data=True))
        
        # Route weight
        route_weight = sum(distance_matrix[route[i]][route[i+1]] for i in range(len(route) - 1))
        
        # Efficiency score
        efficiency = (mst_weight / route_weight) * 100
        return min(100.0, efficiency)
    
    def calculate_multi_day_routes(
        self,
        all_operations: List[Dict],
        teams: List[Dict],
        operation_days: List[int],
        constraints: Dict
    ) -> Dict[str, Any]:
        """Calculate routes for multiple teams over multiple days"""
        
        # Group operations by day and proximity
        day_clusters = self._cluster_operations_by_day(
            all_operations, operation_days, constraints
        )
        
        # Assign clusters to teams
        team_assignments = self._assign_clusters_to_teams(
            day_clusters, teams, constraints
        )
        
        # Optimize individual team routes
        all_routes = {}
        
        for team in teams:
            team_id = team["team_code"]
            all_routes[team_id] = {}
            
            for day in operation_days:
                if team_id in team_assignments.get(day, {}):
                    operations = team_assignments[day][team_id]
                    base = (team["base_location_lat"], team["base_location_lng"])
                    
                    route = self.optimize_team_route(operations, base)
                    all_routes[team_id][f"day_{day}"] = route
        
        return all_routes
    
    def _cluster_operations_by_day(
        self,
        operations: List[Dict],
        days: List[int],
        constraints: Dict
    ) -> Dict[int, List[List[Dict]]]:
        """Cluster operations by geographic proximity for each day"""
        # Simplified clustering - in reality would use k-means or DBSCAN
        clusters = {}
        
        for day in days:
            # Filter operations for this day
            day_ops = [op for op in operations if op.get("day") == day]
            
            # Simple geographic clustering
            clusters[day] = self._geographic_clustering(day_ops)
        
        return clusters
    
    def _geographic_clustering(self, operations: List[Dict]) -> List[List[Dict]]:
        """Cluster operations by geographic proximity"""
        if len(operations) <= 30:  # Small enough for one cluster
            return [operations]
        
        # Use simple grid-based clustering
        clusters = []
        # Implementation would use actual clustering algorithm
        
        return clusters
    
    def _assign_clusters_to_teams(
        self,
        day_clusters: Dict,
        teams: List[Dict],
        constraints: Dict
    ) -> Dict[int, Dict[str, List]]:
        """Assign operation clusters to teams"""
        assignments = {}
        
        for day, clusters in day_clusters.items():
            assignments[day] = {}
            
            # Simple round-robin assignment
            # In reality would consider team skills, location, capacity
            for i, cluster in enumerate(clusters):
                team_idx = i % len(teams)
                team_id = teams[team_idx]["team_code"]
                
                if team_id not in assignments[day]:
                    assignments[day][team_id] = []
                
                assignments[day][team_id].extend(cluster)
        
        return assignments
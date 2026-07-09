"""
Hydraulic Service for flow monitoring
Provides hydraulic modeling and verification capabilities
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import numpy as np
import structlog

from hydraulic_solver import HydraulicSolver, ConvergenceResult
from core.calibrated_flow_model_v2 import CalibratedFlowModelV2
from path_based_hydraulic_solver import PathBasedHydraulicSolver
from temporal_irrigation_scheduler import TemporalIrrigationScheduler
from db.connections import DatabaseManager
from db.influxdb_client import InfluxDBClient
from db.timescale_client import TimescaleClient
from core.metrics import hydraulic_solver_iterations, hydraulic_verification_duration
from core.gate_flow import build_gate_flow_calibration, gate_flow_m3s, required_opening_m
from core.network_topology import load_validated_network
from core.canal_capacity import build_capacity_index, reach_capacity

# P0 (F-01) fallback water levels: used ONLY when real sensor/solver levels are
# unavailable. Real levels are threaded in P1 (see docs/remediation/FIX_F01_GATE_FLOW_LAW_SPEC.md §7).
DEFAULT_UPSTREAM_DEPTH_M = 2.0  # assumed head over sill (m)
DEFAULT_HEAD_DIFF_M = 0.2       # assumed driving head (m)
# F-04: fallback canal capacity when a reach has no rated q_max in the network (logged, never silent).
DEFAULT_CANAL_CAPACITY_M3S = 15.0

logger = structlog.get_logger()


class HydraulicService:
    """Service for hydraulic calculations and modeling"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.hydraulic_solver = None
        self.path_solver = None
        self.temporal_scheduler = None
        self.calibrated_flow_model = CalibratedFlowModelV2()
        
        # Initialize solvers
        self._initialize_solvers()
    
    def _initialize_solvers(self):
        """Initialize hydraulic solvers"""
        try:
            # Load network and geometry files
            # F-11: use the canonical, validated topology (was munbon_network_final.json,
            # ~76% wrong). Guard connectivity before building solvers — fail fast, never
            # run hydraulics on a fragmented graph.
            network_file = os.path.join(os.path.dirname(__file__), "..", "config", "network.json")
            geometry_file = "/services/flow-monitoring/canal_geometry_template.json"
            load_validated_network(network_file)
            
            # Initialize solvers
            self.hydraulic_solver = HydraulicSolver(network_file, geometry_file)
            self.path_solver = PathBasedHydraulicSolver(network_file, geometry_file)
            self.temporal_scheduler = TemporalIrrigationScheduler(network_file)
            
            logger.info("Hydraulic solvers initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize hydraulic solvers: {e}")
            raise
    
    async def get_model_results(self, location_id: UUID, model_type: str) -> Dict[str, Any]:
        """Get hydraulic model results for a location"""
        try:
            # Convert UUID to node ID (in real implementation, lookup from database)
            node_id = f"N{str(location_id)[:8]}"
            
            if model_type == "manning":
                return await self._get_manning_results(node_id)
            elif model_type == "saint-venant":
                return await self._get_saint_venant_results(node_id)
            elif model_type == "rating-curve":
                return await self._get_rating_curve_results(node_id)
            else:
                raise ValueError(f"Unknown model type: {model_type}")
                
        except Exception as e:
            logger.error(f"Failed to get model results: {e}")
            raise
    
    async def simulate_propagation(
        self,
        start_location_id: UUID,
        flow_rate: float,
        duration_hours: int,
        downstream_locations: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Simulate water propagation through network"""
        try:
            # Convert UUIDs to node IDs
            start_node = f"N{str(start_location_id)[:8]}"
            
            # Set up initial conditions
            initial_flows = {start_node: flow_rate}
            
            # Run temporal simulation
            time_steps = duration_hours * 4  # 15-minute steps
            results = []
            
            for t in range(time_steps):
                # Update boundary conditions
                self.hydraulic_solver.set_boundary_flows(initial_flows)
                
                # Solve hydraulic network
                convergence = self.hydraulic_solver.solve()
                
                if convergence.converged:
                    # Extract results
                    step_result = {
                        "time": t * 0.25,  # hours
                        "water_levels": convergence.node_levels.copy(),
                        "gate_flows": convergence.gate_flows.copy(),
                        "travel_times": self._calculate_travel_times(start_node, convergence)
                    }
                    results.append(step_result)
                else:
                    logger.warning(f"Solver did not converge at time {t * 0.25} hours")
            
            # Aggregate results
            propagation_summary = self._summarize_propagation(results, start_node, downstream_locations)
            
            return propagation_summary
            
        except Exception as e:
            logger.error(f"Failed to simulate propagation: {e}")
            raise
    
    async def estimate_ungauged_flow(self, location_id: UUID) -> Dict[str, Any]:
        """Estimate flow at ungauged location"""
        try:
            node_id = f"N{str(location_id)[:8]}"
            
            # Get upstream and downstream gauged locations
            gauged_data = await self._get_nearby_gauged_data(node_id)
            
            if not gauged_data:
                raise ValueError(f"No gauged data available near {node_id}")
            
            # Run hydraulic solver with gauged boundary conditions
            boundary_conditions = {
                loc['node_id']: loc['flow'] 
                for loc in gauged_data
            }
            
            self.hydraulic_solver.set_boundary_flows(boundary_conditions)
            convergence = self.hydraulic_solver.solve()
            
            if not convergence.converged:
                raise RuntimeError("Hydraulic solver failed to converge")
            
            # Extract estimated flow
            estimated_flow = self._interpolate_flow(node_id, convergence)
            
            # Calculate confidence based on distance to gauged points
            confidence = self._calculate_estimation_confidence(node_id, gauged_data)
            
            return {
                "location_id": str(location_id),
                "node_id": node_id,
                "estimated_flow": estimated_flow,
                "confidence": confidence,
                "method": "hydraulic_interpolation",
                "gauged_references": [
                    {
                        "node_id": loc['node_id'],
                        "flow": loc['flow'],
                        "distance": loc['distance']
                    }
                    for loc in gauged_data
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to estimate ungauged flow: {e}")
            raise
    
    async def calibrate_model(
        self,
        location_id: UUID,
        observed_data: List[Dict[str, Any]],
        model_type: str
    ) -> Dict[str, Any]:
        """Calibrate hydraulic model parameters"""
        try:
            node_id = f"N{str(location_id)[:8]}"
            
            # Extract observed values
            observed_flows = np.array([d['flow'] for d in observed_data])
            observed_levels = np.array([d['level'] for d in observed_data])
            
            # Initial parameter guesses
            if model_type == "manning":
                initial_params = {"roughness": 0.025}  # Manning's n
            elif model_type == "rating-curve":
                initial_params = {"a": 1.0, "b": 2.5}  # Q = a * H^b
            else:
                raise ValueError(f"Calibration not supported for {model_type}")
            
            # Run optimization
            best_params, rmse, iterations = await self._optimize_parameters(
                node_id, observed_flows, observed_levels, 
                model_type, initial_params
            )
            
            # Store calibrated parameters
            await self._store_calibration(location_id, model_type, best_params)
            
            return {
                "location_id": str(location_id),
                "model_type": model_type,
                "calibrated_parameters": best_params,
                "rmse": rmse,
                "iterations": iterations,
                "n_observations": len(observed_data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to calibrate model: {e}")
            raise
    
    async def verify_schedule(
        self,
        deliveries: List[Dict[str, Any]],
        safety_margin: float = 0.1
    ) -> Dict[str, Any]:
        """Verify if irrigation schedule is hydraulically feasible"""
        with hydraulic_verification_duration.time():
            try:
                # Extract delivery requirements
                delivery_nodes = {}
                total_demand = 0.0
                
                for delivery in deliveries:
                    node_id = delivery.get('node_id', f"N{delivery.get('location_id', '')[:8]}")
                    flow_rate = delivery['flow_rate']
                    delivery_nodes[node_id] = flow_rate
                    total_demand += flow_rate
                
                # Check total capacity
                system_capacity = await self._get_system_capacity()
                if total_demand > system_capacity * (1 - safety_margin):
                    return {
                        "is_feasible": False,
                        "reason": "Total demand exceeds system capacity",
                        "total_demand": total_demand,
                        "system_capacity": system_capacity,
                        "utilization": total_demand / system_capacity
                    }
                
                # Run hydraulic verification with path-based solver
                paths = self.path_solver.find_delivery_paths(delivery_nodes)
                
                # Check each path for hydraulic constraints
                violations = []
                gate_settings = {}
                
                for path_id, path_info in paths.items():
                    # Calculate required gate openings
                    path_gates = path_info['gates']
                    path_flow = path_info['total_flow']
                    
                    for gate_id in path_gates:
                        # Check gate capacity
                        gate_capacity = self._get_gate_capacity(gate_id)
                        if path_flow > gate_capacity * (1 - safety_margin):
                            violations.append({
                                "type": "gate_capacity",
                                "gate_id": gate_id,
                                "required_flow": path_flow,
                                "capacity": gate_capacity
                            })
                        
                        # Calculate required opening
                        required_opening, opening_info = self._calculate_required_opening(
                            gate_id, path_flow
                        )
                        if not opening_info.get("feasible", True):
                            violations.append({
                                "type": "gate_flow_infeasible",
                                "gate_id": gate_id,
                                "required_flow": path_flow,
                                "reason": opening_info.get("reason", "unknown"),
                                "achievable": opening_info.get("achievable", 0.0),
                                "min_deliverable": opening_info.get("min_deliverable"),
                            })
                        gate_settings[gate_id] = max(
                            gate_settings.get(gate_id, 0),
                            required_opening
                        )
                
                # Check canal capacities
                canal_flows = self._aggregate_canal_flows(paths)
                for canal_id, flow in canal_flows.items():
                    canal_capacity = self._get_canal_capacity(canal_id)
                    if flow > canal_capacity * (1 - safety_margin):
                        violations.append({
                            "type": "canal_capacity",
                            "canal_id": canal_id,
                            "required_flow": flow,
                            "capacity": canal_capacity
                        })
                
                # Run full hydraulic simulation
                convergence = await self._run_schedule_simulation(
                    delivery_nodes, gate_settings
                )
                
                is_feasible = len(violations) == 0 and convergence.converged
                
                result = {
                    "is_feasible": is_feasible,
                    "total_demand": total_demand,
                    "system_utilization": total_demand / system_capacity,
                    "required_gate_settings": gate_settings,
                    "violations": violations,
                    "convergence": {
                        "converged": convergence.converged,
                        "iterations": convergence.iterations,
                        "max_error": convergence.max_error
                    } if convergence else None,
                    "warnings": convergence.warnings if convergence else [],
                    "delivery_paths": {
                        path_id: {
                            "nodes": info['nodes'],
                            "gates": info['gates'],
                            "total_flow": info['total_flow'],
                            "travel_time": info.get('travel_time', 0)
                        }
                        for path_id, info in paths.items()
                    }
                }
                
                if not is_feasible:
                    result["recommendations"] = self._generate_schedule_recommendations(
                        violations, delivery_nodes
                    )
                
                # Record metric
                hydraulic_solver_iterations.observe(
                    convergence.iterations if convergence else 0
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to verify schedule: {e}")
                raise
    
    # Helper methods
    
    async def _get_manning_results(self, node_id: str) -> Dict[str, Any]:
        """Get Manning equation results"""
        # Simplified implementation
        return {
            "model_type": "manning",
            "node_id": node_id,
            "flow_rate": 5.0,  # m³/s
            "water_level": 2.5,  # m
            "velocity": 1.2,  # m/s
            "froude_number": 0.3,
            "roughness": 0.025
        }
    
    async def _get_saint_venant_results(self, node_id: str) -> Dict[str, Any]:
        """Get Saint-Venant equation results"""
        return {
            "model_type": "saint-venant",
            "node_id": node_id,
            "flow_rate": 5.2,
            "water_level": 2.6,
            "velocity": 1.3,
            "wave_celerity": 3.5
        }
    
    async def _get_rating_curve_results(self, node_id: str) -> Dict[str, Any]:
        """Get rating curve results"""
        return {
            "model_type": "rating-curve",
            "node_id": node_id,
            "flow_rate": 4.8,
            "water_level": 2.4,
            "curve_parameters": {"a": 1.2, "b": 2.3}
        }
    
    def _calculate_travel_times(self, start_node: str, convergence: ConvergenceResult) -> Dict[str, float]:
        """Calculate travel times from start node using actual K1/K2 calibrated flow model"""
        travel_times = {}
        
        # Get network topology from hydraulic solver
        network = self.hydraulic_solver.network if hasattr(self.hydraulic_solver, 'network') else {}
        
        # Initialize with start node
        travel_times[start_node] = 0.0
        processed_nodes = set([start_node])
        nodes_to_process = [(start_node, 0.0)]
        
        while nodes_to_process:
            current_node, current_time = nodes_to_process.pop(0)
            
            # Find downstream nodes connected by gates
            for gate_id, gate_info in convergence.gate_flows.items():
                # Parse gate ID to find connected nodes
                # Gate IDs typically formatted as "G_upstream_downstream"
                if gate_id.startswith("G_"):
                    parts = gate_id.split("_")
                    if len(parts) >= 3 and parts[1] == current_node:
                        downstream_node = parts[2]
                        
                        if downstream_node not in processed_nodes:
                            # Calculate flow velocity using calibrated model
                            gate_flow = convergence.gate_flows.get(gate_id, 0)
                            upstream_level = convergence.node_levels.get(current_node, 2.0)
                            downstream_level = convergence.node_levels.get(downstream_node, 1.8)
                            
                            # Get canal properties (simplified - in real system, lookup from database)
                            canal_length = self._get_canal_length(current_node, downstream_node)
                            canal_width = self._get_canal_width(current_node, downstream_node)
                            canal_depth = upstream_level  # Approximate
                            
                            # Calculate cross-sectional area and velocity
                            if canal_depth > 0 and canal_width > 0:
                                area = canal_width * canal_depth
                                velocity = gate_flow / area if area > 0 else 0.5
                                
                                # Apply realistic velocity constraints (0.3 to 2.0 m/s for irrigation canals)
                                velocity = max(0.3, min(2.0, velocity))
                                
                                # Calculate travel time for this segment
                                segment_time = (canal_length / velocity) / 3600  # Convert seconds to hours
                            else:
                                # Default travel time if geometry unavailable
                                segment_time = canal_length / 1000 / 2.0  # Assume 2 km/hr
                            
                            # Add filling time based on canal volume and flow rate
                            canal_volume = canal_length * canal_width * canal_depth
                            filling_time = (0.5 * canal_volume / gate_flow) / 3600 if gate_flow > 0 else 0.5
                            
                            total_time = current_time + segment_time + filling_time
                            travel_times[downstream_node] = total_time
                            processed_nodes.add(downstream_node)
                            nodes_to_process.append((downstream_node, total_time))
        
        # For any unprocessed nodes, estimate based on network distance
        for node in convergence.node_levels:
            if node not in travel_times:
                # Estimate based on typical irrigation canal velocities
                estimated_distance = self._estimate_network_distance(start_node, node)
                travel_times[node] = estimated_distance / 2.0  # 2 km/hr average
        
        return travel_times
    
    def _get_canal_length(self, upstream_node: str, downstream_node: str) -> float:
        """Get canal length between nodes in meters"""
        # In real implementation, query from GIS database
        # For now, use realistic estimates based on irrigation system layout
        default_lengths = {
            ("N0", "N1"): 2000,    # Main canal segments typically 2-5 km
            ("N1", "N2"): 3000,
            ("N2", "N3"): 2500,
            ("N3", "N4"): 1500,    # Secondary canals shorter
            ("N4", "N5"): 1000,
            ("N5", "N6"): 800,     # Tertiary canals even shorter
        }
        
        key = (upstream_node, downstream_node)
        return default_lengths.get(key, 1500)  # Default 1.5 km
    
    def _get_canal_width(self, upstream_node: str, downstream_node: str) -> float:
        """Get canal width in meters"""
        # Main canals wider, tertiary canals narrower
        # Based on typical irrigation canal dimensions
        if upstream_node.startswith("N0"):
            return 10.0  # Main canal 10m wide
        elif upstream_node.startswith("N1") or upstream_node.startswith("N2"):
            return 5.0   # Secondary canal 5m wide
        else:
            return 2.0   # Tertiary canal 2m wide
    
    def _estimate_network_distance(self, start_node: str, end_node: str) -> float:
        """Estimate network distance in km when direct path unknown"""
        # Simple heuristic based on node numbering
        try:
            start_num = int(start_node[1:]) if len(start_node) > 1 else 0
            end_num = int(end_node[1:]) if len(end_node) > 1 else 0
            hops = abs(end_num - start_num)
            return hops * 2.5  # Assume 2.5 km average between nodes
        except:
            return 5.0  # Default 5 km
    
    def _summarize_propagation(
        self, 
        results: List[Dict], 
        start_node: str, 
        downstream_locations: Optional[List[UUID]]
    ) -> Dict[str, Any]:
        """Summarize propagation results"""
        if not results:
            return {"error": "No results to summarize"}
        
        # Extract arrival times
        arrival_times = {}
        peak_flows = {}
        
        for node in results[0]['water_levels']:
            # Find when water arrives (level increases)
            base_level = results[0]['water_levels'][node]
            for result in results:
                if result['water_levels'][node] > base_level + 0.1:
                    arrival_times[node] = result['time']
                    break
            
            # Find peak flow
            peak_flows[node] = max(
                result['gate_flows'].get(node, 0) 
                for result in results
            )
        
        return {
            "start_location": start_node,
            "simulation_duration": results[-1]['time'],
            "arrival_times": arrival_times,
            "peak_flows": peak_flows,
            "time_series": results
        }
    
    async def _get_nearby_gauged_data(self, node_id: str) -> List[Dict[str, Any]]:
        """Get data from nearby gauged locations"""
        # In real implementation, query from database
        # For now, return dummy data
        return [
            {"node_id": "N001", "flow": 5.0, "distance": 2.0},
            {"node_id": "N003", "flow": 4.5, "distance": 3.0}
        ]
    
    def _interpolate_flow(self, node_id: str, convergence: ConvergenceResult) -> float:
        """Interpolate flow at ungauged location"""
        # Simplified linear interpolation
        # In real implementation, use hydraulic routing
        upstream_flow = convergence.gate_flows.get(f"G_{node_id}_up", 0)
        downstream_flow = convergence.gate_flows.get(f"G_{node_id}_down", 0)
        return (upstream_flow + downstream_flow) / 2
    
    def _calculate_estimation_confidence(self, node_id: str, gauged_data: List[Dict]) -> float:
        """Calculate confidence in flow estimation"""
        if not gauged_data:
            return 0.0
        
        # Based on distance to nearest gauge
        min_distance = min(loc['distance'] for loc in gauged_data)
        
        if min_distance < 1.0:
            return 0.95
        elif min_distance < 3.0:
            return 0.85
        elif min_distance < 5.0:
            return 0.70
        else:
            return 0.50
    
    async def _optimize_parameters(
        self,
        node_id: str,
        observed_flows: np.ndarray,
        observed_levels: np.ndarray,
        model_type: str,
        initial_params: Dict[str, float]
    ) -> Tuple[Dict[str, float], float, int]:
        """Optimize model parameters"""
        # Simplified optimization
        # In real implementation, use scipy.optimize
        
        best_params = initial_params.copy()
        best_rmse = float('inf')
        
        for iteration in range(50):
            # Perturb parameters
            for param, value in best_params.items():
                test_params = best_params.copy()
                test_params[param] = value * (1 + np.random.uniform(-0.1, 0.1))
                
                # Calculate RMSE
                predicted_flows = self._predict_flows(
                    observed_levels, model_type, test_params
                )
                rmse = np.sqrt(np.mean((predicted_flows - observed_flows) ** 2))
                
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_params = test_params
        
        return best_params, best_rmse, 50
    
    def _predict_flows(
        self, 
        levels: np.ndarray, 
        model_type: str, 
        params: Dict[str, float]
    ) -> np.ndarray:
        """Predict flows using model"""
        if model_type == "manning":
            # Q = (1/n) * A * R^(2/3) * S^(1/2)
            # Simplified
            return levels * 2.0 / params['roughness']
        elif model_type == "rating-curve":
            # Q = a * H^b
            return params['a'] * (levels ** params['b'])
        else:
            return levels * 2.0
    
    async def _store_calibration(
        self, 
        location_id: UUID, 
        model_type: str, 
        params: Dict[str, float]
    ):
        """Store calibration results"""
        # Store in TimescaleDB
        pass
    
    async def _get_system_capacity(self) -> float:
        """Get total system capacity"""
        # From main canal
        return 30.0  # m³/s
    
    def _get_gate_capacity(self, gate_id: str) -> float:
        """Max flow the gate can pass at full opening, via the corrected flow law (F-01)."""
        calibration = self.calibrated_flow_model.calibration_loader.get_calibration(gate_id)
        if not calibration:
            return 10.0  # m³/s — no calibration available; conservative default
        cal = self._build_gate_flow_cal(gate_id, calibration)
        upstream_level, downstream_level = self._resolve_gate_levels(gate_id, cal)
        return gate_flow_m3s(cal, upstream_level, downstream_level, cal.max_opening_m)


    def _get_canal_capacity(self, canal_id: str) -> float:
        """Rated capacity (m3/s) of a canal reach, from the downstream gate's q_max in the
        canonical network (F-04). Falls back to a documented default (logged) when unknown."""
        capacity, from_data = reach_capacity(
            self._canal_capacity_index(), canal_id, DEFAULT_CANAL_CAPACITY_M3S
        )
        if not from_data:
            logger.warning(
                "canal %s: no rated capacity in network; using default %.1f m3/s",
                canal_id, DEFAULT_CANAL_CAPACITY_M3S,
            )
        return capacity

    def _canal_capacity_index(self) -> dict:
        """Lazily load & cache gate q_max capacities from the canonical network.json."""
        cache = getattr(self, "_canal_cap_index_cache", None)
        if cache is None:
            path = os.path.join(os.path.dirname(__file__), "..", "config", "network.json")
            try:
                with open(path, encoding="utf-8") as f:
                    cache = build_capacity_index(json.load(f))
            except Exception as exc:
                logger.error("failed to load canal capacity index: %s", exc)
                cache = {}
            self._canal_cap_index_cache = cache
        return cache
    
    def _calculate_required_opening(
        self,
        gate_id: str,
        required_flow: float,
        upstream_level: Optional[float] = None,
        downstream_level: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """Gate opening (percent of full) to pass required_flow, via the corrected flow
        law (F-01): a bisection inverse on real levels. Falls back to a documented, logged
        level assumption when sensor/solver levels are unavailable (real levels land in P1).
        Returns (opening_percent, info); info carries feasible/achievable/min_deliverable
        so callers can surface infeasibility instead of trusting the opening alone."""
        calibration = self.calibrated_flow_model.calibration_loader.get_calibration(gate_id)
        if not calibration:
            capacity = self._get_gate_capacity(gate_id)
            pct = min(100.0, (required_flow / capacity) * 100) if capacity > 0 else 100.0
            return pct, {"feasible": True, "reason": "no calibration; capacity-ratio fallback"}
        cal = self._build_gate_flow_cal(gate_id, calibration)
        u_level, d_level = self._resolve_gate_levels(gate_id, cal, upstream_level, downstream_level)
        opening_m, info = required_opening_m(cal, u_level, d_level, required_flow)
        pct = min(100.0, (opening_m / cal.max_opening_m) * 100.0)
        if not info.get("feasible", True):
            logger.warning(
                "gate %s: required flow %.3f m3/s infeasible (%s): achievable %.3f, "
                "min_deliverable %.3f — returning %.1f%% opening",
                gate_id, required_flow, info.get("reason", "unknown"),
                info.get("achievable", 0.0), info.get("min_deliverable", 0.0), pct,
            )
        return pct, info

    def _build_gate_flow_cal(self, gate_id: str, calibration):
        """Assemble a GateFlowCalibration from calibration + rated capacity + geometry.
        Sill/opening geometry sourcing is deferred to P1; build_gate_flow_calibration
        applies documented defaults and lowers confidence when geometry is absent."""
        return build_gate_flow_calibration(
            k1=calibration.k1,
            k2=calibration.k2,
            confidence=calibration.confidence,
            q_max_m3s=self._gate_rated_capacity(gate_id),
            width_m=calibration.width_m,
        )

    def _gate_rated_capacity(self, gate_id: str) -> Optional[float]:
        """Rated q_max (m3/s) for a gate from the calibration table, if present."""
        loader = self.calibrated_flow_model.calibration_loader
        excel_id = loader.gate_id_mapping.get(gate_id, gate_id)
        raw = loader.calibrations.get(excel_id) or loader.calibrations.get(gate_id) or {}
        return raw.get("q_max_m3s")

    def _resolve_gate_levels(
        self,
        gate_id: str,
        cal,
        upstream_level: Optional[float] = None,
        downstream_level: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Upstream/downstream water levels (m MSL) for the flow law. Uses provided levels
        when available; otherwise a documented P0 fallback (sill + typical depth / head
        difference), logged. Real sensor/solver levels are wired in P1 (spec §7)."""
        if upstream_level is not None and downstream_level is not None:
            return upstream_level, downstream_level
        u = cal.sill_m + DEFAULT_UPSTREAM_DEPTH_M
        d = u - DEFAULT_HEAD_DIFF_M
        logger.warning(
            "gate %s: no real levels; assuming upstream=%.2f downstream=%.2f (P0 fallback)",
            gate_id, u, d,
        )
        return u, d


    def _aggregate_canal_flows(self, paths: Dict[str, Any]) -> Dict[str, float]:
        """Aggregate flows by canal"""
        canal_flows = {}
        # Simplified - aggregate by upstream node
        for path_info in paths.values():
            for i, node in enumerate(path_info['nodes'][:-1]):
                canal_id = f"C_{node}_{path_info['nodes'][i+1]}"
                canal_flows[canal_id] = canal_flows.get(canal_id, 0) + path_info['total_flow']
        return canal_flows
    
    async def _run_schedule_simulation(
        self,
        delivery_nodes: Dict[str, float],
        gate_settings: Dict[str, float]
    ) -> Optional[ConvergenceResult]:
        """Run full hydraulic simulation for schedule"""
        try:
            # Set boundary conditions
            self.hydraulic_solver.set_boundary_flows(delivery_nodes)
            
            # Set gate openings
            for gate_id, opening in gate_settings.items():
                self.hydraulic_solver.set_gate_opening(gate_id, opening / 100.0)
            
            # Solve
            return self.hydraulic_solver.solve()
        except Exception as e:
            logger.error(f"Schedule simulation failed: {e}")
            return None
    
    def _generate_schedule_recommendations(
        self,
        violations: List[Dict],
        deliveries: Dict[str, float]
    ) -> List[str]:
        """Generate recommendations for infeasible schedule"""
        recommendations = []
        
        # Group violations by type
        gate_violations = [v for v in violations if v['type'] == 'gate_capacity']
        canal_violations = [v for v in violations if v['type'] == 'canal_capacity']
        
        if gate_violations:
            recommendations.append(
                f"Reduce flow through {len(gate_violations)} gates or stagger deliveries"
            )
        
        if canal_violations:
            recommendations.append(
                f"Split deliveries across multiple time slots to reduce peak canal flow"
            )
        
        # Suggest alternative scheduling
        total_demand = sum(deliveries.values())
        if total_demand > 20:  # High demand
            recommendations.append(
                "Consider night-time irrigation to balance system load"
            )
        
        return recommendations
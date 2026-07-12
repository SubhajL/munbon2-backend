"""
Hydraulic Service for flow monitoring
Provides hydraulic modeling and verification capabilities
"""

import asyncio
import os
from typing import Dict, List, Optional, Any, Tuple
import structlog

from hydraulic_solver import HydraulicSolver, ConvergenceResult
from path_based_hydraulic_solver import PathBasedHydraulicSolver
from db.connections import DatabaseManager
from utils.gate_calibration_loader import GateCalibrationLoader
from core.metrics import hydraulic_solver_iterations, hydraulic_verification_duration
from core.config_loader import load_canal_geometry_config, load_network_config
from core.conveyance_loss import sections_by_edge_from_geometry
from core.gate_flow import build_gate_flow_calibration, gate_flow_m3s, required_opening_m
from core.network_topology import ROOT, load_validated_network
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
        # Wave 1.6 (C10 completion): the calibration loader is owned directly —
        # CalibratedFlowModelV2 (inverted flow law) is deleted.
        self.calibration_loader = GateCalibrationLoader()
        
        # Initialize solvers
        self._initialize_solvers()
    
    def _initialize_solvers(self):
        """Initialize hydraulic solvers"""
        try:
            # Wave 1.3: same canonical configs as /control, anchored to __file__ (the
            # old geometry path was container-absolute and failed everywhere else).
            # F-11 guard: never run hydraulics on a fragmented graph.
            config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
            network_file = os.path.join(config_dir, "network.json")
            geometry_file = os.path.join(config_dir, "canal_geometry.json")
            self._network_edges = load_validated_network(network_file)

            self.hydraulic_solver = HydraulicSolver(network_file, geometry_file)
            self.path_solver = PathBasedHydraulicSolver(network_file)
            # temporal_scheduler stays None: nothing consumes it, its ctor never
            # matched the canonical network format, and travel-time offsets are
            # Wave 3.2 (core/travel_time.py).

            # Wave 1.1: warm the strict capacity index so a corrupt/drifted network
            # fails construction instead of the first capacity check.
            self._canal_capacity_index()
            # Wave 2.1a: same for the surveyed segment bounds.
            self._canal_sections_by_edge()

            logger.info("Hydraulic solvers initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize hydraulic solvers: {e}")
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
                    # Two deliveries to one node combine (the reach must carry both);
                    # a dict overwrite would silently verify only the last one.
                    delivery_nodes[node_id] = delivery_nodes.get(node_id, 0.0) + flow_rate
                    total_demand += flow_rate
                
                # Check total capacity
                system_capacity = await self._get_system_capacity()
                if total_demand > system_capacity * (1 - safety_margin):
                    return {
                        "is_feasible": False,
                        "reason": "Total demand exceeds system capacity",
                        "total_demand": total_demand,
                        "system_capacity": system_capacity,
                        # same field name as the full-verification response
                        "system_utilization": total_demand / system_capacity,
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
                
                # Fail closed when the simulation seam is unavailable (returns None):
                # capacity + gate-flow checks alone cannot verify the schedule.
                is_feasible = (
                    len(violations) == 0
                    and convergence is not None
                    and convergence.converged
                )

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
                    "warnings": convergence.warnings if convergence else [
                        "hydraulic simulation unavailable; schedule checked against "
                        "capacity and gate-flow limits only"
                    ],
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
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    async def _get_system_capacity(self) -> float:
        """Rated capacity at the network head: the sum of the source children's rated
        q_max (Wave 1.4 — replaces a hardcoded 30.0 that let physically impossible
        schedules pass the total-demand gate). Fail-closed when a source reach has
        no rating: a fabricated capacity is how overdelivery gets approved."""
        index = self._canal_capacity_index()
        heads = [child for parent, child in self._network_edges if parent == ROOT]
        missing = sorted(g for g in heads if g not in index)
        if not heads or missing:
            raise ValueError(
                "cannot determine system capacity: source reaches without rated "
                f"q_max: {missing if missing else '(network has no source children)'}"
            )
        return sum(index[g] for g in heads)
    
    def _get_gate_capacity(self, gate_id: str) -> float:
        """Max flow the gate can pass: its rated q_max when the calibration table has
        one (Wave 1.4), else the corrected flow law at max opening (F-01). The old
        flat 10.0 branch was dead — get_calibration always returns the default
        ladder — and a low-confidence fallback is logged, never silent."""
        rated = self._gate_rated_capacity(gate_id)
        if rated is not None:
            return rated
        calibration = self.calibration_loader.get_calibration(gate_id)
        if calibration.source != "field_measurement":
            logger.warning(
                "gate %s: capacity from %s calibration (confidence %.2f)",
                gate_id, calibration.source, calibration.confidence,
            )
        cal = self._build_gate_flow_cal(gate_id, calibration)
        upstream_level, downstream_level = self._resolve_gate_levels(gate_id, cal)
        return gate_flow_m3s(cal, upstream_level, downstream_level, cal.max_opening_m)


    def _get_canal_capacity(self, canal_id: str) -> float:
        """Rated capacity (m3/s) of a canal reach: min of the downstream gate's q_max
        (F-04) and the weakest surveyed canal segment (Wave 2.1a), over whichever is
        known. Falls back to a documented default (logged) when neither is."""
        capacity, from_data = reach_capacity(
            self._canal_capacity_index(), canal_id, DEFAULT_CANAL_CAPACITY_M3S,
            sections_by_edge=self._canal_sections_by_edge(),
        )
        if not from_data:
            logger.warning(
                "canal %s: no rated capacity in network or survey; using default %.1f m3/s",
                canal_id, DEFAULT_CANAL_CAPACITY_M3S,
            )
        return capacity

    def _canal_sections_by_edge(self) -> dict:
        """Lazily load & cache the surveyed segment lists keyed by normalized edge
        (Wave 2.1a). Strict + fail-closed like the capacity index; warmed at
        construction alongside it."""
        cache = getattr(self, "_canal_sections_cache", None)
        if cache is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "config", "canal_geometry.json"
            )
            cache = sections_by_edge_from_geometry(load_canal_geometry_config(path))
            self._canal_sections_cache = cache
        return cache

    def _canal_capacity_index(self) -> dict:
        """Lazily load & cache gate q_max capacities from the canonical network.json.

        Strict + fail-closed (Wave 1.1): a corrupt or drifted network raises ConfigError
        instead of silently emptying the index (which sent every canal to the default
        capacity). Failures are not cached; the index is warmed at construction so a bad
        config fails the service, not the first capacity check.
        """
        cache = getattr(self, "_canal_cap_index_cache", None)
        if cache is None:
            path = os.path.join(os.path.dirname(__file__), "..", "config", "network.json")
            cache = build_capacity_index(load_network_config(path))
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
        calibration = self.calibration_loader.get_calibration(gate_id)
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
        """Rated q_max (m3/s) for a gate from the calibration table, if any."""
        return self.calibration_loader.rated_q_max(gate_id)

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
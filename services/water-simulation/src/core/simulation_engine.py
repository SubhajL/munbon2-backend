"""
Core simulation engine for water distribution simulation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.core.models import (
    Scenario, SimulationRun, SimulationState,
    GateOperation, OptimizationResult
)
from src.core.schemas import SimulationStatus
from src.clients.ros_client import ROSClient
from src.clients.flow_client import FlowMonitoringClient
from src.clients.gate_client import GateControlClient
from src.clients.gis_client import GISClient
from src.config import get_settings

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Main simulation engine orchestrating water distribution simulation"""
    
    def __init__(
        self,
        db_session: AsyncSession,
        ros_client: ROSClient,
        flow_client: FlowMonitoringClient,
        gate_client: GateControlClient,
        gis_client: GISClient
    ):
        self.db = db_session
        self.ros = ros_client
        self.flow = flow_client
        self.gate = gate_client
        self.gis = gis_client
        self.settings = get_settings()
        
        # Simulation state
        self.current_run: Optional[SimulationRun] = None
        self.scenario: Optional[Scenario] = None
        self.current_state: Dict[str, Any] = {}
        self.network_topology: Dict[str, Any] = {}
        self.section_details: Dict[str, Dict] = {}
        self.gate_properties: Dict[str, Dict] = {}
        
    async def initialize_simulation(
        self,
        scenario_id: UUID,
        start_from_time: Optional[datetime] = None
    ) -> SimulationRun:
        """Initialize a new simulation run"""
        try:
            # Load scenario
            result = await self.db.execute(
                select(Scenario).where(Scenario.scenario_id == scenario_id)
            )
            self.scenario = result.scalar_one()
            
            # Create new run
            self.current_run = SimulationRun(
                scenario_id=scenario_id,
                status=SimulationStatus.pending.value,
                start_time=datetime.utcnow(),
                current_simulation_time=start_from_time or self.scenario.base_date,
                statistics={}
            )
            
            self.db.add(self.current_run)
            await self.db.commit()
            
            # Load network topology
            await self._load_network_topology()
            
            # Initialize state
            await self._initialize_state()
            
            logger.info(f"Initialized simulation run {self.current_run.run_id}")
            return self.current_run
            
        except Exception as e:
            logger.error(f"Failed to initialize simulation: {str(e)}")
            raise
    
    async def run_simulation(self) -> None:
        """Execute the main simulation loop"""
        if not self.current_run or not self.scenario:
            raise ValueError("Simulation not initialized")
        
        try:
            # Update status to running
            await self._update_run_status(SimulationStatus.running.value)
            
            simulation_end = self.scenario.base_date + timedelta(days=self.scenario.duration_days)
            time_step = timedelta(minutes=self.scenario.time_step_minutes)
            
            current_time = self.current_run.current_simulation_time
            step_count = 0
            
            while current_time < simulation_end:
                logger.debug(f"Processing simulation time: {current_time}")
                
                # Calculate water demands
                demands = await self._calculate_demands(current_time)
                
                # Run optimization
                optimization_result = await self._optimize_water_distribution(
                    current_time, demands
                )
                
                # Execute gate operations
                await self._execute_gate_operations(current_time, optimization_result)
                
                # Simulate hydraulic flow
                await self._simulate_hydraulic_flow(current_time, time_step.total_seconds())
                
                # Save state snapshot
                await self._save_state_snapshot(current_time, step_count)
                
                # Update progress
                progress = (step_count / (self.scenario.duration_days * 24 / (self.scenario.time_step_minutes / 60))) * 100
                await self._update_progress(progress, current_time)
                
                # Move to next time step
                current_time += time_step
                step_count += 1
                
                # Check for cancellation
                if await self._check_cancelled():
                    logger.info("Simulation cancelled by user")
                    break
            
            # Complete simulation
            await self._complete_simulation()
            
        except Exception as e:
            logger.error(f"Simulation failed: {str(e)}")
            await self._fail_simulation(str(e))
            raise
    
    async def _load_network_topology(self) -> None:
        """Load network topology from GIS service"""
        self.network_topology = await self.gis.get_gate_network_topology()
        
        # Cache section details
        for zone in range(1, 5):  # Assuming 4 zones
            sections = await self.gis.get_sections_in_zone(zone)
            for section in sections:
                self.section_details[section["section_id"]] = section
        
        # Cache gate properties
        for node in self.network_topology.get("nodes", []):
            if node["type"] == "gate":
                gate_id = node["id"]
                self.gate_properties[gate_id] = await self.flow.get_gate_properties(gate_id)
    
    async def _initialize_state(self) -> None:
        """Initialize simulation state"""
        self.current_state = {
            "water_levels": {},
            "gate_positions": {},
            "flow_rates": {},
            "section_deliveries": {}
        }
        
        # Initialize water levels at key points
        for node in self.network_topology.get("nodes", []):
            node_id = node["id"]
            # Default initial water level (could be loaded from historical data)
            self.current_state["water_levels"][node_id] = node.get("initial_level", 2.0)
        
        # Initialize gate positions
        for gate_id in self.gate_properties:
            status = await self.gate.get_gate_status(gate_id)
            self.current_state["gate_positions"][gate_id] = status["current_opening_m"]
    
    async def _calculate_demands(self, simulation_time: datetime) -> Dict[str, float]:
        """Calculate water demands for all sections"""
        week = simulation_time.isocalendar()[1]
        year = simulation_time.year
        
        demands = {}
        
        # Get demands in bulk for efficiency
        section_ids = list(self.section_details.keys())
        bulk_demands = await self.ros.get_bulk_water_demand(section_ids, week, year)
        
        for demand_data in bulk_demands:
            section_id = demand_data["section_id"]
            
            # Check for scenario-specific demand overrides
            override = await self._get_demand_override(section_id, week)
            if override:
                demands[section_id] = override["base_demand_m3"] * override.get("weather_adjustment_factor", 1.0)
            else:
                demands[section_id] = demand_data["demand_m3"]
        
        # Convert weekly to time-step demand
        hours_per_week = 168
        hours_per_timestep = self.scenario.time_step_minutes / 60
        time_step_factor = hours_per_timestep / hours_per_week
        
        return {sid: demand * time_step_factor for sid, demand in demands.items()}
    
    async def _optimize_water_distribution(
        self,
        simulation_time: datetime,
        demands: Dict[str, float]
    ) -> OptimizationResult:
        """Run optimization to determine gate operations"""
        # This will be implemented in the gate optimizer service
        # For now, create a placeholder
        from src.services.gate_optimizer import GateOptimizer
        
        optimizer = GateOptimizer(
            self.network_topology,
            self.gate_properties,
            self.section_details
        )
        
        result = await optimizer.optimize(
            demands=demands,
            current_state=self.current_state,
            objective=self.scenario.optimization_objective,
            constraints=await self._get_constraints(simulation_time)
        )
        
        # Save optimization result
        opt_result = OptimizationResult(
            run_id=self.current_run.run_id,
            optimization_time=simulation_time,
            objective_function=self.scenario.optimization_objective,
            water_efficiency_score=result.get("efficiency_score", 0),
            fairness_index=result.get("fairness_index", 0),
            energy_usage_kwh=result.get("energy_usage", 0),
            computational_time_ms=result.get("computation_time_ms", 0),
            iterations=result.get("iterations", 0),
            convergence_achieved=result.get("converged", False),
            gate_schedule=result.get("gate_schedule", {}),
            section_allocations=result.get("allocations", {})
        )
        
        self.db.add(opt_result)
        await self.db.commit()
        
        return opt_result
    
    async def _execute_gate_operations(
        self,
        simulation_time: datetime,
        optimization_result: OptimizationResult
    ) -> None:
        """Execute gate operations based on optimization"""
        gate_schedule = optimization_result.gate_schedule
        
        for gate_id, target_opening in gate_schedule.items():
            current_opening = self.current_state["gate_positions"].get(gate_id, 0)
            
            if abs(current_opening - target_opening) > 0.01:  # Threshold for change
                # Create gate operation record
                operation = GateOperation(
                    run_id=self.current_run.run_id,
                    gate_id=gate_id,
                    scheduled_time=simulation_time,
                    target_opening_m=target_opening,
                    operation_type="automatic",
                    priority="normal",
                    executed_time=simulation_time,
                    actual_opening_m=target_opening,
                    status="completed"
                )
                
                self.db.add(operation)
                
                # Update state
                self.current_state["gate_positions"][gate_id] = target_opening
    
    async def _simulate_hydraulic_flow(
        self,
        simulation_time: datetime,
        time_step_seconds: float
    ) -> None:
        """Simulate hydraulic flow through the network"""
        # Calculate flows through gates
        for gate_id in self.gate_properties:
            gate_props = self.gate_properties[gate_id]
            opening = self.current_state["gate_positions"][gate_id]
            
            # Get upstream and downstream nodes
            upstream_node = self._find_upstream_node(gate_id)
            downstream_node = self._find_downstream_node(gate_id)
            
            if upstream_node and downstream_node:
                upstream_level = self.current_state["water_levels"].get(upstream_node, 0)
                downstream_level = self.current_state["water_levels"].get(downstream_node, 0)
                
                # Calculate flow
                flow_result = await self.flow.calculate_gate_flow(
                    gate_id, opening, upstream_level, downstream_level
                )
                
                self.current_state["flow_rates"][gate_id] = flow_result["flow_m3s"]
        
        # Update water levels based on mass balance
        await self._update_water_levels(time_step_seconds)
    
    async def _update_water_levels(self, time_step_seconds: float) -> None:
        """Update water levels based on flow balance"""
        new_levels = {}
        
        for node_id in self.current_state["water_levels"]:
            current_level = self.current_state["water_levels"][node_id]
            
            # Calculate net inflow/outflow
            inflow = self._calculate_node_inflow(node_id)
            outflow = self._calculate_node_outflow(node_id)
            
            # Estimate new level
            new_level = await self.flow.estimate_water_level(
                node_id, inflow, outflow, current_level, int(time_step_seconds)
            )
            
            new_levels[node_id] = new_level
        
        # Update state
        self.current_state["water_levels"] = new_levels
    
    async def _save_state_snapshot(
        self,
        simulation_time: datetime,
        step_count: int
    ) -> None:
        """Save current state snapshot to database"""
        # Calculate system metrics
        total_demand = sum(self.current_state.get("section_deliveries", {}).values())
        total_supply = sum(self.current_state.get("flow_rates", {}).values()) * self.scenario.time_step_minutes * 60
        
        state = SimulationState(
            run_id=self.current_run.run_id,
            simulation_time=simulation_time,
            time_step=step_count,
            water_levels=self.current_state["water_levels"],
            gate_positions=self.current_state["gate_positions"],
            flow_rates=self.current_state["flow_rates"],
            total_demand_m3=total_demand,
            total_supply_m3=total_supply,
            total_delivered_m3=min(total_demand, total_supply),
            system_efficiency=min(total_demand, total_supply) / total_supply if total_supply > 0 else 0
        )
        
        self.db.add(state)
        
        # Commit periodically
        if step_count % 10 == 0:
            await self.db.commit()
    
    async def _update_run_status(self, status: str) -> None:
        """Update simulation run status"""
        await self.db.execute(
            update(SimulationRun)
            .where(SimulationRun.run_id == self.current_run.run_id)
            .values(status=status)
        )
        await self.db.commit()
    
    async def _update_progress(self, progress: float, current_time: datetime) -> None:
        """Update simulation progress"""
        await self.db.execute(
            update(SimulationRun)
            .where(SimulationRun.run_id == self.current_run.run_id)
            .values(
                progress_percent=progress,
                current_simulation_time=current_time
            )
        )
        await self.db.commit()
    
    async def _check_cancelled(self) -> bool:
        """Check if simulation has been cancelled"""
        result = await self.db.execute(
            select(SimulationRun.status)
            .where(SimulationRun.run_id == self.current_run.run_id)
        )
        status = result.scalar_one()
        return status == SimulationStatus.cancelled.value
    
    async def _complete_simulation(self) -> None:
        """Complete the simulation run"""
        await self.db.execute(
            update(SimulationRun)
            .where(SimulationRun.run_id == self.current_run.run_id)
            .values(
                status=SimulationStatus.completed.value,
                end_time=datetime.utcnow(),
                progress_percent=100
            )
        )
        await self.db.commit()
        
        logger.info(f"Simulation {self.current_run.run_id} completed successfully")
    
    async def _fail_simulation(self, error_message: str) -> None:
        """Mark simulation as failed"""
        await self.db.execute(
            update(SimulationRun)
            .where(SimulationRun.run_id == self.current_run.run_id)
            .values(
                status=SimulationStatus.failed.value,
                end_time=datetime.utcnow(),
                error_message=error_message
            )
        )
        await self.db.commit()
    
    # Helper methods
    def _find_upstream_node(self, gate_id: str) -> Optional[str]:
        """Find upstream node for a gate"""
        for edge in self.network_topology.get("edges", []):
            if edge["to"] == gate_id:
                return edge["from"]
        return None
    
    def _find_downstream_node(self, gate_id: str) -> Optional[str]:
        """Find downstream node for a gate"""
        for edge in self.network_topology.get("edges", []):
            if edge["from"] == gate_id:
                return edge["to"]
        return None
    
    def _calculate_node_inflow(self, node_id: str) -> float:
        """Calculate total inflow to a node"""
        inflow = 0
        for gate_id, flow in self.current_state["flow_rates"].items():
            if self._find_downstream_node(gate_id) == node_id:
                inflow += flow
        return inflow
    
    def _calculate_node_outflow(self, node_id: str) -> float:
        """Calculate total outflow from a node"""
        outflow = 0
        for gate_id, flow in self.current_state["flow_rates"].items():
            if self._find_upstream_node(gate_id) == node_id:
                outflow += flow
        return outflow
    
    async def _get_demand_override(self, section_id: str, week: int) -> Optional[Dict]:
        """Get demand override from scenario configuration"""
        # Implementation would query section_demands table
        # Placeholder for now
        return None
    
    async def _get_constraints(self, simulation_time: datetime) -> Dict[str, Any]:
        """Get operational constraints for optimization"""
        constraints = {
            "gate_constraints": {},
            "maintenance_windows": [],
            "priority_deliveries": []
        }
        
        # Get gate maintenance status
        for gate_id in self.gate_properties:
            maintenance = await self.gate.get_gate_maintenance_status(gate_id)
            if maintenance["maintenance_required"]:
                constraints["maintenance_windows"].append({
                    "gate_id": gate_id,
                    "restrictions": maintenance["restrictions"]
                })
        
        return constraints
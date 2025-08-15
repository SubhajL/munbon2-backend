import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import logging
from ..models.channel import NetworkTopology
from ..models.optimization import (
    OptimizationResult, OptimizationObjective, ZoneDeliveryRequest,
    ElevationFeasibility, DeliverySequence, FlowSplitOptimization,
    ContingencyPlan, EnergyRecoveryPotential
)
from .elevation_feasibility import ElevationFeasibilityChecker
from .minimum_depth_calculator import MinimumDepthCalculator
from .flow_splitter import FlowSplitter
from ..config.settings import settings

logger = logging.getLogger(__name__)


class GravityOptimizer:
    """Main gravity flow optimization service"""
    
    def __init__(self, network: NetworkTopology):
        self.network = network
        self.elevation_checker = ElevationFeasibilityChecker(network)
        self.depth_calculator = MinimumDepthCalculator()
        self.flow_splitter = FlowSplitter(network)
        
    async def optimize_delivery(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        source_water_level: Optional[float] = None,
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
        include_contingency: bool = True,
        include_energy_recovery: bool = True
    ) -> OptimizationResult:
        """
        Perform complete gravity flow optimization
        
        Args:
            zone_requests: Water delivery requests for each zone
            source_water_level: Current water level at source
            objective: Optimization objective
            include_contingency: Whether to generate contingency plans
            include_energy_recovery: Whether to identify energy recovery potential
        
        Returns:
            Complete optimization result with all components
        """
        logger.info(f"Starting gravity optimization for {len(zone_requests)} zones")
        request_id = f"opt_{datetime.now().isoformat()}"
        
        # Step 1: Check elevation feasibility
        logger.info("Checking elevation feasibility...")
        feasibility_results = await self._check_feasibility(zone_requests, source_water_level)
        
        # Filter feasible zones
        feasible_zones = [
            req for req, feas in zip(zone_requests, feasibility_results)
            if feas.is_feasible
        ]
        
        if not feasible_zones:
            logger.warning("No zones are feasible for gravity delivery")
            return self._create_empty_result(request_id, zone_requests, feasibility_results)
        
        # Step 2: Calculate minimum depths
        logger.info("Calculating minimum depth requirements...")
        depth_requirements = await self._calculate_depth_requirements(feasible_zones)
        
        # Step 3: Optimize flow splits
        logger.info("Optimizing flow distribution...")
        total_inflow = self._calculate_available_inflow(source_water_level)
        flow_splits = await self._optimize_flow_splits(
            total_inflow, feasible_zones, objective
        )
        
        # Step 4: Generate delivery sequence
        logger.info("Generating optimal delivery sequence...")
        delivery_sequence = await self._generate_delivery_sequence(
            feasible_zones, flow_splits, depth_requirements
        )
        
        # Step 5: Optional - Energy recovery analysis
        energy_recovery = None
        if include_energy_recovery:
            logger.info("Analyzing energy recovery potential...")
            energy_recovery = await self._analyze_energy_recovery()
        
        # Step 6: Optional - Contingency planning
        contingency_plans = None
        if include_contingency:
            logger.info("Generating contingency plans...")
            contingency_plans = await self._generate_contingency_plans(
                feasible_zones, flow_splits
            )
        
        # Calculate overall metrics
        total_delivery_time = self._calculate_total_delivery_time(delivery_sequence)
        overall_efficiency = self._calculate_overall_efficiency(
            flow_splits, zone_requests, feasibility_results
        )
        
        # Compile warnings
        warnings = self._compile_warnings(
            feasibility_results, depth_requirements, flow_splits
        )
        
        return OptimizationResult(
            request_id=request_id,
            timestamp=datetime.now(),
            objective=objective,
            zone_requests=zone_requests,
            feasibility_results=feasibility_results,
            delivery_sequence=delivery_sequence,
            flow_splits=flow_splits,
            energy_recovery=energy_recovery,
            contingency_plans=contingency_plans,
            total_delivery_time=total_delivery_time,
            overall_efficiency=overall_efficiency,
            warnings=warnings
        )
    
    async def _check_feasibility(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        source_water_level: Optional[float]
    ) -> List[ElevationFeasibility]:
        """Check elevation feasibility for all zones"""
        # Run feasibility checks concurrently
        tasks = []
        for request in zone_requests:
            zone_elevation = self._get_zone_elevation(request.zone_id)
            task = asyncio.create_task(
                asyncio.to_thread(
                    self.elevation_checker.check_zone_feasibility,
                    request.zone_id,
                    zone_elevation,
                    request.required_flow_rate,
                    source_water_level
                )
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def _calculate_depth_requirements(
        self,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> Dict[str, Dict]:
        """Calculate minimum depth requirements for all channels"""
        depth_requirements = {}
        
        for zone_req in zone_requests:
            # Get channels serving this zone
            channels = self._get_channels_for_zone(zone_req.zone_id)
            
            for channel in channels:
                if channel.channel_id not in depth_requirements:
                    requirements = self.depth_calculator.calculate_channel_requirements(
                        channel,
                        zone_req.required_flow_rate,
                        check_transitions=True
                    )
                    depth_requirements[channel.channel_id] = requirements
        
        return depth_requirements
    
    async def _optimize_flow_splits(
        self,
        total_inflow: float,
        zone_requests: List[ZoneDeliveryRequest],
        objective: OptimizationObjective
    ) -> FlowSplitOptimization:
        """Optimize flow distribution through gates"""
        return await asyncio.to_thread(
            self.flow_splitter.optimize_flow_split,
            total_inflow,
            zone_requests,
            objective
        )
    
    async def _generate_delivery_sequence(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        flow_splits: FlowSplitOptimization,
        depth_requirements: Dict
    ) -> List[DeliverySequence]:
        """Generate optimal delivery sequence using dynamic programming"""
        # Simplified sequencing - prioritize by elevation (highest first)
        sorted_zones = sorted(
            zone_requests,
            key=lambda x: (x.priority, -self._get_zone_elevation(x.zone_id))
        )
        
        delivery_sequence = []
        current_time = datetime.now()
        
        for i, zone_req in enumerate(sorted_zones):
            # Calculate travel time based on flow velocity
            zone_flow = flow_splits.zone_allocations.get(zone_req.zone_id, 0)
            travel_time = self._estimate_travel_time(zone_req.zone_id, zone_flow)
            
            # Get gate settings for this zone
            zone_gates = self._get_gates_for_zone(zone_req.zone_id)
            gate_settings = [
                gs for gs in flow_splits.gate_settings
                if gs.gate_id in zone_gates
            ]
            
            # Calculate head loss
            total_head_loss = self._calculate_total_head_loss(zone_req.zone_id, zone_flow)
            
            end_time = current_time + travel_time
            
            sequence = DeliverySequence(
                sequence_id=f"seq_{i}",
                zone_id=zone_req.zone_id,
                order=i + 1,
                start_time=current_time,
                end_time=end_time,
                gate_settings=gate_settings,
                expected_travel_time=travel_time.total_seconds() / 60,  # minutes
                total_head_loss=total_head_loss
            )
            
            delivery_sequence.append(sequence)
            current_time = end_time
        
        return delivery_sequence
    
    async def _analyze_energy_recovery(self) -> List[EnergyRecoveryPotential]:
        """Identify locations with energy recovery potential"""
        energy_sites = []
        
        # Look for significant elevation drops
        for channel in self.network.channels:
            for section in channel.sections:
                elevation_drop = section.start_elevation - section.end_elevation
                
                if elevation_drop > 2.0:  # More than 2m drop
                    # Estimate average flow
                    avg_flow = channel.capacity * 0.7  # Assume 70% utilization
                    
                    # Calculate potential power (P = ρ * g * Q * H * η)
                    efficiency = 0.85  # Turbine efficiency
                    power_kw = (
                        settings.water_density * settings.gravity * 
                        avg_flow * elevation_drop * efficiency / 1000
                    )
                    
                    if power_kw > 50:  # Only consider sites > 50 kW
                        # Estimate annual energy (assume 6 months operation)
                        annual_energy_mwh = power_kw * 24 * 180 / 1000
                        
                        # Simple feasibility assessment
                        if power_kw > 500:
                            feasibility = "Highly feasible"
                            cost_per_kw = 2000
                        elif power_kw > 200:
                            feasibility = "Feasible"
                            cost_per_kw = 3000
                        else:
                            feasibility = "Marginally feasible"
                            cost_per_kw = 4000
                        
                        estimated_cost = power_kw * cost_per_kw
                        
                        # Simple payback calculation (assume $0.1/kWh)
                        annual_revenue = annual_energy_mwh * 1000 * 0.1
                        payback_years = estimated_cost / annual_revenue if annual_revenue > 0 else None
                        
                        site = EnergyRecoveryPotential(
                            location_id=f"{channel.channel_id}_{section.section_id}",
                            channel_id=channel.channel_id,
                            available_head=elevation_drop,
                            flow_rate=avg_flow,
                            potential_power=power_kw,
                            annual_energy=annual_energy_mwh,
                            installation_feasibility=feasibility,
                            estimated_cost=estimated_cost,
                            payback_period=payback_years
                        )
                        energy_sites.append(site)
        
        return sorted(energy_sites, key=lambda x: x.potential_power, reverse=True)
    
    async def _generate_contingency_plans(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        nominal_flow_splits: FlowSplitOptimization
    ) -> List[ContingencyPlan]:
        """Generate contingency plans for common failure scenarios"""
        plans = []
        
        # Scenario 1: Main channel blockage
        main_channel_plan = await self._plan_main_channel_failure(
            zone_requests, nominal_flow_splits
        )
        if main_channel_plan:
            plans.append(main_channel_plan)
        
        # Scenario 2: Gate failure (stuck closed)
        for gate in self.flow_splitter.automated_gates[:5]:  # Top 5 critical gates
            gate_failure_plan = await self._plan_gate_failure(
                gate.gate_id, zone_requests, nominal_flow_splits
            )
            if gate_failure_plan:
                plans.append(gate_failure_plan)
        
        # Scenario 3: Reduced source water level
        low_water_plan = await self._plan_low_water_scenario(
            zone_requests, nominal_flow_splits
        )
        if low_water_plan:
            plans.append(low_water_plan)
        
        return plans
    
    async def _plan_main_channel_failure(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        nominal_splits: FlowSplitOptimization
    ) -> Optional[ContingencyPlan]:
        """Plan for main channel blockage"""
        # Simplified: assume 50% flow reduction
        reduced_flow = nominal_splits.total_inflow * 0.5
        
        # Re-optimize with reduced flow
        emergency_splits = await asyncio.to_thread(
            self.flow_splitter.optimize_flow_split,
            reduced_flow,
            zone_requests,
            OptimizationObjective.MAXIMIZE_EFFICIENCY
        )
        
        return ContingencyPlan(
            plan_id="main_channel_blockage",
            trigger_condition="Main channel flow < 50% nominal",
            affected_zones=[req.zone_id for req in zone_requests],
            alternative_routes=[{
                "description": "Use lateral channels with increased gate openings",
                "flow_reduction": "50%"
            }],
            gate_adjustments=emergency_splits.gate_settings,
            expected_performance=emergency_splits.efficiency,
            head_loss_increase=0.5  # Additional 0.5m head loss
        )
    
    async def _plan_gate_failure(
        self,
        gate_id: str,
        zone_requests: List[ZoneDeliveryRequest],
        nominal_splits: FlowSplitOptimization
    ) -> Optional[ContingencyPlan]:
        """Plan for specific gate failure"""
        # Find zones affected by this gate
        affected_zones = []
        for zone_req in zone_requests:
            zone_gates = self._get_gates_for_zone(zone_req.zone_id)
            if gate_id in zone_gates:
                affected_zones.append(zone_req.zone_id)
        
        if not affected_zones:
            return None
        
        # Create modified gate settings (set failed gate to 0)
        modified_settings = [
            gs if gs.gate_id != gate_id else gs._replace(opening_ratio=0)
            for gs in nominal_splits.gate_settings
        ]
        
        return ContingencyPlan(
            plan_id=f"gate_failure_{gate_id}",
            trigger_condition=f"Gate {gate_id} stuck closed",
            affected_zones=affected_zones,
            alternative_routes=[{
                "description": f"Redistribute flow through adjacent gates",
                "gate_compensation": "Increase adjacent gate openings by 30%"
            }],
            gate_adjustments=modified_settings,
            expected_performance=0.85,  # 85% of nominal
            head_loss_increase=0.3
        )
    
    async def _plan_low_water_scenario(
        self,
        zone_requests: List[ZoneDeliveryRequest],
        nominal_splits: FlowSplitOptimization
    ) -> ContingencyPlan:
        """Plan for low source water level"""
        # Prioritize high-priority zones
        priority_zones = [req for req in zone_requests if req.priority <= 2]
        
        # Re-optimize for priority zones only
        priority_splits = await asyncio.to_thread(
            self.flow_splitter.optimize_flow_split,
            nominal_splits.total_inflow * 0.7,  # 70% of nominal
            priority_zones,
            OptimizationObjective.MAXIMIZE_EFFICIENCY
        )
        
        return ContingencyPlan(
            plan_id="low_water_level",
            trigger_condition="Source water level < minimum + 0.5m",
            affected_zones=[req.zone_id for req in zone_requests if req.priority > 2],
            alternative_routes=[{
                "description": "Serve only high-priority zones",
                "priority_cutoff": "Priority 1-2 only"
            }],
            gate_adjustments=priority_splits.gate_settings,
            expected_performance=0.7,
            head_loss_increase=0.2
        )
    
    def _calculate_available_inflow(self, source_water_level: Optional[float]) -> float:
        """Calculate available inflow based on source water level"""
        if source_water_level is None:
            source_water_level = settings.source_elevation + 1.0  # 1m above ground
        
        # Simple relationship: flow proportional to head above minimum
        min_operating_level = settings.source_elevation + settings.min_flow_depth
        if source_water_level < min_operating_level:
            return 0
        
        available_head = source_water_level - min_operating_level
        # Assume 50 m³/s per meter of head (simplified)
        return min(available_head * 50, 200)  # Max 200 m³/s
    
    def _get_zone_elevation(self, zone_id: str) -> float:
        """Get minimum elevation for a zone"""
        zone_key = zone_id.lower().replace("-", "_")
        if zone_key in settings.zone_elevations:
            return settings.zone_elevations[zone_key]["min"]
        return 220.0  # Default
    
    def _get_channels_for_zone(self, zone_id: str) -> List:
        """Get channels that serve a specific zone"""
        # Simplified - would use actual network topology
        return [c for c in self.network.channels if zone_id.lower() in c.name.lower()]
    
    def _get_gates_for_zone(self, zone_id: str) -> List[str]:
        """Get gates serving a zone"""
        # Simplified implementation
        zone_number = int(zone_id.split("_")[1]) if "_" in zone_id else 1
        gates_per_zone = len(self.flow_splitter.automated_gates) // 6
        start_idx = (zone_number - 1) * gates_per_zone
        end_idx = min(start_idx + gates_per_zone, len(self.flow_splitter.automated_gates))
        
        return [g.gate_id for g in self.flow_splitter.automated_gates[start_idx:end_idx]]
    
    def _estimate_travel_time(self, zone_id: str, flow_rate: float) -> datetime:
        """Estimate water travel time to zone"""
        # Distance estimates (km)
        zone_distances = {
            "zone_1": 5,
            "zone_2": 8,
            "zone_3": 10,
            "zone_4": 12,
            "zone_5": 15,
            "zone_6": 18
        }
        
        distance = zone_distances.get(zone_id, 10) * 1000  # meters
        
        # Estimate velocity based on flow
        velocity = max(0.3, min(2.0, flow_rate / 20))  # m/s
        
        travel_seconds = distance / velocity
        return datetime.now() + datetime.timedelta(seconds=travel_seconds)
    
    def _calculate_total_head_loss(self, zone_id: str, flow_rate: float) -> float:
        """Calculate total head loss to zone"""
        # Simplified - actual would trace path and sum losses
        zone_distances = {
            "zone_1": 5,
            "zone_2": 8,
            "zone_3": 10,
            "zone_4": 12,
            "zone_5": 15,
            "zone_6": 18
        }
        
        distance = zone_distances.get(zone_id, 10) * 1000
        # Assume 0.5m loss per km at nominal flow
        return distance / 1000 * 0.5 * (flow_rate / 50)
    
    def _calculate_total_delivery_time(self, sequences: List[DeliverySequence]) -> float:
        """Calculate total time to complete all deliveries"""
        if not sequences:
            return 0
        
        last_sequence = max(sequences, key=lambda x: x.end_time)
        first_sequence = min(sequences, key=lambda x: x.start_time)
        
        total_hours = (last_sequence.end_time - first_sequence.start_time).total_seconds() / 3600
        return total_hours
    
    def _calculate_overall_efficiency(
        self,
        flow_splits: FlowSplitOptimization,
        zone_requests: List[ZoneDeliveryRequest],
        feasibility_results: List[ElevationFeasibility]
    ) -> float:
        """Calculate overall system efficiency"""
        # Factors: feasibility rate, flow efficiency, demand satisfaction
        feasibility_rate = sum(1 for f in feasibility_results if f.is_feasible) / len(feasibility_results)
        
        total_delivered = sum(flow_splits.zone_allocations.values())
        total_requested = sum(req.required_flow_rate for req in zone_requests)
        demand_satisfaction = min(total_delivered / max(total_requested, 1e-6), 1.0)
        
        return (feasibility_rate + flow_splits.efficiency + demand_satisfaction) / 3
    
    def _compile_warnings(
        self,
        feasibility_results: List[ElevationFeasibility],
        depth_requirements: Dict,
        flow_splits: FlowSplitOptimization
    ) -> List[str]:
        """Compile all warnings from optimization process"""
        warnings = []
        
        # Feasibility warnings
        for feas in feasibility_results:
            warnings.extend(feas.warnings)
        
        # Depth warnings
        for channel_id, requirements in depth_requirements.items():
            for section_id, req in requirements.items():
                if req.froude_number > 0.9 and req.froude_number < 1.1:
                    warnings.append(
                        f"Channel {channel_id} section {section_id}: "
                        f"Flow near critical (Fr={req.froude_number:.2f})"
                    )
        
        # Flow split warnings
        if flow_splits.efficiency < 0.8:
            warnings.append(
                f"Low delivery efficiency: {flow_splits.efficiency:.1%}"
            )
        
        return warnings
    
    def _create_empty_result(
        self,
        request_id: str,
        zone_requests: List[ZoneDeliveryRequest],
        feasibility_results: List[ElevationFeasibility]
    ) -> OptimizationResult:
        """Create empty result when no feasible solution exists"""
        return OptimizationResult(
            request_id=request_id,
            timestamp=datetime.now(),
            objective=OptimizationObjective.BALANCED,
            zone_requests=zone_requests,
            feasibility_results=feasibility_results,
            delivery_sequence=[],
            flow_splits=FlowSplitOptimization(
                optimization_id="none",
                timestamp=datetime.now(),
                objective=OptimizationObjective.BALANCED,
                total_inflow=0,
                zone_allocations={},
                gate_settings=[],
                efficiency=0,
                convergence_iterations=0,
                optimization_time=0
            ),
            energy_recovery=None,
            contingency_plans=None,
            total_delivery_time=0,
            overall_efficiency=0,
            warnings=["No feasible delivery solution found"]
        )
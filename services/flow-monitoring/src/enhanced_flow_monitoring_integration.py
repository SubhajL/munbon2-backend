#!/usr/bin/env python3
"""
Enhanced Flow Monitoring Integration
Combines gate properties, calibrated flow model, and job order system
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import pandas as pd
import logging

from core.gate_properties_enhanced import (
    GatePropertiesManager, GatePropertiesEnhanced,
    GateShape, GateControlType, DiscreteControlLevels
)
from core.calibrated_flow_model import (
    CalibratedFlowModel, HydraulicConditions,
    FlowCalculationResult, FlowRegime
)
from core.job_order_system import (
    JobOrderManager, JobOrderPriority, JobOrder
)

logger = logging.getLogger(__name__)


@dataclass
class GateOptimizationResult:
    """Result from gate optimization"""
    gate_id: str
    recommended_opening_m: float
    actual_opening_m: float  # Snapped to discrete level if automatic
    expected_flow_m3s: float
    confidence: float
    is_manual: bool
    job_order: Optional[JobOrder] = None
    warnings: List[str] = None
    

@dataclass
class SystemFlowBalance:
    """System-wide flow balance"""
    total_inflow_m3s: float
    total_outflow_m3s: float
    zone_flows: Dict[int, float]
    gate_flows: Dict[str, float]
    balance_error_m3s: float
    timestamp: datetime
    

class EnhancedFlowMonitoringSystem:
    """Main integration class for enhanced flow monitoring"""
    
    def __init__(self, excel_path: str):
        # Initialize components
        self.gate_manager = GatePropertiesManager()
        self.flow_model = CalibratedFlowModel()
        self.job_order_manager = JobOrderManager()
        
        # Load gate data
        self.gate_manager.load_from_excel(excel_path)
        
        # System state
        self.current_gate_openings: Dict[str, float] = {}
        self.water_levels: Dict[str, Tuple[float, float]] = {}  # upstream, downstream
        
        # Initialize gate openings to closed
        for gate_id in self.gate_manager.gates:
            self.current_gate_openings[gate_id] = 0.0
            
        logger.info(f"Initialized flow monitoring with {len(self.gate_manager.gates)} gates")
        
    def calculate_gate_flow(
        self,
        gate_id: str,
        opening_m: Optional[float] = None,
        upstream_level: Optional[float] = None,
        downstream_level: Optional[float] = None
    ) -> FlowCalculationResult:
        """Calculate flow through a specific gate"""
        
        gate = self.gate_manager.get_gate(gate_id)
        if not gate:
            logger.error(f"Gate {gate_id} not found")
            return FlowCalculationResult(
                flow_rate_m3s=0.0,
                flow_regime=FlowRegime.NO_FLOW,
                discharge_coefficient=0.0,
                velocity_ms=0.0,
                froude_number=0.0,
                energy_loss_m=0.0,
                confidence=0.0,
                warnings=[f"Gate {gate_id} not found"]
            )
            
        # Use provided values or current state
        if opening_m is None:
            opening_m = self.current_gate_openings.get(gate_id, 0.0)
            
        if upstream_level is None or downstream_level is None:
            levels = self.water_levels.get(gate_id, (2.0, 1.5))  # Default levels
            upstream_level = upstream_level or levels[0]
            downstream_level = downstream_level or levels[1]
            
        # Create hydraulic conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=upstream_level,
            downstream_water_level_m=downstream_level,
            gate_opening_m=opening_m
        )
        
        # Calculate flow
        return self.flow_model.calculate_gate_flow(gate, conditions)
        
    def optimize_gate_settings(
        self,
        target_flows: Dict[int, float],  # Zone -> target flow
        constraints: Optional[Dict[str, Tuple[float, float]]] = None  # Gate -> (min, max) opening
    ) -> List[GateOptimizationResult]:
        """Optimize gate settings to achieve target flows"""
        
        results = []
        manual_operations = []
        
        # Group gates by zone
        for zone, target_flow in target_flows.items():
            zone_gates = self.gate_manager.get_gates_by_zone(zone)
            
            if not zone_gates:
                logger.warning(f"No gates found for zone {zone}")
                continue
                
            # Distribute flow among gates in zone
            flow_per_gate = target_flow / len(zone_gates)
            
            for gate in zone_gates:
                # Get constraints
                min_opening, max_opening = 0.0, gate.height_m
                if constraints and gate.gate_id in constraints:
                    min_opening, max_opening = constraints[gate.gate_id]
                    
                # Calculate required opening
                required_opening = self._calculate_required_opening(
                    gate, flow_per_gate, min_opening, max_opening
                )
                
                # Snap to discrete level if automatic
                actual_opening = required_opening
                if gate.is_automatic and gate.control_levels:
                    actual_opening = gate.control_levels.get_nearest_level(required_opening)
                    
                # Calculate expected flow with actual opening
                expected_flow = self.calculate_gate_flow(
                    gate.gate_id,
                    opening_m=actual_opening
                )
                
                # Create result
                result = GateOptimizationResult(
                    gate_id=gate.gate_id,
                    recommended_opening_m=required_opening,
                    actual_opening_m=actual_opening,
                    expected_flow_m3s=expected_flow.flow_rate_m3s,
                    confidence=expected_flow.confidence,
                    is_manual=not gate.is_automatic,
                    warnings=expected_flow.warnings
                )
                
                # Create job order if manual gate needs adjustment
                if not gate.is_automatic:
                    current_opening = self.current_gate_openings.get(gate.gate_id, 0.0)
                    if abs(current_opening - actual_opening) > 0.05:  # 5cm threshold
                        job_order = self.job_order_manager.create_job_order(
                            gate=gate,
                            target_opening_m=actual_opening,
                            priority=JobOrderPriority.NORMAL,
                            reason=f"Flow optimization for Zone {zone}"
                        )
                        result.job_order = job_order
                        manual_operations.append(job_order)
                        
                results.append(result)
                
        # Log summary
        automatic_adjustments = sum(1 for r in results if not r.is_manual)
        manual_adjustments = len(manual_operations)
        
        logger.info(
            f"Optimization complete: {automatic_adjustments} automatic adjustments, "
            f"{manual_adjustments} manual operations required"
        )
        
        return results
        
    def apply_automatic_adjustments(
        self,
        optimization_results: List[GateOptimizationResult]
    ) -> Dict[str, float]:
        """Apply adjustments to automatic gates"""
        
        adjustments = {}
        
        for result in optimization_results:
            if not result.is_manual:
                # Update automatic gate
                self.current_gate_openings[result.gate_id] = result.actual_opening_m
                adjustments[result.gate_id] = result.actual_opening_m
                
                logger.info(
                    f"Adjusted automatic gate {result.gate_id} to {result.actual_opening_m:.2f}m"
                )
                
        return adjustments
        
    def calculate_system_balance(self) -> SystemFlowBalance:
        """Calculate system-wide flow balance"""
        
        total_inflow = 0.0
        total_outflow = 0.0
        zone_flows = {}
        gate_flows = {}
        
        for gate_id, gate in self.gate_manager.gates.items():
            # Calculate flow
            flow_result = self.calculate_gate_flow(gate_id)
            flow = flow_result.flow_rate_m3s
            
            gate_flows[gate_id] = flow
            
            # Accumulate by zone
            zone = gate.zone or 0
            if zone not in zone_flows:
                zone_flows[zone] = 0.0
            zone_flows[zone] += flow
            
            # Determine if inflow or outflow based on gate naming
            if "Source" in gate_id or gate_id.startswith("M(0,"):
                total_inflow += flow
            else:
                total_outflow += flow
                
        balance_error = total_inflow - total_outflow
        
        return SystemFlowBalance(
            total_inflow_m3s=total_inflow,
            total_outflow_m3s=total_outflow,
            zone_flows=zone_flows,
            gate_flows=gate_flows,
            balance_error_m3s=balance_error,
            timestamp=datetime.now()
        )
        
    def update_water_levels(
        self,
        water_level_data: Dict[str, Tuple[float, float]]
    ) -> None:
        """Update water levels for gates"""
        
        self.water_levels.update(water_level_data)
        logger.info(f"Updated water levels for {len(water_level_data)} gates")
        
    def get_gate_summary(self) -> pd.DataFrame:
        """Get summary of all gates with current status"""
        
        data = []
        
        for gate_id, gate in self.gate_manager.gates.items():
            # Current state
            opening = self.current_gate_openings.get(gate_id, 0.0)
            levels = self.water_levels.get(gate_id, (2.0, 1.5))
            
            # Calculate flow
            flow_result = self.calculate_gate_flow(gate_id)
            
            # Job order status
            pending_orders = [
                o for o in self.job_order_manager.orders.values()
                if o.gate_id == gate_id and o.status.value in ["pending", "assigned"]
            ]
            
            data.append({
                "Gate ID": gate_id,
                "Type": gate.shape.value,
                "Control": gate.control_type.value,
                "Width/Diameter (m)": gate.width_m or gate.diameter_m,
                "Height (m)": gate.height_m,
                "Drop (m)": gate.drop_height_m,
                "Current Opening (m)": opening,
                "Upstream Level (m)": levels[0],
                "Downstream Level (m)": levels[1],
                "Flow (m³/s)": flow_result.flow_rate_m3s,
                "Flow Regime": flow_result.flow_regime.value,
                "Confidence": flow_result.confidence,
                "Pending Orders": len(pending_orders),
                "Zone": gate.zone
            })
            
        return pd.DataFrame(data)
        
    def _calculate_required_opening(
        self,
        gate: GatePropertiesEnhanced,
        target_flow: float,
        min_opening: float,
        max_opening: float
    ) -> float:
        """Calculate gate opening required for target flow"""
        
        if target_flow <= 0:
            return 0.0
            
        # Get current water levels
        levels = self.water_levels.get(gate.gate_id, (2.0, 1.5))
        upstream_level, downstream_level = levels
        
        # Binary search for required opening
        low, high = min_opening, max_opening
        tolerance = 0.01  # 1cm tolerance
        max_iterations = 20
        
        for _ in range(max_iterations):
            mid = (low + high) / 2
            
            # Calculate flow at mid opening
            flow_result = self.calculate_gate_flow(
                gate.gate_id,
                opening_m=mid,
                upstream_level=upstream_level,
                downstream_level=downstream_level
            )
            
            flow = flow_result.flow_rate_m3s
            
            if abs(flow - target_flow) < target_flow * 0.05:  # 5% tolerance
                return mid
                
            if flow < target_flow:
                low = mid
            else:
                high = mid
                
            if high - low < tolerance:
                break
                
        return (low + high) / 2
        
    def generate_daily_operation_plan(
        self,
        date: datetime,
        irrigation_schedule: Dict[int, List[Tuple[float, float]]]  # Zone -> [(start_hour, flow)]
    ) -> Dict[str, List[Tuple[datetime, float]]]:
        """Generate daily operation plan for all gates"""
        
        operation_plan = {}
        
        for zone, schedule in irrigation_schedule.items():
            zone_gates = self.gate_manager.get_gates_by_zone(zone)
            
            for start_hour, target_flow in schedule:
                # Calculate start time
                start_time = date.replace(hour=int(start_hour), minute=int((start_hour % 1) * 60))
                
                # Optimize gates for this period
                results = self.optimize_gate_settings({zone: target_flow})
                
                # Add to operation plan
                for result in results:
                    if result.gate_id not in operation_plan:
                        operation_plan[result.gate_id] = []
                        
                    operation_plan[result.gate_id].append(
                        (start_time, result.actual_opening_m)
                    )
                    
        return operation_plan
        
    def export_gate_database(self, filename: str) -> None:
        """Export gate database with all properties"""
        
        data = []
        
        for gate_id, gate in self.gate_manager.gates.items():
            gate_data = {
                "gate_id": gate_id,
                "shape": gate.shape.value,
                "control_type": gate.control_type.value,
                "width_m": gate.width_m,
                "diameter_m": gate.diameter_m,
                "height_m": gate.height_m,
                "sill_elevation_m": gate.sill_elevation_m,
                "drop_height_m": gate.drop_height_m,
                "has_drop": gate.has_drop_structure,
                "is_automatic": gate.is_automatic,
                "zone": gate.zone,
                "latitude": gate.latitude,
                "longitude": gate.longitude,
                "max_flow_m3s": gate.max_flow_m3s
            }
            
            # Add calibration
            if gate.calibration:
                gate_data.update({
                    "k1": gate.calibration.k1,
                    "k2": gate.calibration.k2,
                    "confidence": gate.calibration.confidence,
                    "calibration_source": gate.calibration.source
                })
                
            # Add control levels
            if gate.control_levels:
                levels = gate.control_levels.get_available_openings()
                for i, level in enumerate(levels):
                    gate_data[f"L{i+1}"] = level
                    
            data.append(gate_data)
            
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Exported gate database to {filename}")
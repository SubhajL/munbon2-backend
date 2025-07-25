"""
Feasibility checker for gravity flow delivery
Verifies if water can reach target sections by gravity alone
"""

import logging
from typing import List, Dict, Optional
from models import (
    TargetDelivery, OptimizationConstraints,
    ElevationCheck, DepthCheck
)
from hydraulic_engine import HydraulicEngine

logger = logging.getLogger(__name__)

class FeasibilityChecker:
    def __init__(self):
        self.hydraulic_engine = HydraulicEngine()
        self.elevation_data = {
            "Source": 221.0,
            "M(0,0)": 220.9,
            "M(0,2)": 220.7,
            "Zone_1": 219.0,
            "Zone_2": 217.5,
            "Zone_3": 217.0,
            "Zone_4": 216.5,
            "Zone_5": 215.5,
            "Zone_6": 215.5
        }
        
        # Path definitions (would come from network topology)
        self.delivery_paths = {
            "Zone_1": ["Source", "M(0,0)", "M(0,1)", "Zone_1"],
            "Zone_2": ["Source", "M(0,0)", "M(0,2)", "Zone_2"],
            "Zone_3": ["Source", "M(0,0)", "M(0,3)", "Zone_3"],
            "Zone_4": ["Source", "M(0,0)", "M(0,4)", "Zone_4"],
            "Zone_5": ["Source", "M(0,0)", "M(0,5)", "Zone_5"],
            "Zone_6": ["Source", "M(0,0)", "M(0,6)", "Zone_6"]
        }
    
    async def check_all_deliveries(
        self,
        target_deliveries: List[TargetDelivery],
        source_elevation: float,
        constraints: OptimizationConstraints
    ) -> 'FeasibilityResults':
        """Check feasibility for all target deliveries"""
        
        results = FeasibilityResults()
        
        for delivery in target_deliveries:
            zone_id = f"Zone_{delivery.zone}"
            
            # Get delivery path
            if zone_id not in self.delivery_paths:
                results.infeasible_sections.append(delivery.section_id)
                results.warnings.append(f"No path defined for {zone_id}")
                continue
            
            path = self.delivery_paths[zone_id]
            
            # Check elevation feasibility
            elevation_check = await self.check_elevation_feasibility(
                path[0],  # Source
                zone_id,
                delivery.required_flow_m3s
            )
            
            if not elevation_check.feasible:
                results.infeasible_sections.append(delivery.section_id)
                results.warnings.append(
                    f"{delivery.section_id}: Insufficient elevation head. "
                    f"Required: {elevation_check.required_head:.2f}m, "
                    f"Available: {elevation_check.available_head:.2f}m"
                )
            
            # Check minimum depths
            depth_check = await self.check_minimum_depths(
                path,
                delivery.required_flow_m3s
            )
            
            if not depth_check.feasible:
                results.infeasible_sections.extend(depth_check.critical_sections)
                for section, violation in depth_check.depth_violations.items():
                    results.warnings.append(
                        f"{section}: Minimum depth violation. "
                        f"Required: {constraints.min_depth_m}m, "
                        f"Actual: {violation:.2f}m"
                    )
        
        results.all_feasible = len(results.infeasible_sections) == 0
        return results
    
    async def check_elevation_feasibility(
        self,
        source_node: str,
        target_section: str,
        required_flow_m3s: float
    ) -> ElevationCheck:
        """Check if elevation difference allows gravity flow"""
        
        source_elev = self.elevation_data.get(source_node, 221.0)
        target_elev = self.elevation_data.get(target_section, 215.0)
        
        # Calculate total available head
        available_head = source_elev - target_elev
        
        # Estimate losses
        path = self.delivery_paths.get(target_section, [])
        losses = await self._estimate_total_losses(path, required_flow_m3s)
        
        # Required head = losses + minimum operating depth
        min_depth = 0.3
        required_head = losses['total'] + min_depth
        
        return ElevationCheck(
            feasible=available_head >= required_head,
            available_head=available_head,
            required_head=required_head,
            total_losses=losses['total'],
            loss_breakdown=losses
        )
    
    async def check_minimum_depths(
        self,
        path_nodes: List[str],
        required_flow_m3s: float
    ) -> DepthCheck:
        """Check if minimum depths can be maintained along path"""
        
        critical_sections = []
        depth_violations = {}
        
        # Check each canal section
        for i in range(len(path_nodes) - 1):
            canal_id = f"{path_nodes[i]}->{path_nodes[i+1]}"
            
            # Calculate expected depth for given flow
            try:
                canal_data = await self.hydraulic_engine.get_canal_characteristics(canal_id)
                
                # Simple depth estimation based on flow
                estimated_depth = self._estimate_flow_depth(
                    required_flow_m3s,
                    canal_data.bottom_width_m,
                    canal_data.side_slope
                )
                
                if estimated_depth < 0.3:  # minimum depth threshold
                    critical_sections.append(canal_id)
                    depth_violations[canal_id] = estimated_depth
                    
            except Exception as e:
                logger.warning(f"Could not check depth for {canal_id}: {e}")
        
        return DepthCheck(
            feasible=len(critical_sections) == 0,
            all_depths_met=len(critical_sections) == 0,
            critical_sections=critical_sections,
            depth_violations=depth_violations
        )
    
    async def _estimate_total_losses(
        self,
        path: List[str],
        flow_m3s: float
    ) -> Dict[str, float]:
        """Estimate total head losses along path"""
        
        losses = {
            'friction': 0.0,
            'minor': 0.0,
            'gate': 0.0,
            'total': 0.0
        }
        
        # Friction losses for each canal section
        for i in range(len(path) - 1):
            canal_id = f"{path[i]}->{path[i+1]}"
            
            try:
                canal_data = await self.hydraulic_engine.get_canal_characteristics(canal_id)
                friction_result = await self.hydraulic_engine.calculate_friction_loss(
                    canal_id,
                    flow_m3s,
                    canal_data
                )
                losses['friction'] += friction_result.friction_loss
            except:
                # Estimate based on typical values
                length = 1000  # typical section length
                losses['friction'] += 0.0002 * length  # typical slope * length
        
        # Minor losses (bends, transitions) - 10% of friction
        losses['minor'] = 0.1 * losses['friction']
        
        # Gate losses - assume 0.1m per gate
        num_gates = len(path) - 1
        losses['gate'] = 0.1 * num_gates
        
        losses['total'] = losses['friction'] + losses['minor'] + losses['gate']
        
        return losses
    
    def _estimate_flow_depth(
        self,
        flow_m3s: float,
        bottom_width: float,
        side_slope: float
    ) -> float:
        """Simple flow depth estimation"""
        # Assume typical velocity of 1.0 m/s
        velocity = 1.0
        area = flow_m3s / velocity
        
        # For trapezoidal channel: A = y(b + my)
        # Solve quadratic: my² + by - A = 0
        a = side_slope
        b = bottom_width
        c = -area
        
        if a == 0:
            # Rectangular channel
            depth = area / bottom_width
        else:
            # Quadratic formula
            discriminant = b**2 + 4*a*area
            depth = (-b + (discriminant**0.5)) / (2*a)
        
        return max(0, depth)
    
    def get_recommendations(
        self,
        elevation_check: ElevationCheck,
        depth_check: DepthCheck
    ) -> List[str]:
        """Generate recommendations based on feasibility checks"""
        
        recommendations = []
        
        if not elevation_check.feasible:
            deficit = elevation_check.required_head - elevation_check.available_head
            recommendations.append(
                f"Elevation deficit of {deficit:.2f}m. Consider: "
                f"1) Reducing flow rate, 2) Cleaning channels to reduce friction, "
                f"3) Optimizing gate operations"
            )
        
        if not depth_check.all_depths_met:
            recommendations.append(
                f"Minimum depth violations in {len(depth_check.critical_sections)} sections. "
                f"Consider: 1) Increasing flow rate, 2) Check for sediment buildup, "
                f"3) Adjust gate operations upstream"
            )
        
        if elevation_check.total_losses > 2.0:
            recommendations.append(
                f"High total losses ({elevation_check.total_losses:.2f}m). "
                f"Channel maintenance recommended to reduce friction losses"
            )
        
        return recommendations


class FeasibilityResults:
    """Container for feasibility check results"""
    def __init__(self):
        self.all_feasible = True
        self.infeasible_sections = []
        self.warnings = []
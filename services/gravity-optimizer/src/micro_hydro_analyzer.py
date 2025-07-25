"""
Micro-hydro potential analyzer for automated gates
Identifies locations where energy can be recovered from gravity flow
"""

import numpy as np
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MicroHydroSite:
    gate_id: str
    head_m: float
    flow_m3s: float
    power_potential_kW: float
    annual_energy_MWh: float
    payback_years: float
    co2_reduction_tons: float
    feasibility_score: float

class MicroHydroAnalyzer:
    def __init__(self):
        self.gravity = 9.81
        self.water_density = 1000
        self.turbine_efficiency = 0.85
        self.generator_efficiency = 0.95
        self.availability_factor = 0.90
        
        # Economic parameters (Thailand specific)
        self.electricity_price_thb_kwh = 4.5
        self.installation_cost_thb_kw = 80000
        self.om_cost_percent = 0.03
        self.discount_rate = 0.08
        self.project_lifetime_years = 20
    
    def analyze_network_potential(
        self,
        gate_flows: Dict[str, Dict[str, float]],
        automated_gates: List[str]
    ) -> Dict[str, MicroHydroSite]:
        """Analyze entire network for micro-hydro potential"""
        
        potential_sites = {}
        
        for gate_id in automated_gates:
            if gate_id in gate_flows:
                flow_data = gate_flows[gate_id]
                
                site = self.evaluate_site(
                    gate_id,
                    flow_data.get('head_m', 0),
                    flow_data.get('flow_m3s', 0),
                    flow_data.get('operating_hours', 8760)
                )
                
                if site.feasibility_score > 0.6:  # Feasibility threshold
                    potential_sites[gate_id] = site
        
        return potential_sites
    
    def evaluate_site(
        self,
        gate_id: str,
        head_m: float,
        avg_flow_m3s: float,
        operating_hours: float = 8760
    ) -> MicroHydroSite:
        """Evaluate micro-hydro potential at a specific gate"""
        
        # Calculate power potential
        hydraulic_power = self.water_density * self.gravity * avg_flow_m3s * head_m / 1000  # kW
        electrical_power = hydraulic_power * self.turbine_efficiency * self.generator_efficiency
        
        # Annual energy production
        annual_energy = electrical_power * operating_hours * self.availability_factor / 1000  # MWh
        
        # Economic analysis
        capital_cost = electrical_power * self.installation_cost_thb_kw
        annual_revenue = annual_energy * 1000 * self.electricity_price_thb_kwh
        annual_om_cost = capital_cost * self.om_cost_percent
        
        # Simple payback period
        if annual_revenue > annual_om_cost:
            payback_years = capital_cost / (annual_revenue - annual_om_cost)
        else:
            payback_years = 999  # Not economically viable
        
        # CO2 reduction (Thailand grid emission factor)
        co2_reduction = annual_energy * 0.5  # tons CO2/MWh
        
        # Feasibility score (0-1)
        feasibility_score = self._calculate_feasibility_score(
            electrical_power,
            head_m,
            avg_flow_m3s,
            payback_years
        )
        
        return MicroHydroSite(
            gate_id=gate_id,
            head_m=head_m,
            flow_m3s=avg_flow_m3s,
            power_potential_kW=electrical_power,
            annual_energy_MWh=annual_energy,
            payback_years=payback_years,
            co2_reduction_tons=co2_reduction,
            feasibility_score=feasibility_score
        )
    
    def _calculate_feasibility_score(
        self,
        power_kw: float,
        head_m: float,
        flow_m3s: float,
        payback_years: float
    ) -> float:
        """Calculate overall feasibility score"""
        
        score = 0.0
        
        # Power score (0-0.3)
        if power_kw >= 50:
            score += 0.3
        elif power_kw >= 20:
            score += 0.2
        elif power_kw >= 5:
            score += 0.1
        
        # Head score (0-0.2)
        if head_m >= 2.0:
            score += 0.2
        elif head_m >= 1.0:
            score += 0.1
        
        # Flow consistency score (0-0.2)
        if flow_m3s >= 1.0:
            score += 0.2
        elif flow_m3s >= 0.5:
            score += 0.1
        
        # Economic score (0-0.3)
        if payback_years <= 5:
            score += 0.3
        elif payback_years <= 10:
            score += 0.2
        elif payback_years <= 15:
            score += 0.1
        
        return min(score, 1.0)
    
    def optimize_turbine_selection(
        self,
        head_m: float,
        flow_m3s: float
    ) -> Dict[str, any]:
        """Select optimal turbine type based on site characteristics"""
        
        # Specific speed calculation
        power_kw = self.water_density * self.gravity * flow_m3s * head_m / 1000
        specific_speed = self._calculate_specific_speed(flow_m3s, head_m)
        
        # Turbine selection logic
        if head_m < 2 and flow_m3s > 1:
            turbine_type = "Propeller/Kaplan"
            efficiency = 0.90
        elif head_m < 5 and flow_m3s < 2:
            turbine_type = "Cross-flow"
            efficiency = 0.85
        elif head_m > 5:
            turbine_type = "Turgo"
            efficiency = 0.87
        else:
            turbine_type = "Propeller"
            efficiency = 0.85
        
        return {
            "turbine_type": turbine_type,
            "expected_efficiency": efficiency,
            "specific_speed": specific_speed,
            "rated_power_kw": power_kw * efficiency,
            "recommended_diameter_m": self._estimate_runner_diameter(flow_m3s, head_m)
        }
    
    def _calculate_specific_speed(self, flow_m3s: float, head_m: float) -> float:
        """Calculate specific speed for turbine selection"""
        # Assume synchronous speed of 1000 rpm for small hydro
        n = 1000
        ns = n * np.sqrt(flow_m3s) / (head_m ** 0.75)
        return ns
    
    def _estimate_runner_diameter(self, flow_m3s: float, head_m: float) -> float:
        """Estimate turbine runner diameter"""
        # Empirical formula for runner diameter
        velocity = np.sqrt(2 * self.gravity * head_m)
        area = flow_m3s / (0.4 * velocity)  # Assume 40% of theoretical velocity
        diameter = 2 * np.sqrt(area / np.pi)
        return diameter
    
    def calculate_grid_integration_requirements(
        self,
        power_kw: float
    ) -> Dict[str, any]:
        """Calculate requirements for grid integration"""
        
        requirements = {
            "inverter_size_kva": power_kw * 1.1,  # 10% oversizing
            "protection_equipment": [],
            "grid_connection_voltage": "400V",
            "estimated_connection_cost_thb": 0
        }
        
        # Protection requirements based on size
        if power_kw < 10:
            requirements["protection_equipment"] = [
                "Over/under voltage relay",
                "Over/under frequency relay",
                "Anti-islanding protection"
            ]
            requirements["estimated_connection_cost_thb"] = 150000
        elif power_kw < 100:
            requirements["protection_equipment"] = [
                "Directional overcurrent relay",
                "Earth fault relay",
                "Over/under voltage relay",
                "Over/under frequency relay",
                "Anti-islanding protection",
                "Synchronizing equipment"
            ]
            requirements["grid_connection_voltage"] = "22kV"
            requirements["estimated_connection_cost_thb"] = 500000
        else:
            requirements["protection_equipment"] = [
                "Full protection panel",
                "SCADA interface",
                "Remote monitoring"
            ]
            requirements["grid_connection_voltage"] = "22kV"
            requirements["estimated_connection_cost_thb"] = 1000000
        
        return requirements
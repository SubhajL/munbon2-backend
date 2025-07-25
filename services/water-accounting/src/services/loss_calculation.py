"""Loss calculation service for transit losses"""

import math
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LossCalculationService:
    """Service for calculating water transit losses"""
    
    def __init__(self):
        # Default loss coefficients
        self.seepage_rates = {
            "earthen": 0.025,      # 2.5% per km
            "lined": 0.010,        # 1.0% per km
            "concrete": 0.005,     # 0.5% per km
            "pipe": 0.002          # 0.2% per km
        }
        
        # Evaporation coefficients (simplified Penman)
        self.evap_coefficient = 0.0001  # m/hour base rate
    
    async def calculate_transit_losses(
        self,
        flow_data: Dict,
        canal_characteristics: Dict,
        environmental_conditions: Dict
    ) -> Dict:
        """
        Calculate total transit losses including seepage and evaporation
        
        Args:
            flow_data: Flow rate, volume, transit time
            canal_characteristics: Canal type, length, dimensions
            environmental_conditions: Temperature, humidity, wind
            
        Returns:
            Dict with loss breakdown and total losses
        """
        # Extract parameters
        flow_rate_m3s = flow_data.get("flow_rate_m3s", 0)
        transit_time_hours = flow_data.get("transit_time_hours", 0)
        volume_m3 = flow_data.get("volume_m3", 0)
        
        canal_length_km = canal_characteristics.get("length_km", 0)
        canal_type = canal_characteristics.get("type", "earthen")
        canal_width_m = canal_characteristics.get("width_m", 5.0)
        water_depth_m = canal_characteristics.get("water_depth_m", 1.0)
        
        # Calculate seepage losses
        seepage_loss = await self._calculate_seepage_loss(
            volume_m3, canal_length_km, canal_type, transit_time_hours
        )
        
        # Calculate evaporation losses
        evaporation_loss = await self._calculate_evaporation_loss(
            canal_length_km, canal_width_m, water_depth_m,
            transit_time_hours, environmental_conditions
        )
        
        # Calculate operational losses (spills, overflows)
        operational_loss = await self._calculate_operational_loss(
            volume_m3, flow_rate_m3s
        )
        
        # Total losses
        total_loss_m3 = seepage_loss + evaporation_loss + operational_loss
        loss_percentage = (total_loss_m3 / volume_m3 * 100) if volume_m3 > 0 else 0
        
        return {
            "total_loss_m3": total_loss_m3,
            "loss_percentage": loss_percentage,
            "breakdown": {
                "seepage_m3": seepage_loss,
                "evaporation_m3": evaporation_loss,
                "operational_m3": operational_loss
            },
            "calculation_parameters": {
                "canal_length_km": canal_length_km,
                "canal_type": canal_type,
                "transit_time_hours": transit_time_hours,
                "flow_rate_m3s": flow_rate_m3s
            }
        }
    
    async def _calculate_seepage_loss(
        self,
        volume_m3: float,
        canal_length_km: float,
        canal_type: str,
        transit_time_hours: float
    ) -> float:
        """Calculate seepage losses based on canal characteristics"""
        
        # Get seepage rate for canal type
        seepage_rate_per_km = self.seepage_rates.get(canal_type, 0.025)
        
        # Adjust for transit time (longer time = more seepage)
        time_factor = min(transit_time_hours / 24, 1.0)  # Cap at 1 day
        
        # Calculate seepage loss
        seepage_loss = volume_m3 * seepage_rate_per_km * canal_length_km * (1 + time_factor)
        
        return seepage_loss
    
    async def _calculate_evaporation_loss(
        self,
        canal_length_km: float,
        canal_width_m: float,
        water_depth_m: float,
        transit_time_hours: float,
        environmental_conditions: Dict
    ) -> float:
        """Calculate evaporation losses using simplified Penman equation"""
        
        # Environmental parameters
        temp_c = environmental_conditions.get("temperature_c", 30)
        humidity_pct = environmental_conditions.get("humidity_percent", 50)
        wind_speed_ms = environmental_conditions.get("wind_speed_ms", 2)
        solar_radiation = environmental_conditions.get("solar_radiation_wm2", 250)
        
        # Water surface area
        surface_area_m2 = canal_length_km * 1000 * canal_width_m
        
        # Simplified evaporation rate calculation
        # Base rate adjusted for environmental factors
        temp_factor = 1 + (temp_c - 20) * 0.02  # 2% increase per degree above 20C
        humidity_factor = (100 - humidity_pct) / 100  # Lower humidity = more evaporation
        wind_factor = 1 + wind_speed_ms * 0.1  # 10% increase per m/s wind
        radiation_factor = solar_radiation / 250  # Normalized to typical value
        
        # Combined evaporation rate (m/hour)
        evap_rate_m_hr = (self.evap_coefficient * temp_factor * 
                          humidity_factor * wind_factor * radiation_factor)
        
        # Total evaporation volume
        evaporation_m3 = surface_area_m2 * evap_rate_m_hr * transit_time_hours
        
        # Limit evaporation to reasonable percentage of depth
        max_evap = surface_area_m2 * water_depth_m * 0.05  # Max 5% of water depth
        evaporation_m3 = min(evaporation_m3, max_evap)
        
        return evaporation_m3
    
    async def _calculate_operational_loss(
        self,
        volume_m3: float,
        flow_rate_m3s: float
    ) -> float:
        """Calculate operational losses (spills, gate leakage, etc.)"""
        
        # Base operational loss percentage
        base_loss_pct = 0.01  # 1% base loss
        
        # Adjust for flow rate (higher flows = more turbulence/spills)
        if flow_rate_m3s > 10:
            flow_factor = 1.5
        elif flow_rate_m3s > 5:
            flow_factor = 1.2
        else:
            flow_factor = 1.0
        
        operational_loss = volume_m3 * base_loss_pct * flow_factor
        
        return operational_loss
    
    async def estimate_loss_uncertainty(self, loss_calculation: Dict) -> Dict:
        """
        Estimate uncertainty in loss calculations
        
        Returns:
            Dict with confidence intervals and uncertainty factors
        """
        total_loss = loss_calculation["total_loss_m3"]
        breakdown = loss_calculation["breakdown"]
        
        # Uncertainty percentages for each loss type
        uncertainties = {
            "seepage": 0.20,      # ±20% uncertainty
            "evaporation": 0.30,  # ±30% uncertainty
            "operational": 0.40   # ±40% uncertainty
        }
        
        # Calculate uncertainty bounds
        seepage_uncertainty = breakdown["seepage_m3"] * uncertainties["seepage"]
        evap_uncertainty = breakdown["evaporation_m3"] * uncertainties["evaporation"]
        op_uncertainty = breakdown["operational_m3"] * uncertainties["operational"]
        
        # Total uncertainty (root sum of squares)
        total_uncertainty = math.sqrt(
            seepage_uncertainty**2 + evap_uncertainty**2 + op_uncertainty**2
        )
        
        # Confidence intervals
        lower_bound = max(0, total_loss - 1.96 * total_uncertainty)  # 95% CI
        upper_bound = total_loss + 1.96 * total_uncertainty
        
        # Confidence score (0-1)
        confidence_score = 1.0 / (1.0 + total_uncertainty / total_loss) if total_loss > 0 else 0.5
        
        return {
            "total_loss_m3": total_loss,
            "uncertainty_m3": total_uncertainty,
            "confidence_interval_95": {
                "lower_m3": lower_bound,
                "upper_m3": upper_bound
            },
            "confidence_score": confidence_score,
            "uncertainty_breakdown": {
                "seepage_uncertainty_m3": seepage_uncertainty,
                "evaporation_uncertainty_m3": evap_uncertainty,
                "operational_uncertainty_m3": op_uncertainty
            }
        }
    
    async def calibrate_loss_model(
        self,
        measured_losses: List[Dict],
        canal_characteristics: Dict
    ) -> Dict:
        """
        Calibrate loss model based on measured data
        
        Args:
            measured_losses: Historical loss measurements
            canal_characteristics: Canal properties
            
        Returns:
            Dict with calibrated parameters
        """
        if not measured_losses:
            return {
                "calibrated": False,
                "message": "No measured data for calibration"
            }
        
        canal_type = canal_characteristics.get("type", "earthen")
        current_rate = self.seepage_rates.get(canal_type, 0.025)
        
        # Calculate average measured loss rate
        total_measured_loss = sum(m["loss_m3"] for m in measured_losses)
        total_volume = sum(m["volume_m3"] for m in measured_losses)
        total_length = sum(m["canal_length_km"] for m in measured_losses)
        
        if total_volume > 0 and total_length > 0:
            measured_rate = total_measured_loss / (total_volume * total_length)
            
            # Apply calibration factor
            calibration_factor = measured_rate / current_rate
            calibrated_rate = current_rate * calibration_factor
            
            # Update seepage rate
            self.seepage_rates[canal_type] = calibrated_rate
            
            return {
                "calibrated": True,
                "canal_type": canal_type,
                "original_rate": current_rate,
                "calibrated_rate": calibrated_rate,
                "calibration_factor": calibration_factor,
                "samples_used": len(measured_losses)
            }
        
        return {
            "calibrated": False,
            "message": "Insufficient data for calibration"
        }
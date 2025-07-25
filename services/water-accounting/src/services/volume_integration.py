"""Volume integration service for calculating water volumes from flow rates"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
from scipy import integrate

logger = logging.getLogger(__name__)

class VolumeIntegrationService:
    """Service for integrating flow rates to calculate volumes"""
    
    def __init__(self):
        self.methods = {
            "trapezoidal": self._trapezoidal_integration,
            "simpson": self._simpson_integration,
            "rectangular": self._rectangular_integration
        }
    
    async def integrate_flow_to_volume(
        self,
        flow_readings: List[Dict],
        method: str = "trapezoidal"
    ) -> Dict:
        """
        Integrate flow rate measurements to calculate total volume
        
        Args:
            flow_readings: List of {timestamp, flow_rate_m3s} readings
            method: Integration method (trapezoidal, simpson, rectangular)
            
        Returns:
            Dict with total_volume_m3, integration_details
        """
        if not flow_readings or len(flow_readings) < 2:
            return {
                "total_volume_m3": 0.0,
                "integration_details": {
                    "method": method,
                    "num_readings": len(flow_readings),
                    "error": "Insufficient readings for integration"
                }
            }
        
        # Sort readings by timestamp
        sorted_readings = sorted(flow_readings, key=lambda x: x["timestamp"])
        
        # Extract time and flow arrays
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in sorted_readings]
        flow_rates = [r["flow_rate_m3s"] for r in sorted_readings]
        
        # Convert timestamps to seconds from start
        start_time = timestamps[0]
        time_seconds = [(t - start_time).total_seconds() for t in timestamps]
        
        # Apply selected integration method
        integration_func = self.methods.get(method, self._trapezoidal_integration)
        volume_m3 = integration_func(time_seconds, flow_rates)
        
        # Calculate additional metrics
        duration_hours = time_seconds[-1] / 3600
        avg_flow_rate = np.mean(flow_rates)
        peak_flow_rate = max(flow_rates)
        
        return {
            "total_volume_m3": volume_m3,
            "integration_details": {
                "method": method,
                "num_readings": len(flow_readings),
                "duration_hours": duration_hours,
                "start_time": start_time.isoformat(),
                "end_time": timestamps[-1].isoformat(),
                "avg_flow_rate_m3s": avg_flow_rate,
                "peak_flow_rate_m3s": peak_flow_rate,
                "time_resolution_seconds": np.mean(np.diff(time_seconds)) if len(time_seconds) > 1 else 0
            }
        }
    
    def _trapezoidal_integration(self, time_seconds: List[float], flow_rates: List[float]) -> float:
        """Trapezoidal rule integration"""
        return float(np.trapz(flow_rates, time_seconds))
    
    def _simpson_integration(self, time_seconds: List[float], flow_rates: List[float]) -> float:
        """Simpson's rule integration (requires odd number of points)"""
        if len(time_seconds) % 2 == 0:
            # Fall back to trapezoidal for even number of points
            return self._trapezoidal_integration(time_seconds, flow_rates)
        
        return float(integrate.simpson(flow_rates, x=time_seconds))
    
    def _rectangular_integration(self, time_seconds: List[float], flow_rates: List[float]) -> float:
        """Rectangular (left) rule integration"""
        volume = 0.0
        for i in range(len(time_seconds) - 1):
            dt = time_seconds[i + 1] - time_seconds[i]
            volume += flow_rates[i] * dt
        return volume
    
    async def calculate_cumulative_volume(
        self,
        flow_readings: List[Dict],
        interval_minutes: int = 60
    ) -> List[Dict]:
        """
        Calculate cumulative volume at regular intervals
        
        Args:
            flow_readings: List of flow readings
            interval_minutes: Interval for cumulative calculations
            
        Returns:
            List of cumulative volume points
        """
        if not flow_readings:
            return []
        
        sorted_readings = sorted(flow_readings, key=lambda x: x["timestamp"])
        cumulative_points = []
        
        # Group readings by interval
        start_time = datetime.fromisoformat(sorted_readings[0]["timestamp"])
        current_interval_start = start_time
        interval_readings = []
        cumulative_total = 0.0
        
        for reading in sorted_readings:
            reading_time = datetime.fromisoformat(reading["timestamp"])
            
            # Check if we've moved to next interval
            if reading_time >= current_interval_start + timedelta(minutes=interval_minutes):
                # Calculate volume for completed interval
                if interval_readings:
                    interval_volume = await self.integrate_flow_to_volume(interval_readings)
                    cumulative_total += interval_volume["total_volume_m3"]
                    
                    cumulative_points.append({
                        "timestamp": current_interval_start.isoformat(),
                        "cumulative_volume_m3": cumulative_total,
                        "interval_volume_m3": interval_volume["total_volume_m3"],
                        "avg_flow_rate_m3s": interval_volume["integration_details"]["avg_flow_rate_m3s"]
                    })
                
                # Move to next interval
                current_interval_start += timedelta(minutes=interval_minutes)
                interval_readings = []
            
            interval_readings.append(reading)
        
        # Handle final interval
        if interval_readings:
            interval_volume = await self.integrate_flow_to_volume(interval_readings)
            cumulative_total += interval_volume["total_volume_m3"]
            
            cumulative_points.append({
                "timestamp": current_interval_start.isoformat(),
                "cumulative_volume_m3": cumulative_total,
                "interval_volume_m3": interval_volume["total_volume_m3"],
                "avg_flow_rate_m3s": interval_volume["integration_details"]["avg_flow_rate_m3s"]
            })
        
        return cumulative_points
    
    async def validate_flow_data(self, flow_readings: List[Dict]) -> Dict:
        """
        Validate flow data quality and identify issues
        
        Returns:
            Dict with validation results and quality score
        """
        if not flow_readings:
            return {
                "valid": False,
                "quality_score": 0.0,
                "issues": ["No flow readings provided"]
            }
        
        issues = []
        
        # Check for minimum readings
        if len(flow_readings) < 2:
            issues.append("Insufficient readings for integration")
        
        # Check for negative flow rates
        negative_flows = [r for r in flow_readings if r.get("flow_rate_m3s", 0) < 0]
        if negative_flows:
            issues.append(f"Found {len(negative_flows)} negative flow readings")
        
        # Check for data gaps
        sorted_readings = sorted(flow_readings, key=lambda x: x["timestamp"])
        timestamps = [datetime.fromisoformat(r["timestamp"]) for r in sorted_readings]
        
        if len(timestamps) > 1:
            time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                          for i in range(len(timestamps)-1)]
            median_interval = np.median(time_diffs)
            
            # Identify large gaps (> 3x median interval)
            large_gaps = [(i, diff) for i, diff in enumerate(time_diffs) 
                          if diff > 3 * median_interval]
            
            if large_gaps:
                issues.append(f"Found {len(large_gaps)} large time gaps in data")
        
        # Calculate quality score
        quality_score = 1.0
        if issues:
            quality_score -= 0.2 * len(issues)
        quality_score = max(0.0, quality_score)
        
        # Check for outliers
        flow_rates = [r.get("flow_rate_m3s", 0) for r in flow_readings]
        if len(flow_rates) > 3:
            q1, q3 = np.percentile(flow_rates, [25, 75])
            iqr = q3 - q1
            outliers = [f for f in flow_rates if f < q1 - 1.5*iqr or f > q3 + 1.5*iqr]
            if outliers:
                issues.append(f"Found {len(outliers)} potential outlier readings")
                quality_score *= 0.9
        
        return {
            "valid": len(issues) == 0,
            "quality_score": quality_score,
            "issues": issues,
            "statistics": {
                "num_readings": len(flow_readings),
                "duration_hours": (timestamps[-1] - timestamps[0]).total_seconds() / 3600 if len(timestamps) > 1 else 0,
                "avg_interval_seconds": np.mean(time_diffs) if len(timestamps) > 1 else 0
            }
        }
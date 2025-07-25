"""
Travel time predictor for water delivery
Calculates how long water takes to reach different zones
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TravelTimeSegment:
    segment_id: str
    length_m: float
    velocity_ms: float
    travel_time_s: float
    flow_m3s: float
    depth_m: float
    
@dataclass
class DeliveryPrediction:
    destination: str
    path: List[str]
    total_distance_m: float
    travel_time_hours: float
    arrival_time: datetime
    segments: List[TravelTimeSegment]
    confidence_level: float

class TravelTimePredictor:
    def __init__(self):
        # Canal network data (would come from database)
        self.canal_lengths = {
            "Source->M(0,0)": 500,
            "M(0,0)->M(0,1)": 1000,
            "M(0,0)->M(0,2)": 1200,
            "M(0,0)->M(0,3)": 1500,
            "M(0,0)->M(0,4)": 1800,
            "M(0,0)->M(0,5)": 2000,
            "M(0,0)->M(0,6)": 2200,
            "M(0,1)->Zone_1": 800,
            "M(0,2)->Zone_2": 800,
            "M(0,3)->Zone_3": 1000,
            "M(0,4)->Zone_4": 1000,
            "M(0,5)->Zone_5": 1200,
            "M(0,6)->Zone_6": 1200
        }
        
        # Historical velocity data for calibration
        self.velocity_factors = {
            "clean": 1.0,
            "moderate_sediment": 0.85,
            "heavy_sediment": 0.7,
            "dry_startup": 0.5
        }
    
    def predict_delivery_times(
        self,
        gate_settings: Dict[str, Dict[str, float]],
        target_zones: List[str],
        start_time: datetime = None
    ) -> Dict[str, DeliveryPrediction]:
        """Predict delivery times to multiple zones"""
        
        if start_time is None:
            start_time = datetime.now()
        
        predictions = {}
        
        for zone in target_zones:
            path = self._get_path_to_zone(zone)
            if path:
                prediction = self._calculate_travel_time(
                    path,
                    gate_settings,
                    start_time
                )
                predictions[zone] = prediction
        
        return predictions
    
    def _calculate_travel_time(
        self,
        path: List[str],
        gate_settings: Dict[str, Dict[str, float]],
        start_time: datetime
    ) -> DeliveryPrediction:
        """Calculate travel time along a specific path"""
        
        segments = []
        total_time_s = 0
        total_distance_m = 0
        
        for i in range(len(path) - 1):
            segment_id = f"{path[i]}->{path[i+1]}"
            
            # Get segment properties
            length = self.canal_lengths.get(segment_id, 1000)
            
            # Get flow and calculate velocity
            if segment_id in gate_settings:
                flow = gate_settings[segment_id].get('flow_m3s', 0)
                depth = gate_settings[segment_id].get('depth_m', 1.0)
            else:
                flow = 2.0  # Default flow
                depth = 1.0  # Default depth
            
            # Calculate velocity using continuity and Manning's equation
            velocity = self._calculate_segment_velocity(
                flow,
                depth,
                segment_id
            )
            
            # Calculate travel time
            travel_time = length / velocity if velocity > 0 else float('inf')
            
            segment = TravelTimeSegment(
                segment_id=segment_id,
                length_m=length,
                velocity_ms=velocity,
                travel_time_s=travel_time,
                flow_m3s=flow,
                depth_m=depth
            )
            
            segments.append(segment)
            total_time_s += travel_time
            total_distance_m += length
        
        # Convert to hours
        travel_time_hours = total_time_s / 3600
        arrival_time = start_time + timedelta(hours=travel_time_hours)
        
        # Calculate confidence level
        confidence = self._calculate_confidence(segments)
        
        return DeliveryPrediction(
            destination=path[-1],
            path=path,
            total_distance_m=total_distance_m,
            travel_time_hours=travel_time_hours,
            arrival_time=arrival_time,
            segments=segments,
            confidence_level=confidence
        )
    
    def _calculate_segment_velocity(
        self,
        flow_m3s: float,
        depth_m: float,
        segment_id: str
    ) -> float:
        """Calculate flow velocity in a canal segment"""
        
        # Get canal geometry (simplified)
        bottom_width = 3.0  # Default
        side_slope = 1.5
        
        # Calculate flow area
        area = depth_m * (bottom_width + side_slope * depth_m)
        
        # Velocity from continuity equation
        velocity = flow_m3s / area if area > 0 else 0
        
        # Apply correction factors
        condition = self._assess_canal_condition(segment_id)
        velocity *= self.velocity_factors.get(condition, 1.0)
        
        # Limit to reasonable range
        velocity = max(0.1, min(velocity, 2.0))
        
        return velocity
    
    def _assess_canal_condition(self, segment_id: str) -> str:
        """Assess canal condition for velocity correction"""
        # In production, this would query maintenance records
        # For now, return default condition
        return "clean"
    
    def _get_path_to_zone(self, zone: str) -> List[str]:
        """Get the flow path to a specific zone"""
        paths = {
            "Zone_1": ["Source", "M(0,0)", "M(0,1)", "Zone_1"],
            "Zone_2": ["Source", "M(0,0)", "M(0,2)", "Zone_2"],
            "Zone_3": ["Source", "M(0,0)", "M(0,3)", "Zone_3"],
            "Zone_4": ["Source", "M(0,0)", "M(0,4)", "Zone_4"],
            "Zone_5": ["Source", "M(0,0)", "M(0,5)", "Zone_5"],
            "Zone_6": ["Source", "M(0,0)", "M(0,6)", "Zone_6"]
        }
        return paths.get(zone, [])
    
    def _calculate_confidence(self, segments: List[TravelTimeSegment]) -> float:
        """Calculate confidence level of prediction"""
        
        confidence = 1.0
        
        for segment in segments:
            # Reduce confidence for very low or high velocities
            if segment.velocity_ms < 0.3 or segment.velocity_ms > 1.8:
                confidence *= 0.9
            
            # Reduce confidence for low flows
            if segment.flow_m3s < 0.5:
                confidence *= 0.95
            
            # Reduce confidence for shallow depths
            if segment.depth_m < 0.5:
                confidence *= 0.9
        
        return max(0.5, confidence)
    
    def optimize_for_quick_delivery(
        self,
        target_zone: str,
        required_arrival: datetime,
        current_time: datetime = None
    ) -> Dict[str, float]:
        """Calculate required velocities for timely delivery"""
        
        if current_time is None:
            current_time = datetime.now()
        
        # Get path
        path = self._get_path_to_zone(target_zone)
        if not path:
            return {}
        
        # Calculate required travel time
        time_available = (required_arrival - current_time).total_seconds()
        if time_available <= 0:
            logger.warning(f"Required arrival time {required_arrival} has already passed")
            return {}
        
        # Calculate required velocities
        required_velocities = {}
        
        for i in range(len(path) - 1):
            segment_id = f"{path[i]}->{path[i+1]}"
            length = self.canal_lengths.get(segment_id, 1000)
            
            # Equal time distribution (could be optimized)
            segment_time = time_available / (len(path) - 1)
            required_velocity = length / segment_time
            
            # Check if velocity is reasonable
            if required_velocity > 2.0:
                logger.warning(f"Required velocity {required_velocity:.2f} m/s exceeds maximum for {segment_id}")
                required_velocity = 2.0
            
            required_velocities[segment_id] = required_velocity
        
        return required_velocities
    
    def estimate_water_volume_in_transit(
        self,
        active_segments: List[str],
        gate_flows: Dict[str, float]
    ) -> Dict[str, float]:
        """Estimate water volume currently in transit"""
        
        volumes = {}
        total_volume = 0
        
        for segment in active_segments:
            if segment in self.canal_lengths and segment in gate_flows:
                length = self.canal_lengths[segment]
                flow = gate_flows[segment]
                
                # Estimate average area (simplified)
                avg_area = 5.0  # m² (would calculate from geometry)
                
                # Volume = length × area
                volume = length * avg_area
                volumes[segment] = volume
                total_volume += volume
        
        volumes['total'] = total_volume
        return volumes
    
    def predict_dry_channel_startup_time(
        self,
        path: List[str],
        initial_flow_m3s: float
    ) -> float:
        """Predict time to fill dry channels"""
        
        total_time_hours = 0
        
        for i in range(len(path) - 1):
            segment_id = f"{path[i]}->{path[i+1]}"
            length = self.canal_lengths.get(segment_id, 1000)
            
            # Estimate volume to fill (simplified)
            volume_to_fill = length * 5.0 * 0.5  # length × area × fill_depth
            
            # Time to fill
            fill_time_s = volume_to_fill / initial_flow_m3s
            
            # Add wetting time (30% extra for dry soil absorption)
            fill_time_s *= 1.3
            
            total_time_hours += fill_time_s / 3600
        
        return total_time_hours
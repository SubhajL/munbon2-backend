import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial.distance import cdist
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel
import pandas as pd

from models.interpolation import (
    InterpolatedData, InterpolationRequest, SpatialInterpolationGrid,
    InterpolationMethod, DataQuality, ConfidenceScore,
    InterpolationModelMetrics, CalibrationData
)
from db.influxdb import query_sensor_data
from db.redis import cache_interpolation_result, get_cached_interpolation
from utils.spatial import get_section_coordinates, get_network_bounds

class InterpolationEngine:
    """Engine for spatial and temporal data interpolation"""
    
    def __init__(self):
        self.methods = {
            InterpolationMethod.INVERSE_DISTANCE: self._inverse_distance_weighted,
            InterpolationMethod.KRIGING: self._kriging_interpolation,
            InterpolationMethod.HYDRAULIC_MODEL: self._hydraulic_model_interpolation,
            InterpolationMethod.MACHINE_LEARNING: self._ml_interpolation,
            InterpolationMethod.HYBRID: self._hybrid_interpolation
        }
        self.confidence_threshold = 0.7
        self.max_interpolation_distance_km = 5.0
        
    async def interpolate_section(self, section_id: str, parameter: str,
                                timestamp: Optional[datetime] = None) -> InterpolatedData:
        """Interpolate data for a specific section"""
        # Check cache first
        cached = await get_cached_interpolation(section_id, parameter)
        if cached:
            return InterpolatedData(**cached)
        
        # Get section coordinates
        coords = await get_section_coordinates(section_id, None)
        target_point = np.array([[coords["lat"], coords["lon"]]])
        
        # Get nearby sensor data
        sensor_data = await self._get_nearby_sensor_data(
            coords["lat"], coords["lon"], parameter, timestamp
        )
        
        if not sensor_data:
            # No data available, return low confidence estimate
            return self._create_low_confidence_estimate(section_id, parameter, timestamp)
        
        # Choose interpolation method based on data availability
        method = self._select_method(sensor_data, coords)
        
        # Perform interpolation
        value, confidence = await self.methods[method](
            target_point, sensor_data, parameter
        )
        
        # Calculate detailed confidence
        confidence_score = self._calculate_confidence(
            sensor_data, coords, value, method
        )
        
        # Determine data quality
        quality = self._determine_quality(confidence_score.overall)
        
        result = InterpolatedData(
            section_id=section_id,
            timestamp=timestamp or datetime.utcnow(),
            parameter=parameter,
            value=float(value),
            unit=self._get_unit(parameter),
            confidence=confidence_score,
            quality=quality,
            method=method,
            source_sensors=[s["sensor_id"] for s in sensor_data],
            distance_to_nearest_sensor_km=min([s["distance"] for s in sensor_data])
        )
        
        # Cache result
        await cache_interpolation_result(
            section_id, parameter, result.value, 
            result.confidence.overall
        )
        
        return result
    
    async def batch_interpolate(self, request: InterpolationRequest) -> List[InterpolatedData]:
        """Interpolate data for multiple sections"""
        results = []
        
        for section_id in request.section_ids:
            for parameter in request.parameters:
                result = await self.interpolate_section(
                    section_id, parameter, request.timestamp
                )
                results.append(result)
        
        return results
    
    async def generate_spatial_grid(self, parameter: str, 
                                  resolution_m: float) -> SpatialInterpolationGrid:
        """Generate spatial interpolation grid for visualization"""
        # Get network bounds
        bounds = await get_network_bounds()
        
        # Create grid points
        lat_range = np.linspace(bounds["south"], bounds["north"], 
                               int((bounds["north"] - bounds["south"]) * 111000 / resolution_m))
        lon_range = np.linspace(bounds["west"], bounds["east"],
                               int((bounds["east"] - bounds["west"]) * 111000 / resolution_m))
        
        # Get all sensor data
        sensor_data = await self._get_all_sensor_data(parameter)
        
        if not sensor_data:
            raise ValueError("No sensor data available for interpolation")
        
        # Prepare data for interpolation
        sensor_points = np.array([[s["lat"], s["lon"]] for s in sensor_data])
        sensor_values = np.array([s["value"] for s in sensor_data])
        
        # Create meshgrid
        lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
        grid_points = np.column_stack((lat_grid.ravel(), lon_grid.ravel()))
        
        # Interpolate values
        grid_values = griddata(sensor_points, sensor_values, grid_points, method='cubic')
        grid_values = grid_values.reshape(lat_grid.shape)
        
        # Calculate confidence grid
        confidence_grid = self._calculate_grid_confidence(
            grid_points, sensor_points, resolution_m
        ).reshape(lat_grid.shape)
        
        return SpatialInterpolationGrid(
            bounds=bounds,
            resolution_m=resolution_m,
            timestamp=datetime.utcnow(),
            parameter=parameter,
            grid_data=grid_values.tolist(),
            confidence_grid=confidence_grid.tolist(),
            sensor_locations=[{"lat": s["lat"], "lon": s["lon"]} for s in sensor_data]
        )
    
    async def _inverse_distance_weighted(self, target: np.ndarray, 
                                       sensor_data: List[Dict], 
                                       parameter: str) -> Tuple[float, float]:
        """Inverse distance weighted interpolation"""
        points = np.array([[s["lat"], s["lon"]] for s in sensor_data])
        values = np.array([s["value"] for s in sensor_data])
        
        # Calculate distances
        distances = cdist(target, points).flatten()
        
        # Avoid division by zero
        distances[distances == 0] = 1e-10
        
        # Calculate weights (inverse distance with power parameter)
        power = 2
        weights = 1 / (distances ** power)
        weights /= weights.sum()
        
        # Interpolate
        interpolated_value = np.sum(weights * values)
        
        # Confidence based on distance to nearest sensor
        min_distance = distances.min()
        confidence = np.exp(-min_distance / 2.0)  # Exponential decay
        
        return interpolated_value, confidence
    
    async def _kriging_interpolation(self, target: np.ndarray,
                                   sensor_data: List[Dict],
                                   parameter: str) -> Tuple[float, float]:
        """Kriging interpolation using Gaussian Process"""
        points = np.array([[s["lat"], s["lon"]] for s in sensor_data])
        values = np.array([s["value"] for s in sensor_data])
        
        # Define kernel
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(length_scale=0.1, length_scale_bounds=(1e-2, 1e2))
        
        # Create and fit Gaussian Process
        gp = GaussianProcessRegressor(kernel=kernel, alpha=1e-6, normalize_y=True)
        gp.fit(points, values)
        
        # Predict
        y_pred, y_std = gp.predict(target, return_std=True)
        
        # Confidence from prediction variance
        confidence = 1 - (y_std[0] / (values.std() + 1e-6))
        confidence = max(0, min(1, confidence))
        
        return y_pred[0], confidence
    
    async def _hydraulic_model_interpolation(self, target: np.ndarray,
                                           sensor_data: List[Dict],
                                           parameter: str) -> Tuple[float, float]:
        """Interpolation using hydraulic principles"""
        # For water level, consider hydraulic gradient
        if parameter == "water_level":
            # Simplified hydraulic model
            # In reality, would use Manning's equation and channel geometry
            points = np.array([[s["lat"], s["lon"]] for s in sensor_data])
            values = np.array([s["value"] for s in sensor_data])
            
            # Calculate hydraulic gradient
            if len(points) >= 2:
                # Simple linear interpolation along flow path
                distances = cdist(target, points).flatten()
                nearest_idx = np.argmin(distances)
                
                # Find upstream and downstream sensors
                # This is simplified - real implementation would use network topology
                interpolated_value = values[nearest_idx]
                confidence = 0.8  # Higher confidence for hydraulic model
            else:
                interpolated_value = values[0]
                confidence = 0.5
                
            return interpolated_value, confidence
        else:
            # Fall back to IDW for other parameters
            return await self._inverse_distance_weighted(target, sensor_data, parameter)
    
    async def _ml_interpolation(self, target: np.ndarray,
                              sensor_data: List[Dict],
                              parameter: str) -> Tuple[float, float]:
        """Machine learning based interpolation"""
        # Placeholder for ML model
        # In production, would use trained neural network or random forest
        # For now, use Gaussian Process as proxy
        return await self._kriging_interpolation(target, sensor_data, parameter)
    
    async def _hybrid_interpolation(self, target: np.ndarray,
                                  sensor_data: List[Dict],
                                  parameter: str) -> Tuple[float, float]:
        """Hybrid approach combining multiple methods"""
        # Get predictions from multiple methods
        idw_val, idw_conf = await self._inverse_distance_weighted(target, sensor_data, parameter)
        krg_val, krg_conf = await self._kriging_interpolation(target, sensor_data, parameter)
        hyd_val, hyd_conf = await self._hydraulic_model_interpolation(target, sensor_data, parameter)
        
        # Weighted average based on confidence
        weights = np.array([idw_conf, krg_conf, hyd_conf])
        weights /= weights.sum()
        
        values = np.array([idw_val, krg_val, hyd_val])
        interpolated_value = np.sum(weights * values)
        
        # Combined confidence
        confidence = np.mean([idw_conf, krg_conf, hyd_conf])
        
        return interpolated_value, confidence
    
    def _select_method(self, sensor_data: List[Dict], target_coords: Dict) -> InterpolationMethod:
        """Select best interpolation method based on data characteristics"""
        n_sensors = len(sensor_data)
        
        if n_sensors < 3:
            return InterpolationMethod.INVERSE_DISTANCE
        elif n_sensors < 5:
            return InterpolationMethod.KRIGING
        else:
            # Check if hydraulic model is applicable
            min_distance = min([s["distance"] for s in sensor_data])
            if min_distance < 2.0:  # Within 2 km
                return InterpolationMethod.HYDRAULIC_MODEL
            else:
                return InterpolationMethod.HYBRID
    
    def _calculate_confidence(self, sensor_data: List[Dict], target_coords: Dict,
                            interpolated_value: float, method: InterpolationMethod) -> ConfidenceScore:
        """Calculate detailed confidence score"""
        # Spatial coverage
        distances = [s["distance"] for s in sensor_data]
        min_distance = min(distances)
        spatial_coverage = np.exp(-min_distance / self.max_interpolation_distance_km)
        
        # Temporal coverage
        time_deltas = [(datetime.utcnow() - s["timestamp"]).total_seconds() / 3600 
                      for s in sensor_data]
        temporal_coverage = np.exp(-min(time_deltas) / 24)  # Decay over 24 hours
        
        # Model accuracy (method-specific)
        model_accuracy = {
            InterpolationMethod.INVERSE_DISTANCE: 0.7,
            InterpolationMethod.KRIGING: 0.85,
            InterpolationMethod.HYDRAULIC_MODEL: 0.9,
            InterpolationMethod.MACHINE_LEARNING: 0.8,
            InterpolationMethod.HYBRID: 0.88
        }[method]
        
        # Data freshness
        avg_age_hours = np.mean(time_deltas)
        data_freshness = np.exp(-avg_age_hours / 48)  # Decay over 48 hours
        
        # Overall confidence
        overall = np.mean([spatial_coverage, temporal_coverage, model_accuracy, data_freshness])
        
        return ConfidenceScore(
            overall=float(overall),
            spatial_coverage=float(spatial_coverage),
            temporal_coverage=float(temporal_coverage),
            model_accuracy=float(model_accuracy),
            data_freshness=float(data_freshness),
            factors={
                "n_sensors": len(sensor_data),
                "min_distance_km": min_distance,
                "avg_age_hours": avg_age_hours
            }
        )
    
    def _determine_quality(self, confidence: float) -> DataQuality:
        """Determine data quality based on confidence"""
        if confidence >= 0.8:
            return DataQuality.HIGH
        elif confidence >= 0.6:
            return DataQuality.MEDIUM
        elif confidence >= 0.4:
            return DataQuality.LOW
        else:
            return DataQuality.ESTIMATED
    
    def _get_unit(self, parameter: str) -> str:
        """Get unit for parameter"""
        units = {
            "water_level": "m",
            "moisture": "%",
            "flow_rate": "m³/s",
            "temperature": "°C"
        }
        return units.get(parameter, "")
    
    async def _get_nearby_sensor_data(self, lat: float, lon: float, 
                                    parameter: str, timestamp: Optional[datetime]) -> List[Dict]:
        """Get data from nearby sensors"""
        # Mock implementation - would query actual sensor data
        # In production, would query InfluxDB and filter by distance
        
        mock_sensors = [
            {"sensor_id": "WL001", "lat": lat + 0.01, "lon": lon + 0.01, 
             "value": 2.5, "distance": 1.2, "timestamp": datetime.utcnow()},
            {"sensor_id": "WL002", "lat": lat - 0.02, "lon": lon + 0.02,
             "value": 2.3, "distance": 2.8, "timestamp": datetime.utcnow() - timedelta(hours=1)},
            {"sensor_id": "WL003", "lat": lat + 0.03, "lon": lon - 0.01,
             "value": 2.7, "distance": 3.5, "timestamp": datetime.utcnow() - timedelta(hours=2)}
        ]
        
        # Filter by max distance
        return [s for s in mock_sensors if s["distance"] <= self.max_interpolation_distance_km]
    
    async def _get_all_sensor_data(self, parameter: str) -> List[Dict]:
        """Get all available sensor data"""
        # Mock implementation
        return [
            {"sensor_id": "WL001", "lat": 13.5, "lon": 100.5, "value": 2.5},
            {"sensor_id": "WL002", "lat": 13.52, "lon": 100.52, "value": 2.3},
            {"sensor_id": "WL003", "lat": 13.48, "lon": 100.48, "value": 2.7},
            {"sensor_id": "WL004", "lat": 13.51, "lon": 100.49, "value": 2.4},
            {"sensor_id": "WL005", "lat": 13.49, "lon": 100.51, "value": 2.6},
            {"sensor_id": "WL006", "lat": 13.53, "lon": 100.50, "value": 2.2}
        ]
    
    def _calculate_grid_confidence(self, grid_points: np.ndarray, 
                                 sensor_points: np.ndarray,
                                 resolution_m: float) -> np.ndarray:
        """Calculate confidence for each grid point"""
        # Distance to nearest sensor
        distances = cdist(grid_points, sensor_points).min(axis=1)
        
        # Convert to km
        distances_km = distances * 111  # Rough conversion
        
        # Exponential decay confidence
        confidence = np.exp(-distances_km / self.max_interpolation_distance_km)
        
        return confidence
    
    def _create_low_confidence_estimate(self, section_id: str, parameter: str,
                                      timestamp: Optional[datetime]) -> InterpolatedData:
        """Create low confidence estimate when no data available"""
        return InterpolatedData(
            section_id=section_id,
            timestamp=timestamp or datetime.utcnow(),
            parameter=parameter,
            value=0.0,  # Default value
            unit=self._get_unit(parameter),
            confidence=ConfidenceScore(
                overall=0.1,
                spatial_coverage=0.0,
                temporal_coverage=0.0,
                model_accuracy=0.0,
                data_freshness=0.0,
                factors={"no_data": True}
            ),
            quality=DataQuality.ESTIMATED,
            method=InterpolationMethod.INVERSE_DISTANCE,
            source_sensors=[],
            distance_to_nearest_sensor_km=999.0
        )
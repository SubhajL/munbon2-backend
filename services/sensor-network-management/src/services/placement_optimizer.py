import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import numpy as np
from scipy.optimize import linear_sum_assignment
import uuid

from models.sensor import SensorDB, SensorType, SensorStatus
from models.placement import (
    PlacementRecommendation, OptimizationRequest, OptimizationResult,
    SensorPlacement, PlacementPriority, PlacementReason
)
from utils.spatial import calculate_distance, get_section_coordinates

class PlacementOptimizer:
    """Optimize sensor placement across irrigation network"""
    
    def __init__(self):
        self.max_water_sensors = int(os.getenv("MAX_WATER_LEVEL_SENSORS", 6))
        self.max_moisture_sensors = int(os.getenv("MAX_MOISTURE_SENSORS", 1))
    
    async def optimize_placement(self, request: OptimizationRequest, 
                               db: AsyncSession) -> OptimizationResult:
        """Generate optimal sensor placement plan"""
        # Get available sensors
        sensors = await self._get_available_sensors(db)
        
        # Get sections needing monitoring
        sections = await self._get_priority_sections(request, db)
        
        # Create cost matrix (distance + priority based)
        cost_matrix = await self._create_cost_matrix(sensors, sections, db)
        
        # Solve assignment problem
        sensor_indices, section_indices = linear_sum_assignment(cost_matrix)
        
        # Create placements
        placements = []
        total_distance = 0
        
        for i, (sensor_idx, section_idx) in enumerate(zip(sensor_indices, section_indices)):
            if sensor_idx < len(sensors) and section_idx < len(sections):
                sensor = sensors[sensor_idx]
                section = sections[section_idx]
                
                # Calculate placement details
                coords = await get_section_coordinates(section["id"], db)
                distance = cost_matrix[sensor_idx, section_idx]
                total_distance += distance
                
                placement = SensorPlacement(
                    sensor_id=sensor.id,
                    section_id=section["id"],
                    latitude=coords["lat"],
                    longitude=coords["lon"],
                    priority=section["priority"],
                    reasons=section["reasons"],
                    estimated_duration_days=7,
                    expected_readings_per_day=24,
                    placement_date=request.start_date + timedelta(days=i // 2)
                )
                placements.append(placement)
        
        # Calculate metrics
        coverage_score = len(placements) / len(sections) if sections else 0
        
        return OptimizationResult(
            optimization_id=str(uuid.uuid4()),
            generated_at=datetime.utcnow(),
            period_start=request.start_date,
            period_end=request.end_date,
            placements=placements,
            total_movements=len(placements),
            total_travel_distance_km=total_distance,
            coverage_score=min(coverage_score, 1.0),
            expected_data_quality=0.85,
            recommendations=await self._generate_recommendations(sections, placements),
            unmonitored_critical_sections=self._get_unmonitored_critical(sections, placements)
        )
    
    async def get_recommendations(self, days_ahead: int, min_priority: str,
                                db: AsyncSession) -> List[PlacementRecommendation]:
        """Get placement recommendations"""
        # Mock implementation - would integrate with real data
        recommendations = []
        
        # Simulate priority sections
        priority_sections = [
            {"id": "RMC-01", "priority": PlacementPriority.CRITICAL, 
             "reasons": [PlacementReason.SCHEDULED_IRRIGATION, PlacementReason.GATE_AUTOMATION]},
            {"id": "1L-1a", "priority": PlacementPriority.HIGH,
             "reasons": [PlacementReason.HISTORICAL_PROBLEMS]},
            {"id": "1R-2a", "priority": PlacementPriority.MEDIUM,
             "reasons": [PlacementReason.MANUAL_VALIDATION]}
        ]
        
        for section in priority_sections:
            if self._priority_meets_threshold(section["priority"], min_priority):
                coords = {"lat": 13.5 + np.random.uniform(-0.1, 0.1), 
                         "lon": 100.5 + np.random.uniform(-0.1, 0.1)}
                
                rec = PlacementRecommendation(
                    section_id=section["id"],
                    priority=section["priority"],
                    score=np.random.uniform(0.7, 1.0),
                    reasons=section["reasons"],
                    recommended_sensor_type="water_level",
                    optimal_coordinates=coords,
                    expected_benefit=np.random.uniform(0.6, 0.9),
                    historical_accuracy=np.random.uniform(0.8, 0.95),
                    nearby_sections=[]
                )
                recommendations.append(rec)
        
        return recommendations
    
    async def get_current_placements(self, db: AsyncSession) -> List[SensorPlacement]:
        """Get current sensor placements"""
        # Get active sensors with locations
        result = await db.execute(
            select(SensorDB).where(
                and_(
                    SensorDB.status == SensorStatus.ACTIVE,
                    SensorDB.current_section_id.isnot(None)
                )
            )
        )
        sensors = result.scalars().all()
        
        placements = []
        for sensor in sensors:
            placement = SensorPlacement(
                sensor_id=sensor.id,
                section_id=sensor.current_section_id,
                latitude=sensor.latitude or 0,
                longitude=sensor.longitude or 0,
                priority=PlacementPriority.MEDIUM,
                reasons=[PlacementReason.GATE_AUTOMATION],
                estimated_duration_days=7,
                expected_readings_per_day=24,
                placement_date=sensor.installation_date or datetime.utcnow()
            )
            placements.append(placement)
        
        return placements
    
    async def analyze_coverage(self, db: AsyncSession) -> Dict:
        """Analyze current sensor coverage"""
        # Get sensor locations
        sensors = await self.get_current_placements(db)
        
        # Mock section data - would come from GIS service
        total_sections = 47  # Total canal sections
        critical_sections = 12
        monitored_sections = len(sensors)
        
        # Calculate coverage metrics
        coverage_percentage = (monitored_sections / total_sections) * 100
        critical_coverage = min(len([s for s in sensors if s.priority == PlacementPriority.CRITICAL]) / critical_sections, 1.0) * 100
        
        return {
            "total_sections": total_sections,
            "monitored_sections": monitored_sections,
            "coverage_percentage": coverage_percentage,
            "critical_sections": critical_sections,
            "critical_coverage_percentage": critical_coverage,
            "sensor_density": monitored_sections / total_sections,
            "recommendations": f"Increase sensors in critical sections. Current coverage: {coverage_percentage:.1f}%"
        }
    
    async def _get_available_sensors(self, db: AsyncSession) -> List[SensorDB]:
        """Get sensors available for placement"""
        result = await db.execute(
            select(SensorDB).where(
                SensorDB.status.in_([SensorStatus.ACTIVE, SensorStatus.INACTIVE])
            )
        )
        return result.scalars().all()
    
    async def _get_priority_sections(self, request: OptimizationRequest, 
                                   db: AsyncSession) -> List[Dict]:
        """Get sections prioritized for monitoring"""
        # Mock implementation - would integrate with real data sources
        sections = []
        
        # Simulate section priorities based on various factors
        section_ids = ["RMC-01", "1L-1a", "1L-2a", "1R-1a", "1R-2a", "2L-1a", "3R-1a"]
        
        for section_id in section_ids:
            priority = np.random.choice([
                PlacementPriority.CRITICAL,
                PlacementPriority.HIGH,
                PlacementPriority.MEDIUM,
                PlacementPriority.LOW
            ], p=[0.2, 0.3, 0.3, 0.2])
            
            reasons = []
            if priority in [PlacementPriority.CRITICAL, PlacementPriority.HIGH]:
                reasons.append(PlacementReason.SCHEDULED_IRRIGATION)
            if np.random.random() > 0.5:
                reasons.append(PlacementReason.HISTORICAL_PROBLEMS)
            
            sections.append({
                "id": section_id,
                "priority": priority,
                "reasons": reasons,
                "score": np.random.uniform(0.5, 1.0)
            })
        
        # Sort by priority and score
        sections.sort(key=lambda x: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[x["priority"]],
            -x["score"]
        ))
        
        return sections
    
    async def _create_cost_matrix(self, sensors: List[SensorDB], 
                                sections: List[Dict], db: AsyncSession) -> np.ndarray:
        """Create cost matrix for optimization"""
        n_sensors = len(sensors)
        n_sections = len(sections)
        
        # Initialize with high cost
        cost_matrix = np.full((n_sensors, n_sections), 1000.0)
        
        for i, sensor in enumerate(sensors):
            for j, section in enumerate(sections):
                # Calculate distance cost
                if sensor.latitude and sensor.longitude:
                    section_coords = await get_section_coordinates(section["id"], db)
                    distance = calculate_distance(
                        sensor.latitude, sensor.longitude,
                        section_coords["lat"], section_coords["lon"]
                    )
                else:
                    distance = 50  # Default distance if no current location
                
                # Adjust cost based on priority
                priority_multiplier = {
                    PlacementPriority.CRITICAL: 0.1,
                    PlacementPriority.HIGH: 0.3,
                    PlacementPriority.MEDIUM: 0.6,
                    PlacementPriority.LOW: 1.0
                }[section["priority"]]
                
                cost_matrix[i, j] = distance * priority_multiplier
        
        return cost_matrix
    
    async def _generate_recommendations(self, sections: List[Dict], 
                                      placements: List[SensorPlacement]) -> List[PlacementRecommendation]:
        """Generate additional recommendations"""
        placed_sections = {p.section_id for p in placements}
        recommendations = []
        
        for section in sections:
            if section["id"] not in placed_sections and section["priority"] in [PlacementPriority.CRITICAL, PlacementPriority.HIGH]:
                rec = PlacementRecommendation(
                    section_id=section["id"],
                    priority=section["priority"],
                    score=section["score"],
                    reasons=section["reasons"],
                    recommended_sensor_type="water_level",
                    optimal_coordinates={"lat": 13.5, "lon": 100.5},  # Mock coords
                    expected_benefit=0.8,
                    historical_accuracy=0.85,
                    nearby_sections=[]
                )
                recommendations.append(rec)
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _get_unmonitored_critical(self, sections: List[Dict], 
                                 placements: List[SensorPlacement]) -> List[str]:
        """Get critical sections without sensors"""
        placed_sections = {p.section_id for p in placements}
        return [
            s["id"] for s in sections 
            if s["priority"] == PlacementPriority.CRITICAL and s["id"] not in placed_sections
        ]
    
    def _priority_meets_threshold(self, priority: PlacementPriority, threshold: str) -> bool:
        """Check if priority meets minimum threshold"""
        priority_order = {
            PlacementPriority.CRITICAL: 0,
            PlacementPriority.HIGH: 1,
            PlacementPriority.MEDIUM: 2,
            PlacementPriority.LOW: 3
        }
        
        threshold_map = {
            "critical": PlacementPriority.CRITICAL,
            "high": PlacementPriority.HIGH,
            "medium": PlacementPriority.MEDIUM,
            "low": PlacementPriority.LOW
        }
        
        threshold_priority = threshold_map.get(threshold, PlacementPriority.MEDIUM)
        return priority_order[priority] <= priority_order[threshold_priority]
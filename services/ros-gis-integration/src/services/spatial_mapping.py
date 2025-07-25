from typing import List, Dict, Optional, Tuple
import asyncio
from math import radians, sin, cos, sqrt, atan2
from core import get_logger
from config import settings
from db import DatabaseManager
from schemas.spatial import SpatialMapping, GateMapping, SectionBoundary

logger = get_logger(__name__)


class SpatialMappingService:
    """Manages spatial relationships between sections and delivery infrastructure"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = logger.bind(service="spatial_mapping")
        
        # Mock data for development
        self._sections = self._initialize_mock_sections()
        self._gates = self._initialize_mock_gates()
    
    def _initialize_mock_sections(self) -> Dict[str, Dict]:
        """Initialize mock section data"""
        sections = {}
        zones = [2, 3, 5, 6]
        section_letters = ["A", "B", "C", "D"]
        
        for zone in zones:
            for letter in section_letters:
                section_id = f"Zone_{zone}_Section_{letter}"
                sections[section_id] = {
                    "section_id": section_id,
                    "zone": zone,
                    "area_hectares": 150 + (zone * 10),
                    "crop_type": "rice" if zone in [2, 3] else "sugarcane",
                    "soil_type": "clay_loam",
                    "elevation_m": 220 - (zone * 0.5),
                    "delivery_gate": f"M(0,{2 if zone in [2,3] else 5})->Zone_{zone}",
                    "centroid": {
                        "lat": 14.82 + (zone * 0.01),
                        "lon": 103.15 + (zone * 0.01)
                    }
                }
        
        return sections
    
    def _initialize_mock_gates(self) -> Dict[str, Dict]:
        """Initialize mock gate data"""
        return {
            "M(0,2)->Zone_2": {
                "gate_id": "M(0,2)->Zone_2",
                "gate_type": "automated",
                "location": {"lat": 14.8234, "lon": 103.1567},
                "max_flow_m3s": 5.0,
                "sections_served": ["Zone_2_Section_A", "Zone_2_Section_B", 
                                  "Zone_2_Section_C", "Zone_2_Section_D"],
                "elevation_m": 219.5
            },
            "M(0,5)->Zone_5": {
                "gate_id": "M(0,5)->Zone_5",
                "gate_type": "manual",
                "location": {"lat": 14.8456, "lon": 103.1789},
                "max_flow_m3s": 4.5,
                "sections_served": ["Zone_5_Section_A", "Zone_5_Section_B",
                                  "Zone_5_Section_C", "Zone_5_Section_D"],
                "elevation_m": 218.0
            },
            "M(0,2)->Zone_3": {
                "gate_id": "M(0,2)->Zone_3",
                "gate_type": "automated",
                "location": {"lat": 14.8345, "lon": 103.1678},
                "max_flow_m3s": 4.0,
                "sections_served": ["Zone_3_Section_A", "Zone_3_Section_B",
                                  "Zone_3_Section_C", "Zone_3_Section_D"],
                "elevation_m": 219.0
            }
        }
    
    async def get_section(self, section_id: str) -> Optional[Dict]:
        """Get section details including spatial data"""
        return self._sections.get(section_id)
    
    async def get_sections_by_zone(self, zone: int) -> List[Dict]:
        """Get all sections in a specific zone"""
        return [
            section for section in self._sections.values()
            if section["zone"] == zone
        ]
    
    async def get_section_mapping(self, section_id: str) -> Optional[Dict]:
        """Get spatial mapping for a section to its delivery gate"""
        section = self._sections.get(section_id)
        if not section:
            return None
        
        gate_id = section["delivery_gate"]
        gate = self._gates.get(gate_id)
        if not gate:
            return None
        
        # Calculate distance and travel time
        distance_km = self._calculate_distance(
            section["centroid"]["lat"],
            section["centroid"]["lon"],
            gate["location"]["lat"],
            gate["location"]["lon"]
        )
        
        # Estimate travel time based on gravity flow
        # Assuming average flow velocity of 1.5 m/s in canals
        travel_time_hours = distance_km / (1.5 * 3.6)  # Convert m/s to km/h
        
        return {
            "section_id": section_id,
            "delivery_gate": gate_id,
            "distance_km": round(distance_km, 2),
            "elevation_difference_m": gate["elevation_m"] - section["elevation_m"],
            "delivery_path": [gate_id, f"Zone_{section['zone']}_Node", section_id],
            "travel_time_hours": round(travel_time_hours, 2)
        }
    
    async def get_all_delivery_points(self) -> List[Dict]:
        """Get all delivery gates with their served sections"""
        delivery_points = []
        
        for gate_id, gate_data in self._gates.items():
            # Calculate current utilization
            sections_served = gate_data["sections_served"]
            total_area = sum(
                self._sections[sid].get("area_rai", 0) 
                for sid in sections_served 
                if sid in self._sections
            )
            
            delivery_points.append({
                "gate_id": gate_id,
                "location": gate_data["location"],
                "sections_served": sections_served,
                "max_flow_m3s": gate_data["max_flow_m3s"],
                "current_flow_m3s": gate_data["max_flow_m3s"] * 0.7,  # Mock 70% utilization
                "elevation_m": gate_data["elevation_m"],
                "total_area_rai": total_area
            })
        
        return delivery_points
    
    async def get_gate_mappings(self) -> List[Dict]:
        """Get gate utilization and section mappings"""
        mappings = []
        
        for gate_id, gate_data in self._gates.items():
            sections_served = gate_data["sections_served"]
            total_area = sum(
                self._sections[sid]["area_hectares"]
                for sid in sections_served
                if sid in self._sections
            )
            
            # Calculate mock utilization based on area served
            # Assume 1 m³/s can serve ~300 hectares
            required_flow = total_area / 300
            utilization = (required_flow / gate_data["max_flow_m3s"]) * 100
            
            mappings.append({
                "gate_id": gate_id,
                "gate_type": gate_data["gate_type"],
                "sections_served": sections_served,
                "total_area_hectares": total_area,
                "max_capacity_m3s": gate_data["max_flow_m3s"],
                "current_allocation_m3s": required_flow,
                "utilization_percent": min(utilization, 100)
            })
        
        return mappings
    
    async def update_section_gate(self, section_id: str, new_gate_id: str) -> bool:
        """Update the delivery gate assignment for a section"""
        if section_id not in self._sections:
            self.logger.error("Section not found", section_id=section_id)
            return False
        
        if new_gate_id not in self._gates:
            self.logger.error("Gate not found", gate_id=new_gate_id)
            return False
        
        old_gate_id = self._sections[section_id]["delivery_gate"]
        
        # Update section
        self._sections[section_id]["delivery_gate"] = new_gate_id
        
        # Update gate mappings
        if old_gate_id in self._gates:
            old_sections = self._gates[old_gate_id]["sections_served"]
            if section_id in old_sections:
                old_sections.remove(section_id)
        
        self._gates[new_gate_id]["sections_served"].append(section_id)
        
        self.logger.info(
            "Section gate updated",
            section_id=section_id,
            old_gate=old_gate_id,
            new_gate=new_gate_id
        )
        
        return True
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    async def find_optimal_delivery_path(
        self, 
        section_id: str,
        constraints: Optional[Dict] = None
    ) -> Optional[List[str]]:
        """Find optimal delivery path considering constraints"""
        section = self._sections.get(section_id)
        if not section:
            return None
        
        gate_id = section["delivery_gate"]
        
        # Simple path for now
        # In production, would use graph algorithms with PostGIS
        path = [
            "Source",
            "M(0,0)",
            "M(0,2)" if section["zone"] in [2, 3] else "M(0,5)",
            gate_id,
            f"Zone_{section['zone']}_Node",
            section_id
        ]
        
        return path
    
    async def calculate_delivery_metrics(
        self,
        section_id: str,
        volume_m3: float
    ) -> Dict[str, float]:
        """Calculate delivery time and losses for a section"""
        mapping = await self.get_section_mapping(section_id)
        if not mapping:
            return {}
        
        # Estimate losses (2% per km)
        loss_percent = mapping["distance_km"] * 0.02
        losses_m3 = volume_m3 * loss_percent
        
        # Delivery time based on flow rate
        # Assume average 3 m³/s flow rate
        delivery_hours = (volume_m3 / 3) / 3600  # Convert seconds to hours
        total_time = mapping["travel_time_hours"] + delivery_hours
        
        return {
            "travel_time_hours": mapping["travel_time_hours"],
            "delivery_time_hours": delivery_hours,
            "total_time_hours": total_time,
            "expected_losses_m3": losses_m3,
            "loss_percent": loss_percent * 100
        }
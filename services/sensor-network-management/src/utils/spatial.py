import math
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

async def get_section_coordinates(section_id: str, db: Optional[AsyncSession]) -> Dict[str, float]:
    """Get coordinates for a canal section"""
    # Mock implementation - would query from GIS database
    # These are example coordinates around the Munbon area
    
    section_coords = {
        "RMC-01": {"lat": 13.5000, "lon": 100.5000},
        "1L-1a": {"lat": 13.5200, "lon": 100.5200},
        "1L-2a": {"lat": 13.5250, "lon": 100.5250},
        "1R-1a": {"lat": 13.4800, "lon": 100.5100},
        "1R-2a": {"lat": 13.4750, "lon": 100.5150},
        "2L-1a": {"lat": 13.5100, "lon": 100.5300},
        "2L-2a": {"lat": 13.5150, "lon": 100.5350},
        "2R-1a": {"lat": 13.4900, "lon": 100.5200},
        "3L-1a": {"lat": 13.5300, "lon": 100.5400},
        "3R-1a": {"lat": 13.4700, "lon": 100.5250},
        "4L-1a": {"lat": 13.5400, "lon": 100.5500},
        "4R-1a": {"lat": 13.4600, "lon": 100.5300},
        "5L-1a": {"lat": 13.5500, "lon": 100.5600},
        "5R-1a": {"lat": 13.4500, "lon": 100.5350},
        "6L-1a": {"lat": 13.5600, "lon": 100.5700},
        "6R-1a": {"lat": 13.4400, "lon": 100.5400}
    }
    
    # If section not found, generate random coordinates within bounds
    if section_id not in section_coords:
        return {
            "lat": 13.5 + np.random.uniform(-0.1, 0.1),
            "lon": 100.5 + np.random.uniform(-0.1, 0.1)
        }
    
    return section_coords[section_id]

async def get_network_bounds() -> Dict[str, float]:
    """Get bounding box of the irrigation network"""
    # Mock bounds for the Munbon irrigation area
    return {
        "north": 13.6000,
        "south": 13.4000,
        "east": 100.6000,
        "west": 100.4000
    }

def point_in_polygon(point: tuple, polygon: list) -> bool:
    """Check if a point is inside a polygon"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

def interpolate_along_path(start: Dict[str, float], end: Dict[str, float], 
                          fraction: float) -> Dict[str, float]:
    """Interpolate coordinates along a path"""
    return {
        "lat": start["lat"] + (end["lat"] - start["lat"]) * fraction,
        "lon": start["lon"] + (end["lon"] - start["lon"]) * fraction
    }

def create_buffer_zone(center: Dict[str, float], radius_km: float, 
                      n_points: int = 16) -> list:
    """Create a circular buffer zone around a point"""
    points = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        
        # Approximate conversion (1 degree ≈ 111 km)
        lat_offset = (radius_km / 111) * math.cos(angle)
        lon_offset = (radius_km / (111 * math.cos(math.radians(center["lat"])))) * math.sin(angle)
        
        points.append({
            "lat": center["lat"] + lat_offset,
            "lon": center["lon"] + lon_offset
        })
    
    return points
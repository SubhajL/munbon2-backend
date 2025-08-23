"""
GIS Service Mock Endpoints
Provides mock spatial data, parcel information, and consolidated demands
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
from datetime import datetime, date
import random

from data import get_mock_data_manager

router = APIRouter()
mock_data = get_mock_data_manager()


# Request/Response Models
class ParcelQuery(BaseModel):
    zone: Optional[int] = None
    crop_type: Optional[str] = None
    min_area_rai: Optional[float] = None
    max_area_rai: Optional[float] = None
    limit: int = 100


class ConsolidatedDemand(BaseModel):
    section_id: str
    crop_type: str
    growth_stage: str
    crop_week: int
    area_rai: float
    net_demand_m3: float
    gross_demand_m3: float
    moisture_deficit_percent: float
    stress_level: str
    amphoe: str
    tambon: str


class BulkDemandRequest(BaseModel):
    demands: List[Dict[str, Any]]


# Endpoints
@router.get("/api/v1/parcels")
async def get_parcels(
    zone: Optional[int] = Query(None),
    crop_type: Optional[str] = Query(None),
    status: Optional[str] = Query("active"),
    limit: int = Query(100, le=500),
    offset: int = Query(0)
):
    """Get parcels with optional filtering"""
    
    # Filter plots based on criteria
    filtered_plots = []
    
    for plot_id, plot in mock_data.plots.items():
        if zone and plot['zone'] != zone:
            continue
        if crop_type and plot['crop_type'] != crop_type:
            continue
        if status and plot['status'] != status:
            continue
        
        # Create parcel data with GIS information
        section = mock_data.sections.get(plot['section_id'], {})
        
        parcel = {
            "parcel_id": plot_id,
            "section_id": plot['section_id'],
            "zone": plot['zone'],
            "plot_number": plot['plot_number'],
            "area_rai": plot['area_rai'],
            "area_hectares": plot['area_rai'] / 6.25,
            "crop_type": plot['crop_type'],
            "planting_date": plot['planting_date'],
            "expected_harvest_date": plot['expected_harvest_date'],
            "farmer_id": plot['farmer_id'],
            "status": plot['status'],
            "geometry": {
                "type": "Polygon",
                "coordinates": _generate_polygon_coords(
                    16.4419 + (plot['zone'] * 0.01),
                    102.8359 + (plot['zone'] * 0.01),
                    plot['plot_number']
                )
            },
            "properties": {
                "soil_type": section.get('soil_type', 'loam'),
                "elevation_m": plot.get('elevation_m', 220),
                "delivery_gate": section.get('delivery_gate'),
                "irrigation_channel": f"channel_zone_{plot['zone']}",
                "amphoe": "เมืองนครราชสีมา",
                "tambon": f"ตำบลที่ {plot['zone']}",
                "village": f"หมู่ที่ {plot['plot_number']}"
            }
        }
        
        filtered_plots.append(parcel)
    
    # Apply pagination
    total_count = len(filtered_plots)
    paginated_plots = filtered_plots[offset:offset + limit]
    
    return {
        "status": "success",
        "data": paginated_plots,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
    }


@router.get("/api/v1/parcels/{parcel_id}")
async def get_parcel_detail(parcel_id: str):
    """Get detailed parcel information"""
    
    plot = mock_data.plots.get(parcel_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Parcel not found")
    
    section = mock_data.sections.get(plot['section_id'], {})
    
    # Get current demand if exists
    current_demand = mock_data.get_demand_for_section(
        plot['section_id'], 
        datetime.now().date()
    )
    
    return {
        "status": "success",
        "data": {
            "parcel_id": parcel_id,
            "section_id": plot['section_id'],
            "zone": plot['zone'],
            "plot_number": plot['plot_number'],
            "area_rai": plot['area_rai'],
            "area_hectares": plot['area_rai'] / 6.25,
            "crop_type": plot['crop_type'],
            "planting_date": plot['planting_date'],
            "expected_harvest_date": plot['expected_harvest_date'],
            "farmer": {
                "id": plot['farmer_id'],
                "name": f"นาย สมชาย ใจดี_{plot['farmer_id']}",
                "phone": f"08{random.randint(10000000, 99999999)}",
                "group": f"กลุ่มผู้ใช้น้ำโซน {plot['zone']}"
            },
            "status": plot['status'],
            "geometry": {
                "type": "Polygon",
                "coordinates": _generate_polygon_coords(
                    16.4419 + (plot['zone'] * 0.01),
                    102.8359 + (plot['zone'] * 0.01),
                    plot['plot_number']
                ),
                "centroid": {
                    "latitude": 16.4419 + (plot['zone'] * 0.01),
                    "longitude": 102.8359 + (plot['zone'] * 0.01)
                }
            },
            "properties": {
                "soil_type": section.get('soil_type', 'loam'),
                "elevation_m": plot.get('elevation_m', 220),
                "slope_percent": random.uniform(0, 2),
                "drainage_class": random.choice(["good", "moderate", "poor"]),
                "delivery_gate": section.get('delivery_gate'),
                "irrigation_channel": f"channel_zone_{plot['zone']}",
                "distance_to_gate_km": random.uniform(0.5, 3.0),
                "amphoe": "เมืองนครราชสีมา",
                "tambon": f"ตำบลที่ {plot['zone']}",
                "village": f"หมู่ที่ {plot['plot_number']}"
            },
            "water_demand": {
                "current_demand_m3": current_demand.get('adjusted_demand_m3', 0),
                "weekly_average_m3": current_demand.get('adjusted_demand_m3', 0) * 7,
                "seasonal_total_m3": current_demand.get('adjusted_demand_m3', 0) * 7 * 16
            },
            "aquacrop_results": {
                "latest_calculation": datetime.now().date().isoformat(),
                "irrigation_requirement_mm": random.uniform(5, 8),
                "soil_moisture_percent": random.uniform(40, 80),
                "water_stress_level": random.choice(["none", "mild", "moderate"]),
                "yield_prediction_ton_rai": random.uniform(0.8, 1.2) if plot['crop_type'] == 'rice' else random.uniform(8, 12)
            }
        }
    }


@router.get("/api/v1/parcels/near")
async def get_parcels_near_location(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(5.0, le=50.0),
    limit: int = Query(20, le=100)
):
    """Get parcels near a specific location"""
    
    # Simple distance calculation (not accurate for real GIS)
    nearby_parcels = []
    
    for plot_id, plot in mock_data.plots.items():
        # Mock distance calculation
        plot_lat = 16.4419 + (plot['zone'] * 0.01)
        plot_lon = 102.8359 + (plot['zone'] * 0.01)
        
        # Simplified distance (degrees to km approximation)
        distance = ((plot_lat - latitude)**2 + (plot_lon - longitude)**2)**0.5 * 111
        
        if distance <= radius_km:
            section = mock_data.sections.get(plot['section_id'], {})
            
            nearby_parcels.append({
                "parcel_id": plot_id,
                "section_id": plot['section_id'],
                "distance_km": round(distance, 2),
                "area_rai": plot['area_rai'],
                "crop_type": plot['crop_type'],
                "coordinates": {
                    "latitude": plot_lat,
                    "longitude": plot_lon
                }
            })
    
    # Sort by distance and limit
    nearby_parcels.sort(key=lambda x: x['distance_km'])
    
    return {
        "status": "success",
        "data": {
            "search_location": {
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": radius_km
            },
            "parcels": nearby_parcels[:limit],
            "total_found": len(nearby_parcels)
        }
    }


@router.post("/api/v1/ros-demands/bulk")
async def store_bulk_ros_demands(request: BulkDemandRequest):
    """Store ROS calculation results in bulk"""
    
    stored_count = 0
    
    for demand in request.demands:
        # Store in mock data
        section_id = demand.get('section_id')
        if section_id:
            key = f"{section_id}_{datetime.now().date().isoformat()}"
            mock_data.demands[key] = {
                **demand,
                "stored_at": datetime.utcnow().isoformat()
            }
            stored_count += 1
    
    return {
        "status": "success",
        "data": {
            "count": stored_count,
            "message": f"Stored {stored_count} ROS demand calculations"
        }
    }


@router.get("/api/v1/ros-demands")
async def get_ros_demands(
    sectionId: str = Query(...),
    calendarWeek: int = Query(...),
    calendarYear: int = Query(...),
    latest: bool = Query(True)
):
    """Get ROS demand calculations"""
    
    # Get or create demand
    demand = mock_data.get_demand_for_section(sectionId, datetime.now().date())
    
    # Add ROS calculation details
    section = mock_data.sections.get(sectionId, {})
    
    ros_demand = {
        "section_id": sectionId,
        "calendar_week": calendarWeek,
        "calendar_year": calendarYear,
        "crop_type": section.get('crop_type', 'rice'),
        "growth_stage": _get_growth_stage_for_week(section.get('crop_type', 'rice'), calendarWeek),
        "crop_week": calendarWeek % 16 + 1,  # Simple calculation
        "area_rai": section.get('area_rai', 100),
        "net_demand_m3": demand['adjusted_demand_m3'],
        "gross_demand_m3": demand['base_demand_m3'],
        "moisture_deficit_percent": random.uniform(10, 30),
        "stress_level": random.choice(["none", "mild", "moderate"]),
        "amphoe": "เมืองนครราชสีมา",
        "tambon": f"ตำบลที่ {section.get('zone', 1)}",
        "calculated_at": datetime.utcnow().isoformat()
    }
    
    return {
        "status": "success",
        "data": [ros_demand] if latest else [ros_demand] * 3  # Return multiple if not latest
    }


@router.get("/api/v1/spatial/sections/{section_id}/plots")
async def get_section_plots(section_id: str):
    """Get all plots within a section"""
    
    section = mock_data.sections.get(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    
    section_plots = []
    
    for plot_id, plot in mock_data.plots.items():
        if plot['section_id'] == section_id:
            section_plots.append({
                "plot_id": plot_id,
                "plot_number": plot['plot_number'],
                "area_rai": plot['area_rai'],
                "crop_type": plot['crop_type'],
                "status": plot['status'],
                "geometry": {
                    "type": "Polygon",
                    "coordinates": _generate_polygon_coords(
                        16.4419 + (plot['zone'] * 0.01),
                        102.8359 + (plot['zone'] * 0.01),
                        plot['plot_number']
                    )
                }
            })
    
    return {
        "status": "success",
        "data": {
            "section_id": section_id,
            "section_name": f"Section {section_id}",
            "total_plots": len(section_plots),
            "total_area_rai": sum(p['area_rai'] for p in section_plots),
            "plots": section_plots
        }
    }


@router.get("/api/v1/spatial/zones/{zone}/summary")
async def get_zone_summary(zone: int):
    """Get spatial summary for a zone"""
    
    zone_sections = []
    zone_plots = []
    
    for section_id, section in mock_data.sections.items():
        if section['zone'] == zone:
            zone_sections.append(section)
    
    for plot_id, plot in mock_data.plots.items():
        if plot['zone'] == zone:
            zone_plots.append(plot)
    
    # Calculate statistics
    total_area_rai = sum(s['area_rai'] for s in zone_sections)
    crop_distribution = {}
    
    for plot in zone_plots:
        crop = plot['crop_type']
        if crop not in crop_distribution:
            crop_distribution[crop] = {"count": 0, "area_rai": 0}
        crop_distribution[crop]["count"] += 1
        crop_distribution[crop]["area_rai"] += plot['area_rai']
    
    return {
        "status": "success",
        "data": {
            "zone": zone,
            "sections": {
                "count": len(zone_sections),
                "total_area_rai": total_area_rai,
                "total_area_hectares": total_area_rai / 6.25
            },
            "plots": {
                "count": len(zone_plots),
                "active_count": sum(1 for p in zone_plots if p['status'] == 'active'),
                "average_size_rai": sum(p['area_rai'] for p in zone_plots) / len(zone_plots) if zone_plots else 0
            },
            "crop_distribution": crop_distribution,
            "irrigation": {
                "primary_gates": list(set(s['delivery_gate'] for s in zone_sections)),
                "channels": [f"channel_zone_{zone}"]
            }
        }
    }


# Helper functions
def _generate_polygon_coords(base_lat: float, base_lon: float, plot_num: int) -> List[List[List[float]]]:
    """Generate mock polygon coordinates for a plot"""
    # Create a simple rectangle
    offset = plot_num * 0.001
    coords = [
        [
            [base_lon + offset, base_lat + offset],
            [base_lon + offset + 0.002, base_lat + offset],
            [base_lon + offset + 0.002, base_lat + offset + 0.002],
            [base_lon + offset, base_lat + offset + 0.002],
            [base_lon + offset, base_lat + offset]  # Close polygon
        ]
    ]
    return coords


def _get_growth_stage_for_week(crop_type: str, week: int) -> str:
    """Determine growth stage based on week number"""
    if crop_type == "rice":
        week_mod = week % 16
        if week_mod <= 3:
            return "seedling"
        elif week_mod <= 7:
            return "tillering"
        elif week_mod <= 11:
            return "flowering"
        elif week_mod <= 14:
            return "grain_filling"
        else:
            return "maturity"
    else:
        week_mod = week % 48
        if week_mod <= 12:
            return "germination"
        elif week_mod <= 28:
            return "tillering"
        elif week_mod <= 40:
            return "grand_growth"
        else:
            return "ripening"
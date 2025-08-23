from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
from pydantic import BaseModel

from core import get_logger
from services.daily_demand_calculator import DailyDemandCalculator
from database import Database
from api.water_demand_queries import WaterDemandQueries
from api.crop_season_queries import CropSeasonQueries

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/water-demand", tags=["water-demand"])


# Response Models
class DemandResponse(BaseModel):
    date: date
    section_id: str
    zone: int
    ros_demand_m3: float
    rid_ms_demand_m3: float
    awd_demand_m3: float
    combined_demand_m3: float
    area_rai: float
    # Water level adjustment fields
    original_demand_m3: Optional[float] = None
    adjusted_demand_m3: Optional[float] = None
    water_level_m: Optional[float] = None
    adjustment_factor: float = 1.0
    adjustment_method: Optional[str] = None


class AccumulatedDemandResponse(BaseModel):
    section_id: str
    period: str
    start_date: date
    end_date: date
    total_demand_m3: float
    total_ros_m3: float
    total_rid_ms_m3: float
    total_awd_m3: float
    plot_count: int


class SpatialDemandResponse(BaseModel):
    feature_id: str
    feature_type: str
    geometry: Optional[Dict]
    current_demand_m3: float
    ros_demand_m3: float
    rid_ms_demand_m3: float
    awd_demand_m3: float
    area_rai: float
    label: str


# Section Level Endpoints
@router.get("/sections/{section_id}/daily")
async def get_section_daily_demand(
    section_id: str,
    date: date = Query(..., description="Date for demand data"),
    method: Optional[str] = Query(None, regex="^(ros|rid_ms|awd|combined)$")
) -> DemandResponse:
    """Get daily water demand for a specific section"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                dd.date,
                dd.section_id,
                p.zone,
                SUM(dd.ros_demand_m3) as ros_demand_m3,
                SUM(dd.aquacrop_demand_m3) as rid_ms_demand_m3,
                SUM(COALESCE(dd.awd_demand_m3, dd.combined_demand_m3)) as awd_demand_m3,
                SUM(dd.combined_demand_m3) as combined_demand_m3,
                SUM(p.area_rai) as area_rai,
                -- Water level adjustment fields
                SUM(dd.original_demand_m3) as original_demand_m3,
                SUM(dd.adjusted_demand_m3) as adjusted_demand_m3,
                AVG(dd.water_level_m) as water_level_m,
                AVG(dd.adjustment_factor) as adjustment_factor,
                MAX(dd.adjustment_method) as adjustment_method
            FROM ros_gis.daily_demands dd
            JOIN ros_gis.plots p ON p.plot_id = dd.plot_id
            WHERE dd.section_id = $1 AND dd.date = $2
            GROUP BY dd.date, dd.section_id, p.zone
        """
        
        result = await conn.fetchrow(query, section_id, date)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"No demand data found for section {section_id} on {date}")
        
        return DemandResponse(
            date=result['date'],
            section_id=result['section_id'],
            zone=result['zone'],
            ros_demand_m3=float(result['ros_demand_m3'] or 0),
            rid_ms_demand_m3=float(result['rid_ms_demand_m3'] or 0),
            awd_demand_m3=float(result['awd_demand_m3'] or 0),
            combined_demand_m3=float(result['combined_demand_m3'] or 0),
            area_rai=float(result['area_rai'] or 0),
            # Water level adjustment fields
            original_demand_m3=float(result['original_demand_m3']) if result['original_demand_m3'] else None,
            adjusted_demand_m3=float(result['adjusted_demand_m3']) if result['adjusted_demand_m3'] else None,
            water_level_m=float(result['water_level_m']) if result['water_level_m'] else None,
            adjustment_factor=float(result['adjustment_factor'] or 1.0),
            adjustment_method=result['adjustment_method']
        )


@router.get("/sections/{section_id}/weekly")
async def get_section_weekly_demand(
    section_id: str,
    week_start: date = Query(..., description="Start date of the week"),
    method: Optional[str] = Query(None, regex="^(ros|rid_ms|awd|combined)$")
) -> Dict:
    """Get weekly water demand for a specific section"""
    db = Database()
    week_end = week_start + timedelta(days=6)
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                dd.date,
                SUM(dd.ros_demand_m3) as ros_demand_m3,
                SUM(dd.aquacrop_demand_m3) as rid_ms_demand_m3,
                SUM(COALESCE(dd.awd_demand_m3, dd.combined_demand_m3)) as awd_demand_m3,
                SUM(dd.combined_demand_m3) as combined_demand_m3
            FROM ros_gis.daily_demands dd
            WHERE dd.section_id = $1 
                AND dd.date >= $2 
                AND dd.date <= $3
            GROUP BY dd.date
            ORDER BY dd.date
        """
        
        results = await conn.fetch(query, section_id, week_start, week_end)
        
        # Calculate totals
        total_ros = sum(r['ros_demand_m3'] or 0 for r in results)
        total_rid_ms = sum(r['rid_ms_demand_m3'] or 0 for r in results)
        total_awd = sum(r['awd_demand_m3'] or 0 for r in results)
        total_combined = sum(r['combined_demand_m3'] or 0 for r in results)
        
        return {
            "section_id": section_id,
            "week_start": week_start,
            "week_end": week_end,
            "total_ros_m3": float(total_ros),
            "total_rid_ms_m3": float(total_rid_ms),
            "total_awd_m3": float(total_awd),
            "total_combined_m3": float(total_combined),
            "daily_breakdown": [
                {
                    "date": r['date'],
                    "ros_m3": float(r['ros_demand_m3'] or 0),
                    "rid_ms_m3": float(r['rid_ms_demand_m3'] or 0),
                    "awd_m3": float(r['awd_demand_m3'] or 0),
                    "combined_m3": float(r['combined_demand_m3'] or 0)
                }
                for r in results
            ]
        }


@router.get("/sections/{section_id}/accumulated-weekly")
async def get_section_accumulated_weekly(
    section_id: str,
    week_start: date = Query(..., description="Start date of the week")
) -> AccumulatedDemandResponse:
    """Get accumulated weekly demand for a section"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                ad.*,
                COALESCE(SUM(dd.ros_demand_m3), 0) as total_ros,
                COALESCE(SUM(dd.aquacrop_demand_m3), 0) as total_rid_ms,
                COALESCE(SUM(dd.awd_demand_m3), 0) as total_awd
            FROM ros_gis.accumulated_demands ad
            LEFT JOIN ros_gis.daily_demands dd ON 
                dd.section_id = ad.section_id AND
                dd.date >= ad.start_date AND
                dd.date <= ad.end_date
            WHERE ad.section_id = $1 
                AND ad.control_interval = 'weekly'
                AND ad.start_date = $2
            GROUP BY ad.accumulation_id
        """
        
        result = await conn.fetchrow(query, section_id, week_start)
        
        if not result:
            # Calculate on the fly if not pre-accumulated
            week_data = await get_section_weekly_demand(section_id, week_start)
            return AccumulatedDemandResponse(
                section_id=section_id,
                period="weekly",
                start_date=week_start,
                end_date=week_start + timedelta(days=6),
                total_demand_m3=week_data["total_combined_m3"],
                total_ros_m3=week_data["total_ros_m3"],
                total_rid_ms_m3=week_data["total_rid_ms_m3"],
                total_awd_m3=week_data["total_awd_m3"],
                plot_count=len(week_data["daily_breakdown"])
            )
        
        return AccumulatedDemandResponse(
            section_id=result['section_id'],
            period=result['control_interval'],
            start_date=result['start_date'],
            end_date=result['end_date'],
            total_demand_m3=float(result['total_demand_m3']),
            total_ros_m3=float(result['total_ros']),
            total_rid_ms_m3=float(result['total_rid_ms']),
            total_awd_m3=float(result['total_awd']),
            plot_count=result['plot_count']
        )


@router.get("/sections/{section_id}/seasonal")
async def get_section_seasonal_demand(
    section_id: str,
    season_id: Optional[str] = Query(None, description="Season config ID")
) -> Dict:
    """Get seasonal demand for a section"""
    db = Database()
    
    # Get active season if not specified
    if not season_id:
        async with db.get_connection() as conn:
            season = await conn.fetchrow("SELECT * FROM ros_gis.v_active_crop_season")
            if not season:
                raise HTTPException(status_code=404, detail="No active season found")
            season_id = str(season['config_id'])
            start_date = season['start_date']
            end_date = season['end_date']
    else:
        async with db.get_connection() as conn:
            season = await conn.fetchrow(
                "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1",
                season_id
            )
            if not season:
                raise HTTPException(status_code=404, detail="Season not found")
            start_date = season['start_date']
            end_date = season['end_date']
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT dd.plot_id) as plot_count,
                SUM(dd.ros_demand_m3) as total_ros,
                SUM(dd.aquacrop_demand_m3) as total_rid_ms,
                SUM(dd.combined_demand_m3) as total_combined,
                DATE_TRUNC('month', dd.date) as month
            FROM ros_gis.daily_demands dd
            WHERE dd.section_id = $1
                AND dd.date >= $2
                AND dd.date <= $3
            GROUP BY DATE_TRUNC('month', dd.date)
            ORDER BY month
        """
        
        results = await conn.fetch(query, section_id, start_date, end_date)
        
        total_ros = sum(r['total_ros'] or 0 for r in results)
        total_rid_ms = sum(r['total_rid_ms'] or 0 for r in results)
        total_combined = sum(r['total_combined'] or 0 for r in results)
        
        return {
            "section_id": section_id,
            "season_id": season_id,
            "season_name": season['season_name'],
            "start_date": start_date,
            "end_date": end_date,
            "total_ros_m3": float(total_ros),
            "total_rid_ms_m3": float(total_rid_ms),
            "total_combined_m3": float(total_combined),
            "monthly_breakdown": [
                {
                    "month": r['month'].strftime('%Y-%m'),
                    "ros_m3": float(r['total_ros'] or 0),
                    "rid_ms_m3": float(r['total_rid_ms'] or 0),
                    "combined_m3": float(r['total_combined'] or 0)
                }
                for r in results
            ]
        }


# Zone Level Endpoints
@router.get("/zones/{zone_id}/daily")
async def get_zone_daily_demand(
    zone_id: int,
    date: date = Query(..., description="Date for demand data")
) -> Dict:
    """Get daily water demand for all sections in a zone"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                s.section_id,
                s.section_name,
                SUM(dd.ros_demand_m3) as ros_demand_m3,
                SUM(dd.aquacrop_demand_m3) as rid_ms_demand_m3,
                SUM(dd.combined_demand_m3) as combined_demand_m3,
                SUM(DISTINCT p.area_rai) as area_rai
            FROM ros_gis.sections s
            LEFT JOIN ros_gis.plots p ON p.section_id = s.section_id
            LEFT JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id AND dd.date = $2
            WHERE s.zone = $1
            GROUP BY s.section_id, s.section_name
        """
        
        results = await conn.fetch(query, zone_id, date)
        
        total_ros = sum(r['ros_demand_m3'] or 0 for r in results)
        total_rid_ms = sum(r['rid_ms_demand_m3'] or 0 for r in results)
        total_combined = sum(r['combined_demand_m3'] or 0 for r in results)
        total_area = sum(r['area_rai'] or 0 for r in results)
        
        return {
            "zone_id": zone_id,
            "date": date,
            "total_ros_m3": float(total_ros),
            "total_rid_ms_m3": float(total_rid_ms),
            "total_combined_m3": float(total_combined),
            "total_area_rai": float(total_area),
            "sections": [
                {
                    "section_id": r['section_id'],
                    "section_name": r['section_name'],
                    "ros_m3": float(r['ros_demand_m3'] or 0),
                    "rid_ms_m3": float(r['rid_ms_demand_m3'] or 0),
                    "combined_m3": float(r['combined_demand_m3'] or 0),
                    "area_rai": float(r['area_rai'] or 0)
                }
                for r in results
            ]
        }


@router.get("/zones/{zone_id}/weekly")
async def get_zone_weekly_demand(
    zone_id: int,
    week_start: date = Query(..., description="Start date of the week")
) -> Dict:
    """Get weekly water demand for all sections in a zone"""
    week_end = week_start + timedelta(days=6)
    daily_demands = []
    
    # Get daily demands for each day
    current_date = week_start
    while current_date <= week_end:
        daily_data = await get_zone_daily_demand(zone_id, current_date)
        daily_demands.append({
            "date": current_date,
            "ros_m3": daily_data["total_ros_m3"],
            "rid_ms_m3": daily_data["total_rid_ms_m3"],
            "combined_m3": daily_data["total_combined_m3"]
        })
        current_date += timedelta(days=1)
    
    return {
        "zone_id": zone_id,
        "week_start": week_start,
        "week_end": week_end,
        "total_ros_m3": sum(d["ros_m3"] for d in daily_demands),
        "total_rid_ms_m3": sum(d["rid_ms_m3"] for d in daily_demands),
        "total_combined_m3": sum(d["combined_m3"] for d in daily_demands),
        "daily_breakdown": daily_demands
    }


@router.get("/zones/{zone_id}/seasonal")
async def get_zone_seasonal_demand(
    zone_id: int,
    season_id: Optional[str] = Query(None, description="Season config ID")
) -> Dict:
    """Get seasonal demand for all sections in a zone"""
    db = Database()
    
    # Get season dates
    if not season_id:
        async with db.get_connection() as conn:
            season = await conn.fetchrow("SELECT * FROM ros_gis.v_active_crop_season")
            if not season:
                raise HTTPException(status_code=404, detail="No active season found")
    else:
        async with db.get_connection() as conn:
            season = await conn.fetchrow(
                "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1",
                season_id
            )
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT dd.plot_id) as plot_count,
                COUNT(DISTINCT s.section_id) as section_count,
                SUM(dd.ros_demand_m3) as total_ros,
                SUM(dd.aquacrop_demand_m3) as total_rid_ms,
                SUM(dd.combined_demand_m3) as total_combined,
                DATE_TRUNC('month', dd.date) as month
            FROM ros_gis.sections s
            JOIN ros_gis.plots p ON p.section_id = s.section_id
            JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id
            WHERE s.zone = $1
                AND dd.date >= $2
                AND dd.date <= $3
            GROUP BY DATE_TRUNC('month', dd.date)
            ORDER BY month
        """
        
        results = await conn.fetch(query, zone_id, season['start_date'], season['end_date'])
        
        return {
            "zone_id": zone_id,
            "season_id": str(season['config_id']),
            "season_name": season['season_name'],
            "total_ros_m3": sum(r['total_ros'] or 0 for r in results),
            "total_rid_ms_m3": sum(r['total_rid_ms'] or 0 for r in results),
            "total_combined_m3": sum(r['total_combined'] or 0 for r in results),
            "monthly_breakdown": [
                {
                    "month": r['month'].strftime('%Y-%m'),
                    "ros_m3": float(r['total_ros'] or 0),
                    "rid_ms_m3": float(r['total_rid_ms'] or 0),
                    "combined_m3": float(r['total_combined'] or 0)
                }
                for r in results
            ]
        }


# Munbon Level Endpoints
@router.get("/munbon/daily")
async def get_munbon_daily_demand(
    date: date = Query(..., description="Date for demand data")
) -> Dict:
    """Get daily water demand for entire Munbon area"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT s.zone) as zone_count,
                COUNT(DISTINCT dd.section_id) as section_count,
                COUNT(DISTINCT dd.plot_id) as plot_count,
                SUM(dd.ros_demand_m3) as total_ros,
                SUM(dd.aquacrop_demand_m3) as total_rid_ms,
                SUM(dd.combined_demand_m3) as total_combined,
                SUM(DISTINCT p.area_rai) as total_area
            FROM ros_gis.daily_demands dd
            JOIN ros_gis.plots p ON p.plot_id = dd.plot_id
            JOIN ros_gis.sections s ON s.section_id = dd.section_id
            WHERE dd.date = $1
        """
        
        result = await conn.fetchrow(query, date)
        
        return {
            "date": date,
            "zone_count": result['zone_count'] or 0,
            "section_count": result['section_count'] or 0,
            "plot_count": result['plot_count'] or 0,
            "total_area_rai": float(result['total_area'] or 0),
            "total_ros_m3": float(result['total_ros'] or 0),
            "total_rid_ms_m3": float(result['total_rid_ms'] or 0),
            "total_combined_m3": float(result['total_combined'] or 0)
        }


@router.get("/munbon/weekly")
async def get_munbon_weekly_demand(
    week_start: date = Query(..., description="Start date of the week")
) -> Dict:
    """Get weekly water demand for entire Munbon area"""
    week_end = week_start + timedelta(days=6)
    daily_demands = []
    
    current_date = week_start
    while current_date <= week_end:
        daily_data = await get_munbon_daily_demand(current_date)
        daily_demands.append({
            "date": current_date,
            "ros_m3": daily_data["total_ros_m3"],
            "rid_ms_m3": daily_data["total_rid_ms_m3"],
            "combined_m3": daily_data["total_combined_m3"]
        })
        current_date += timedelta(days=1)
    
    return {
        "week_start": week_start,
        "week_end": week_end,
        "total_ros_m3": sum(d["ros_m3"] for d in daily_demands),
        "total_rid_ms_m3": sum(d["rid_ms_m3"] for d in daily_demands),
        "total_combined_m3": sum(d["combined_m3"] for d in daily_demands),
        "daily_breakdown": daily_demands
    }


@router.get("/munbon/seasonal")
async def get_munbon_seasonal_demand(
    season_id: Optional[str] = Query(None, description="Season config ID")
) -> Dict:
    """Get seasonal demand for entire Munbon area"""
    db = Database()
    
    # Get season
    if not season_id:
        async with db.get_connection() as conn:
            season = await conn.fetchrow("SELECT * FROM ros_gis.v_active_crop_season")
            if not season:
                raise HTTPException(status_code=404, detail="No active season found")
    else:
        async with db.get_connection() as conn:
            season = await conn.fetchrow(
                "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1",
                season_id
            )
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT s.zone) as zone_count,
                COUNT(DISTINCT dd.section_id) as section_count,
                COUNT(DISTINCT dd.plot_id) as plot_count,
                SUM(dd.ros_demand_m3) as total_ros,
                SUM(dd.aquacrop_demand_m3) as total_rid_ms,
                SUM(dd.combined_demand_m3) as total_combined,
                DATE_TRUNC('month', dd.date) as month
            FROM ros_gis.daily_demands dd
            JOIN ros_gis.sections s ON s.section_id = dd.section_id
            WHERE dd.date >= $1 AND dd.date <= $2
            GROUP BY DATE_TRUNC('month', dd.date)
            ORDER BY month
        """
        
        results = await conn.fetch(query, season['start_date'], season['end_date'])
        
        return {
            "season_id": str(season['config_id']),
            "season_name": season['season_name'],
            "total_ros_m3": sum(r['total_ros'] or 0 for r in results),
            "total_rid_ms_m3": sum(r['total_rid_ms'] or 0 for r in results),
            "total_combined_m3": sum(r['total_combined'] or 0 for r in results),
            "zone_count": max(r['zone_count'] or 0 for r in results),
            "section_count": max(r['section_count'] or 0 for r in results),
            "monthly_breakdown": [
                {
                    "month": r['month'].strftime('%Y-%m'),
                    "ros_m3": float(r['total_ros'] or 0),
                    "rid_ms_m3": float(r['total_rid_ms'] or 0),
                    "combined_m3": float(r['total_combined'] or 0)
                }
                for r in results
            ]
        }


# Map/Spatial Endpoints
@router.get("/spatial/map-data")
async def get_map_data(
    date: date = Query(..., description="Date for demand data"),
    feature_type: str = Query("section", regex="^(section|zone)$"),
    bbox: Optional[str] = Query(None, description="Bounding box: minLon,minLat,maxLon,maxLat")
) -> List[SpatialDemandResponse]:
    """Get spatial demand data for map visualization"""
    db = Database()
    bbox_coords = None
    
    if bbox:
        try:
            bbox_coords = [float(x) for x in bbox.split(',')]
            if len(bbox_coords) != 4:
                raise ValueError("Invalid bbox format")
        except:
            raise HTTPException(status_code=400, detail="Invalid bbox format. Use: minLon,minLat,maxLon,maxLat")
    
    async with db.get_connection() as conn:
        if feature_type == "section":
            query = """
                SELECT 
                    s.section_id as feature_id,
                    'section' as feature_type,
                    ST_AsGeoJSON(s.geometry)::json as geometry,
                    s.section_name as label,
                    s.area_rai,
                    COALESCE(SUM(dd.combined_demand_m3), 0) as current_demand,
                    COALESCE(SUM(dd.ros_demand_m3), 0) as ros_demand,
                    COALESCE(SUM(dd.aquacrop_demand_m3), 0) as rid_ms_demand
                FROM ros_gis.sections s
                LEFT JOIN ros_gis.plots p ON p.section_id = s.section_id
                LEFT JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id AND dd.date = $1
            """
            
            if bbox_coords:
                query += """
                    WHERE ST_Intersects(
                        s.geometry, 
                        ST_MakeEnvelope($2, $3, $4, $5, 4326)
                    )
                """
            
            query += " GROUP BY s.section_id, s.section_name, s.geometry, s.area_rai"
            
        else:  # zone
            query = """
                SELECT 
                    z.zone_id::text as feature_id,
                    'zone' as feature_type,
                    ST_AsGeoJSON(z.geometry)::json as geometry,
                    z.zone_name as label,
                    SUM(DISTINCT s.area_rai) as area_rai,
                    COALESCE(SUM(dd.combined_demand_m3), 0) as current_demand,
                    COALESCE(SUM(dd.ros_demand_m3), 0) as ros_demand,
                    COALESCE(SUM(dd.aquacrop_demand_m3), 0) as rid_ms_demand
                FROM ros_gis.zones z
                LEFT JOIN ros_gis.sections s ON s.zone = z.zone_id
                LEFT JOIN ros_gis.plots p ON p.section_id = s.section_id
                LEFT JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id AND dd.date = $1
            """
            
            if bbox_coords:
                query += """
                    WHERE ST_Intersects(
                        z.geometry, 
                        ST_MakeEnvelope($2, $3, $4, $5, 4326)
                    )
                """
            
            query += " GROUP BY z.zone_id, z.zone_name, z.geometry"
        
        # Execute query
        if bbox_coords:
            results = await conn.fetch(query, date, *bbox_coords)
        else:
            results = await conn.fetch(query, date)
        
        return [
            SpatialDemandResponse(
                feature_id=r['feature_id'],
                feature_type=r['feature_type'],
                geometry=r['geometry'],
                current_demand_m3=float(r['current_demand']),
                ros_demand_m3=float(r['ros_demand']),
                rid_ms_demand_m3=float(r['rid_ms_demand']),
                area_rai=float(r['area_rai'] or 0),
                label=r['label']
            )
            for r in results
        ]


# Comparison Endpoint
@router.get("/compare/{section_id}")
async def compare_methods(
    section_id: str,
    start_date: date = Query(...),
    end_date: date = Query(...)
) -> Dict:
    """Compare ROS vs RID-MS methods for a section"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT plot_id) as plot_count,
                SUM(ros_demand_m3) as ros_total,
                AVG(ros_demand_m3) as ros_avg,
                MAX(ros_demand_m3) as ros_peak,
                SUM(aquacrop_demand_m3) as rid_ms_total,
                AVG(aquacrop_demand_m3) as rid_ms_avg,
                MAX(aquacrop_demand_m3) as rid_ms_peak
            FROM ros_gis.daily_demands
            WHERE section_id = $1
                AND date >= $2
                AND date <= $3
        """
        
        result = await conn.fetchrow(query, section_id, start_date, end_date)
        
        ros_total = float(result['ros_total'] or 0)
        rid_ms_total = float(result['rid_ms_total'] or 0)
        difference = rid_ms_total - ros_total
        difference_percent = (difference / ros_total * 100) if ros_total > 0 else 0
        
        return {
            "section_id": section_id,
            "period": f"{start_date} to {end_date}",
            "ros_total_m3": ros_total,
            "ros_daily_avg_m3": float(result['ros_avg'] or 0),
            "ros_peak_m3": float(result['ros_peak'] or 0),
            "rid_ms_total_m3": rid_ms_total,
            "rid_ms_daily_avg_m3": float(result['rid_ms_avg'] or 0),
            "rid_ms_peak_m3": float(result['rid_ms_peak'] or 0),
            "difference_m3": difference,
            "difference_percent": difference_percent,
            "plot_count": result['plot_count'] or 0
        }


# AWD-Specific Endpoints
class AWDDemandResponse(BaseModel):
    """AWD-specific demand response with savings information"""
    section_id: str
    date: date
    standard_demand_m3: float
    awd_demand_m3: float
    water_saved_m3: float
    savings_percent: float
    awd_enabled_plots: int
    total_plots: int
    irrigation_interval_days: Optional[int]
    next_irrigation_date: Optional[date]


@router.get("/sections/{section_id}/awd-status")
async def get_section_awd_status(
    section_id: str,
    date: date = Query(..., description="Date for AWD status")
) -> AWDDemandResponse:
    """Get AWD status and demand for a section"""
    from services.awd_integration import AWDIntegrationService
    
    db = Database()
    awd_service = AWDIntegrationService()
    
    # Get AWD status for the section
    awd_status = await awd_service.get_section_awd_status(section_id)
    
    # Get demand data
    async with db.get_connection() as conn:
        query = """
            SELECT 
                COUNT(DISTINCT pwd.plot_id) as total_plots,
                COUNT(DISTINCT pwd.plot_id) FILTER (WHERE pwd.awd_enabled) as awd_plots,
                SUM(pwd.combined_demand_m3) as standard_demand,
                SUM(pwd.awd_demand_m3) as awd_demand,
                SUM(pwd.awd_water_saved_m3) as water_saved,
                AVG(pwd.awd_savings_percent) FILTER (WHERE pwd.awd_enabled) as avg_savings,
                AVG(pwd.awd_irrigation_interval_days) FILTER (WHERE pwd.awd_enabled) as avg_interval
            FROM ros_gis.plot_water_demand pwd
            WHERE pwd.section_id = $1 AND pwd.date = $2
        """
        
        result = await conn.fetchrow(query, section_id, date)
        
        if not result or result['total_plots'] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No AWD data found for section {section_id} on {date}"
            )
        
        return AWDDemandResponse(
            section_id=section_id,
            date=date,
            standard_demand_m3=float(result['standard_demand'] or 0),
            awd_demand_m3=float(result['awd_demand'] or result['standard_demand'] or 0),
            water_saved_m3=float(result['water_saved'] or 0),
            savings_percent=float(result['avg_savings'] or 0),
            awd_enabled_plots=result['awd_plots'] or 0,
            total_plots=result['total_plots'],
            irrigation_interval_days=int(result['avg_interval']) if result['avg_interval'] else None,
            next_irrigation_date=None  # Would be calculated based on last irrigation
        )


@router.get("/zones/{zone_id}/awd-summary")
async def get_zone_awd_summary(
    zone_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...)
) -> Dict:
    """Get AWD summary for a zone over a date range"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT 
                p.zone,
                COUNT(DISTINCT pwd.plot_id) as total_plots,
                COUNT(DISTINCT pwd.plot_id) FILTER (WHERE pwd.awd_enabled) as awd_enabled_plots,
                SUM(pwd.combined_demand_m3) as total_standard_demand,
                SUM(pwd.awd_demand_m3) as total_awd_demand,
                SUM(pwd.awd_water_saved_m3) as total_water_saved,
                AVG(pwd.awd_savings_percent) FILTER (WHERE pwd.awd_enabled) as avg_savings_percent,
                SUM(p.area_rai) as total_area_rai,
                SUM(p.area_rai) FILTER (WHERE pwd.awd_enabled) as awd_area_rai
            FROM ros_gis.plot_water_demand pwd
            JOIN ros_gis.plots p ON p.plot_id = pwd.plot_id
            WHERE p.zone = $1 
                AND pwd.date >= $2 
                AND pwd.date <= $3
            GROUP BY p.zone
        """
        
        result = await conn.fetchrow(query, zone_id, start_date, end_date)
        
        if not result:
            return {
                "zone_id": zone_id,
                "start_date": start_date,
                "end_date": end_date,
                "awd_adoption_rate": 0,
                "total_water_saved_m3": 0,
                "avg_savings_percent": 0,
                "co2_reduction_kg": 0
            }
        
        adoption_rate = (result['awd_enabled_plots'] / result['total_plots'] * 100) if result['total_plots'] > 0 else 0
        co2_reduction = result['total_water_saved'] * 0.0002  # Rough estimate: 0.2kg CO2 per m3 water saved
        
        return {
            "zone_id": zone_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_plots": result['total_plots'],
            "awd_enabled_plots": result['awd_enabled_plots'],
            "awd_adoption_rate": round(adoption_rate, 2),
            "total_area_rai": float(result['total_area_rai'] or 0),
            "awd_area_rai": float(result['awd_area_rai'] or 0),
            "total_standard_demand_m3": float(result['total_standard_demand'] or 0),
            "total_awd_demand_m3": float(result['total_awd_demand'] or 0),
            "total_water_saved_m3": float(result['total_water_saved'] or 0),
            "avg_savings_percent": float(result['avg_savings_percent'] or 0),
            "co2_reduction_kg": round(co2_reduction, 2)
        }


@router.get("/munbon/awd-impact")
async def get_munbon_awd_impact(
    season_id: Optional[str] = Query(None, description="Crop season ID")
) -> Dict:
    """Get AWD impact analysis for entire Munbon area"""
    db = Database()
    
    # Get active season if not specified
    if not season_id:
        season_query = CropSeasonQueries()
        active_season = await season_query.get_active_season(None)
        if not active_season:
            raise HTTPException(status_code=404, detail="No active crop season found")
        season_id = active_season.config_id
    
    async with db.get_connection() as conn:
        # Get season date range
        season_query = """
            SELECT start_date, end_date, season_name 
            FROM ros_gis.crop_season_config 
            WHERE config_id = $1
        """
        season = await conn.fetchrow(season_query, season_id)
        
        if not season:
            raise HTTPException(status_code=404, detail=f"Season {season_id} not found")
        
        # Get AWD impact data
        query = """
            SELECT 
                COUNT(DISTINCT pwd.plot_id) as total_plots,
                COUNT(DISTINCT pwd.plot_id) FILTER (WHERE pwd.awd_enabled) as awd_plots,
                COUNT(DISTINCT pwd.section_id) as total_sections,
                COUNT(DISTINCT pwd.section_id) FILTER (WHERE EXISTS (
                    SELECT 1 FROM ros_gis.plot_water_demand pwd2 
                    WHERE pwd2.section_id = pwd.section_id 
                    AND pwd2.awd_enabled = true
                    AND pwd2.date = pwd.date
                )) as awd_sections,
                SUM(pwd.combined_demand_m3) as total_standard_demand,
                SUM(pwd.awd_demand_m3) as total_awd_demand,
                SUM(pwd.awd_water_saved_m3) as total_water_saved,
                AVG(pwd.awd_savings_percent) FILTER (WHERE pwd.awd_enabled) as avg_savings
            FROM ros_gis.plot_water_demand pwd
            WHERE pwd.date >= $1 AND pwd.date <= $2
        """
        
        result = await conn.fetchrow(query, season['start_date'], season['end_date'])
        
        # Calculate projections
        current_savings = float(result['total_water_saved'] or 0)
        potential_savings = float(result['total_standard_demand'] or 0) * 0.25  # 25% potential
        adoption_rate = (result['awd_plots'] / result['total_plots'] * 100) if result['total_plots'] > 0 else 0
        
        return {
            "season_id": season_id,
            "season_name": season['season_name'],
            "date_range": f"{season['start_date']} to {season['end_date']}",
            "current_status": {
                "total_plots": result['total_plots'],
                "awd_enabled_plots": result['awd_plots'],
                "adoption_rate_percent": round(adoption_rate, 2),
                "total_sections": result['total_sections'],
                "awd_sections": result['awd_sections']
            },
            "water_savings": {
                "total_standard_demand_m3": float(result['total_standard_demand'] or 0),
                "total_awd_demand_m3": float(result['total_awd_demand'] or 0),
                "actual_water_saved_m3": current_savings,
                "potential_water_savings_m3": potential_savings,
                "avg_savings_percent": float(result['avg_savings'] or 0)
            },
            "environmental_impact": {
                "co2_reduced_kg": round(current_savings * 0.0002, 2),
                "co2_potential_kg": round(potential_savings * 0.0002, 2),
                "energy_saved_kwh": round(current_savings * 0.3, 2)  # Estimate
            },
            "recommendations": [
                "Expand AWD adoption to more sections",
                "Provide training for farmers on AWD techniques",
                "Install more soil moisture sensors",
                "Monitor yield impacts closely"
            ] if adoption_rate < 50 else [
                "Maintain current AWD practices",
                "Optimize irrigation intervals based on soil type",
                "Share success stories with neighboring areas"
            ]
        }
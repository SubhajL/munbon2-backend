from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict
from datetime import date
from pydantic import BaseModel
from uuid import uuid4

from core import get_logger
from database import Database
from schemas.crop_season import CropSeasonConfig, CropSeasonConfigInput

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/crop-season", tags=["crop-season"])


# Request/Response Models
class InitializeSeasonRequest(BaseModel):
    season_name: str
    season_year: int
    start_date: date
    end_date: date
    coverage_type: str  # 'full_munbon', 'zones', 'sections'
    selected_zones: Optional[List[int]] = None
    selected_sections: Optional[List[str]] = None
    result_display_period: str = "weekly"
    accumulation_period: str = "monthly"
    demand_display_method: str = "both_separate"
    demand_combination_strategy: str = "aquacrop_priority"
    map_default_view: str = "zones"
    map_color_scheme: str = "demand_gradient"
    show_irrigation_channels: bool = True
    show_delivery_gates: bool = True
    weather_data_source: str = "tmd"
    rainfall_adjustment_enabled: bool = True
    awd_integration_enabled: bool = False


class SeasonConfigResponse(BaseModel):
    config_id: str
    season_name: str
    season_year: int
    start_date: date
    end_date: date
    coverage_type: str
    selected_zones: Optional[List[int]]
    selected_sections: Optional[List[str]]
    result_display_period: str
    accumulation_period: str
    demand_display_method: str
    demand_combination_strategy: str
    map_default_view: str
    is_active: bool


@router.post("/initialize")
async def initialize_season(
    request: InitializeSeasonRequest = Body(...)
) -> Dict:
    """Initialize a new crop season with configuration"""
    db = Database()
    
    try:
        # Validate configuration
        if request.coverage_type == "zones" and not request.selected_zones:
            raise HTTPException(
                status_code=400, 
                detail="Selected zones required when coverage type is 'zones'"
            )
        
        if request.coverage_type == "sections" and not request.selected_sections:
            raise HTTPException(
                status_code=400,
                detail="Selected sections required when coverage type is 'sections'"
            )
        
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=400,
                detail="End date must be after start date"
            )
        
        async with db.get_connection() as conn:
            config_id = str(uuid4())
            
            # Insert configuration
            query = """
                INSERT INTO ros_gis.crop_season_config (
                    config_id, season_name, season_year, start_date, end_date,
                    coverage_type, selected_zones, selected_sections,
                    result_display_period, accumulation_period,
                    demand_display_method, demand_combination_strategy,
                    map_default_view, map_color_scheme,
                    show_irrigation_channels, show_delivery_gates,
                    weather_data_source, rainfall_adjustment_enabled,
                    awd_integration_enabled, created_by, is_active
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
                )
            """
            
            await conn.execute(
                query,
                config_id,
                request.season_name,
                request.season_year,
                request.start_date,
                request.end_date,
                request.coverage_type,
                request.selected_zones,
                request.selected_sections,
                request.result_display_period,
                request.accumulation_period,
                request.demand_display_method,
                request.demand_combination_strategy,
                request.map_default_view,
                request.map_color_scheme,
                request.show_irrigation_channels,
                request.show_delivery_gates,
                request.weather_data_source,
                request.rainfall_adjustment_enabled,
                request.awd_integration_enabled,
                'api_user',  # Would get from auth context
                True  # Set as active
            )
            
            logger.info(
                "Crop season initialized",
                config_id=config_id,
                season_name=request.season_name
            )
            
            return {
                "success": True,
                "config_id": config_id,
                "message": f"Crop season '{request.season_name}' initialized successfully",
                "season_name": request.season_name,
                "start_date": request.start_date,
                "end_date": request.end_date
            }
            
    except Exception as e:
        logger.error("Failed to initialize crop season", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_season() -> SeasonConfigResponse:
    """Get the currently active crop season configuration"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = "SELECT * FROM ros_gis.v_active_crop_season"
        result = await conn.fetchrow(query)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="No active crop season found. Please initialize a season first."
            )
        
        return SeasonConfigResponse(
            config_id=str(result['config_id']),
            season_name=result['season_name'],
            season_year=result['season_year'],
            start_date=result['start_date'],
            end_date=result['end_date'],
            coverage_type=result['coverage_type'],
            selected_zones=result['selected_zones'],
            selected_sections=result['selected_sections'],
            result_display_period=result['result_display_period'],
            accumulation_period=result['accumulation_period'],
            demand_display_method=result['demand_display_method'],
            demand_combination_strategy=result['demand_combination_strategy'],
            map_default_view=result['map_default_view'],
            is_active=result['is_active']
        )


@router.get("/list")
async def list_seasons(
    year: Optional[int] = None,
    limit: int = 10
) -> List[SeasonConfigResponse]:
    """List all crop season configurations"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = """
            SELECT * FROM ros_gis.crop_season_config
        """
        params = []
        
        if year:
            query += " WHERE season_year = $1"
            params.append(year)
        
        query += " ORDER BY created_at DESC LIMIT ${}"
        params.append(limit)
        query = query.format(len(params))
        
        results = await conn.fetch(query, *params)
        
        return [
            SeasonConfigResponse(
                config_id=str(row['config_id']),
                season_name=row['season_name'],
                season_year=row['season_year'],
                start_date=row['start_date'],
                end_date=row['end_date'],
                coverage_type=row['coverage_type'],
                selected_zones=row['selected_zones'],
                selected_sections=row['selected_sections'],
                result_display_period=row['result_display_period'],
                accumulation_period=row['accumulation_period'],
                demand_display_method=row['demand_display_method'],
                demand_combination_strategy=row['demand_combination_strategy'],
                map_default_view=row['map_default_view'],
                is_active=row['is_active']
            )
            for row in results
        ]


@router.get("/{config_id}")
async def get_season_by_id(config_id: str) -> SeasonConfigResponse:
    """Get a specific crop season configuration by ID"""
    db = Database()
    
    async with db.get_connection() as conn:
        query = "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1"
        result = await conn.fetchrow(query, config_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Crop season configuration {config_id} not found"
            )
        
        return SeasonConfigResponse(
            config_id=str(result['config_id']),
            season_name=result['season_name'],
            season_year=result['season_year'],
            start_date=result['start_date'],
            end_date=result['end_date'],
            coverage_type=result['coverage_type'],
            selected_zones=result['selected_zones'],
            selected_sections=result['selected_sections'],
            result_display_period=result['result_display_period'],
            accumulation_period=result['accumulation_period'],
            demand_display_method=result['demand_display_method'],
            demand_combination_strategy=result['demand_combination_strategy'],
            map_default_view=result['map_default_view'],
            is_active=result['is_active']
        )


@router.put("/{config_id}")
async def update_season_config(
    config_id: str,
    updates: Dict = Body(...)
) -> Dict:
    """Update an existing crop season configuration"""
    db = Database()
    
    # List of updatable fields
    updatable_fields = [
        'season_name', 'result_display_period', 'accumulation_period',
        'demand_display_method', 'demand_combination_strategy',
        'map_default_view', 'map_color_scheme', 'show_irrigation_channels',
        'show_delivery_gates', 'rainfall_adjustment_enabled', 'awd_integration_enabled'
    ]
    
    # Filter only allowed fields
    filtered_updates = {k: v for k, v in updates.items() if k in updatable_fields}
    
    if not filtered_updates:
        raise HTTPException(
            status_code=400,
            detail="No valid fields to update"
        )
    
    async with db.get_connection() as conn:
        # Check if config exists
        check_query = "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1"
        existing = await conn.fetchrow(check_query, config_id)
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Crop season configuration {config_id} not found"
            )
        
        # Build update query
        set_clauses = []
        params = [config_id]
        param_count = 1
        
        for field, value in filtered_updates.items():
            param_count += 1
            set_clauses.append(f"{field} = ${param_count}")
            params.append(value)
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        
        update_query = f"""
            UPDATE ros_gis.crop_season_config 
            SET {', '.join(set_clauses)}
            WHERE config_id = $1
        """
        
        await conn.execute(update_query, *params)
        
        return {
            "success": True,
            "config_id": config_id,
            "message": "Configuration updated successfully",
            "updated_fields": list(filtered_updates.keys())
        }


@router.post("/{config_id}/activate")
async def activate_season(config_id: str) -> Dict:
    """Activate a specific crop season configuration"""
    db = Database()
    
    async with db.get_connection() as conn:
        # Check if config exists
        check_query = "SELECT season_name FROM ros_gis.crop_season_config WHERE config_id = $1"
        result = await conn.fetchrow(check_query, config_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Crop season configuration {config_id} not found"
            )
        
        # Activate the season (trigger will handle deactivating others)
        update_query = """
            UPDATE ros_gis.crop_season_config 
            SET is_active = true, updated_at = CURRENT_TIMESTAMP
            WHERE config_id = $1
        """
        
        await conn.execute(update_query, config_id)
        
        return {
            "success": True,
            "config_id": config_id,
            "message": f"Crop season '{result['season_name']}' activated successfully"
        }


@router.delete("/{config_id}")
async def delete_season(config_id: str) -> Dict:
    """Delete a crop season configuration"""
    db = Database()
    
    async with db.get_connection() as conn:
        # Check if config exists and is not active
        check_query = """
            SELECT season_name, is_active 
            FROM ros_gis.crop_season_config 
            WHERE config_id = $1
        """
        result = await conn.fetchrow(check_query, config_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Crop season configuration {config_id} not found"
            )
        
        if result['is_active']:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete active season. Please activate another season first."
            )
        
        # Delete the configuration
        delete_query = "DELETE FROM ros_gis.crop_season_config WHERE config_id = $1"
        await conn.execute(delete_query, config_id)
        
        return {
            "success": True,
            "config_id": config_id,
            "message": f"Crop season '{result['season_name']}' deleted successfully"
        }
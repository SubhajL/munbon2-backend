import strawberry
from typing import List, Optional
from datetime import datetime
import asyncio
from uuid import uuid4

from schemas.crop_season import (
    CropSeasonConfigType, CropSeasonConfigInput, CropSeasonInitResult,
    CropSeasonConfig, CoverageTypeEnum
)
from ..context import GraphQLContext
from core import get_logger
from database import Database

logger = get_logger(__name__)


@strawberry.type
class CropSeasonMutations:
    """Mutations for crop season configuration"""
    
    @strawberry.mutation
    async def initialize_crop_season(
        self,
        info: strawberry.Info[GraphQLContext],
        config: CropSeasonConfigInput
    ) -> CropSeasonInitResult:
        """
        Initialize a new crop season with configuration
        
        This will:
        1. Validate the configuration
        2. Deactivate any current active season
        3. Create the new season configuration
        4. Set it as active
        5. Initialize data structures for the season
        """
        db = Database()
        warnings = []
        
        try:
            # Validate configuration
            validation_warnings = await self._validate_config(config, db)
            warnings.extend(validation_warnings)
            
            async with db.get_connection() as conn:
                # Begin transaction
                async with conn.transaction():
                    config_id = str(uuid4())
                    
                    # Insert new configuration
                    insert_query = """
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
                        insert_query,
                        config_id,
                        config.season_name,
                        config.season_year,
                        config.start_date,
                        config.end_date,
                        config.coverage_type,
                        config.selected_zones,
                        config.selected_sections,
                        config.result_display_period,
                        config.accumulation_period,
                        config.demand_display_method,
                        config.demand_combination_strategy,
                        config.map_default_view,
                        config.map_color_scheme,
                        config.show_irrigation_channels,
                        config.show_delivery_gates,
                        config.weather_data_source,
                        config.rainfall_adjustment_enabled,
                        config.awd_integration_enabled,
                        info.context.user_id or 'system',
                        True  # Set as active
                    )
                    
                    # Initialize season data structures
                    await self._initialize_season_data(config_id, config, conn)
                    
                    # Log the initialization
                    logger.info(
                        "Crop season initialized",
                        config_id=config_id,
                        season_name=config.season_name,
                        coverage_type=config.coverage_type
                    )
                    
                    return CropSeasonInitResult(
                        success=True,
                        config_id=config_id,
                        message=f"Crop season '{config.season_name}' initialized successfully",
                        warnings=warnings if warnings else None
                    )
                    
        except Exception as e:
            logger.error("Failed to initialize crop season", error=str(e))
            return CropSeasonInitResult(
                success=False,
                config_id="",
                message=f"Failed to initialize crop season: {str(e)}",
                warnings=warnings if warnings else None
            )
    
    @strawberry.mutation
    async def update_crop_season_config(
        self,
        info: strawberry.Info[GraphQLContext],
        config_id: str,
        updates: CropSeasonConfigInput
    ) -> CropSeasonInitResult:
        """Update an existing crop season configuration"""
        db = Database()
        
        try:
            async with db.get_connection() as conn:
                # Check if config exists
                check_query = "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1"
                existing = await conn.fetchrow(check_query, config_id)
                
                if not existing:
                    return CropSeasonInitResult(
                        success=False,
                        config_id=config_id,
                        message="Crop season configuration not found"
                    )
                
                # Build update query dynamically
                update_fields = []
                params = [config_id]
                param_count = 1
                
                # Map input fields to update
                field_mapping = {
                    'season_name': updates.season_name,
                    'result_display_period': updates.result_display_period,
                    'accumulation_period': updates.accumulation_period,
                    'demand_display_method': updates.demand_display_method,
                    'demand_combination_strategy': updates.demand_combination_strategy,
                    'map_default_view': updates.map_default_view,
                    'map_color_scheme': updates.map_color_scheme,
                    'show_irrigation_channels': updates.show_irrigation_channels,
                    'show_delivery_gates': updates.show_delivery_gates,
                    'rainfall_adjustment_enabled': updates.rainfall_adjustment_enabled,
                    'awd_integration_enabled': updates.awd_integration_enabled
                }
                
                for field, value in field_mapping.items():
                    if value is not None:
                        param_count += 1
                        update_fields.append(f"{field} = ${param_count}")
                        params.append(value)
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    update_query = f"""
                        UPDATE ros_gis.crop_season_config 
                        SET {', '.join(update_fields)}
                        WHERE config_id = $1
                    """
                    
                    await conn.execute(update_query, *params)
                    
                    # Log changes in history
                    history_query = """
                        INSERT INTO ros_gis.crop_season_history (
                            config_id, action, changed_fields, changed_by
                        ) VALUES ($1, $2, $3, $4)
                    """
                    
                    await conn.execute(
                        history_query,
                        config_id,
                        'updated',
                        {'fields': list(field_mapping.keys())},
                        info.context.user_id or 'system'
                    )
                
                return CropSeasonInitResult(
                    success=True,
                    config_id=config_id,
                    message="Crop season configuration updated successfully"
                )
                
        except Exception as e:
            logger.error("Failed to update crop season", error=str(e))
            return CropSeasonInitResult(
                success=False,
                config_id=config_id,
                message=f"Failed to update configuration: {str(e)}"
            )
    
    @strawberry.mutation
    async def activate_crop_season(
        self,
        info: strawberry.Info[GraphQLContext],
        config_id: str
    ) -> CropSeasonInitResult:
        """Activate a specific crop season configuration"""
        db = Database()
        
        try:
            async with db.get_connection() as conn:
                # Check if config exists
                check_query = "SELECT season_name FROM ros_gis.crop_season_config WHERE config_id = $1"
                result = await conn.fetchrow(check_query, config_id)
                
                if not result:
                    return CropSeasonInitResult(
                        success=False,
                        config_id=config_id,
                        message="Crop season configuration not found"
                    )
                
                # Activate the season (trigger will handle deactivating others)
                update_query = """
                    UPDATE ros_gis.crop_season_config 
                    SET is_active = true, updated_at = CURRENT_TIMESTAMP
                    WHERE config_id = $1
                """
                
                await conn.execute(update_query, config_id)
                
                return CropSeasonInitResult(
                    success=True,
                    config_id=config_id,
                    message=f"Crop season '{result['season_name']}' activated successfully"
                )
                
        except Exception as e:
            logger.error("Failed to activate crop season", error=str(e))
            return CropSeasonInitResult(
                success=False,
                config_id=config_id,
                message=f"Failed to activate season: {str(e)}"
            )
    
    async def _validate_config(
        self, 
        config: CropSeasonConfigInput, 
        db: Database
    ) -> List[str]:
        """Validate crop season configuration"""
        warnings = []
        
        # Validate dates
        if config.end_date <= config.start_date:
            raise ValueError("End date must be after start date")
        
        # Validate coverage selections
        if config.coverage_type == CoverageTypeEnum.ZONES and not config.selected_zones:
            raise ValueError("Selected zones required when coverage type is 'zones'")
        
        if config.coverage_type == CoverageTypeEnum.SECTIONS and not config.selected_sections:
            raise ValueError("Selected sections required when coverage type is 'sections'")
        
        # Check for overlapping seasons
        async with db.get_connection() as conn:
            overlap_query = """
                SELECT season_name FROM ros_gis.crop_season_config
                WHERE is_active = true
                    AND NOT (end_date < $1 OR start_date > $2)
            """
            
            overlap = await conn.fetch(overlap_query, config.start_date, config.end_date)
            if overlap:
                warnings.append(
                    f"Warning: Season overlaps with active season '{overlap[0]['season_name']}'"
                )
        
        # Validate zone/section existence
        if config.selected_zones:
            async with db.get_connection() as conn:
                zone_check = """
                    SELECT COUNT(*) as valid_count 
                    FROM ros_gis.zones 
                    WHERE zone_id = ANY($1)
                """
                result = await conn.fetchrow(zone_check, config.selected_zones)
                if result['valid_count'] != len(config.selected_zones):
                    warnings.append("Some selected zones do not exist in the system")
        
        return warnings
    
    async def _initialize_season_data(
        self,
        config_id: str,
        config: CropSeasonConfigInput,
        conn
    ):
        """Initialize data structures for the new season"""
        
        # Create initial accumulated demand records based on control interval
        if config.accumulation_period != "none":
            # Get sections based on coverage type
            sections = []
            
            if config.coverage_type == CoverageTypeEnum.FULL_MUNBON:
                sections_query = "SELECT section_id FROM ros_gis.sections"
                result = await conn.fetch(sections_query)
                sections = [r['section_id'] for r in result]
                
            elif config.coverage_type == CoverageTypeEnum.ZONES:
                sections_query = """
                    SELECT section_id FROM ros_gis.sections 
                    WHERE zone = ANY($1)
                """
                result = await conn.fetch(sections_query, config.selected_zones)
                sections = [r['section_id'] for r in result]
                
            elif config.coverage_type == CoverageTypeEnum.SECTIONS:
                sections = config.selected_sections
            
            # Log initialization
            logger.info(
                "Season data initialized",
                config_id=config_id,
                section_count=len(sections),
                accumulation_period=config.accumulation_period
            )
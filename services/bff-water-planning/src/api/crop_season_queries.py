import strawberry
from typing import List, Optional
from datetime import datetime

from schemas.crop_season import CropSeasonConfigType
from ..context import GraphQLContext
from core import get_logger
from database import Database

logger = get_logger(__name__)


@strawberry.type 
class CropSeasonQueries:
    """Queries for crop season configuration"""
    
    @strawberry.field
    async def get_active_crop_season(
        self,
        info: strawberry.Info[GraphQLContext]
    ) -> Optional[CropSeasonConfigType]:
        """Get the currently active crop season configuration"""
        db = Database()
        
        async with db.get_connection() as conn:
            query = "SELECT * FROM ros_gis.v_active_crop_season"
            result = await conn.fetchrow(query)
            
            if not result:
                return None
            
            return CropSeasonConfigType(
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
                map_color_scheme=result['map_color_scheme'],
                show_irrigation_channels=result['show_irrigation_channels'],
                show_delivery_gates=result['show_delivery_gates'],
                weather_data_source=result['weather_data_source'],
                rainfall_adjustment_enabled=result['rainfall_adjustment_enabled'],
                awd_integration_enabled=result['awd_integration_enabled'],
                created_by=result['created_by'],
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                is_active=result['is_active']
            )
    
    @strawberry.field
    async def get_crop_season_by_id(
        self,
        info: strawberry.Info[GraphQLContext],
        config_id: str
    ) -> Optional[CropSeasonConfigType]:
        """Get a specific crop season configuration by ID"""
        db = Database()
        
        async with db.get_connection() as conn:
            query = "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1"
            result = await conn.fetchrow(query, config_id)
            
            if not result:
                return None
            
            return self._map_to_type(result)
    
    @strawberry.field
    async def list_crop_seasons(
        self,
        info: strawberry.Info[GraphQLContext],
        year: Optional[int] = None,
        limit: int = 10
    ) -> List[CropSeasonConfigType]:
        """List all crop season configurations"""
        db = Database()
        seasons = []
        
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
            
            for row in results:
                seasons.append(self._map_to_type(row))
        
        return seasons
    
    @strawberry.field
    async def get_crop_season_history(
        self,
        info: strawberry.Info[GraphQLContext],
        config_id: str
    ) -> List[dict]:
        """Get change history for a crop season configuration"""
        db = Database()
        history = []
        
        async with db.get_connection() as conn:
            query = """
                SELECT 
                    h.*,
                    c.season_name
                FROM ros_gis.crop_season_history h
                JOIN ros_gis.crop_season_config c ON c.config_id = h.config_id
                WHERE h.config_id = $1
                ORDER BY h.changed_at DESC
            """
            
            results = await conn.fetch(query, config_id)
            
            for row in results:
                history.append({
                    "history_id": str(row['history_id']),
                    "action": row['action'],
                    "changed_fields": row['changed_fields'],
                    "changed_by": row['changed_by'],
                    "changed_at": row['changed_at'],
                    "season_name": row['season_name']
                })
        
        return history
    
    def _map_to_type(self, row) -> CropSeasonConfigType:
        """Map database row to GraphQL type"""
        return CropSeasonConfigType(
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
            map_color_scheme=row['map_color_scheme'],
            show_irrigation_channels=row['show_irrigation_channels'],
            show_delivery_gates=row['show_delivery_gates'],
            weather_data_source=row['weather_data_source'],
            rainfall_adjustment_enabled=row['rainfall_adjustment_enabled'],
            awd_integration_enabled=row['awd_integration_enabled'],
            created_by=row['created_by'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            is_active=row['is_active']
        )
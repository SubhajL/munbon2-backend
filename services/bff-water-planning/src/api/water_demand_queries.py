import strawberry
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
import asyncio
from sqlalchemy import select, and_, func, text

from schemas.time_based_demand import (
    DailyDemandType, AccumulatedDemandType, DemandComparisonType,
    SeasonalDemandSummaryType, MonthlyDemandType, SpatialDemandType,
    DemandTimeSeriesType, TimePeriodEnum, CalculationMethodEnum
)
from schemas.crop_season import CropSeasonConfigType, CropSeasonConfigInput, CropSeasonInitResult
from ..context import GraphQLContext
from core import get_logger
from database import Database

logger = get_logger(__name__)


@strawberry.type
class WaterDemandQueries:
    """Queries for time-based water demand data"""
    
    @strawberry.field
    async def get_demands_by_time_period(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str,
        period: TimePeriodEnum,
        start_date: date,
        end_date: Optional[date] = None,
        method: Optional[CalculationMethodEnum] = None
    ) -> List[DailyDemandType]:
        """
        Get water demands for a section by time period
        
        Args:
            section_id: Section identifier
            period: Time period (daily, weekly, monthly, seasonal)
            start_date: Start date
            end_date: End date (optional, defaults based on period)
            method: Calculation method filter (ros, rid_ms, combined)
        """
        db = Database()
        
        # Calculate end_date if not provided
        if not end_date:
            if period == TimePeriodEnum.DAILY:
                end_date = start_date
            elif period == TimePeriodEnum.WEEKLY:
                end_date = start_date + timedelta(days=6)
            elif period == TimePeriodEnum.MONTHLY:
                # Last day of the month
                next_month = start_date.replace(day=28) + timedelta(days=4)
                end_date = next_month - timedelta(days=next_month.day)
            else:  # seasonal
                end_date = start_date + timedelta(days=365)
        
        demands = []
        
        async with db.get_connection() as conn:
            query = """
                SELECT 
                    dd.date,
                    dd.plot_id,
                    dd.section_id,
                    p.zone,
                    dd.ros_demand_m3,
                    dd.aquacrop_demand_m3 as rid_ms_demand_m3,
                    dd.combined_demand_m3,
                    dd.selected_method,
                    p.crop_type,
                    dd.growth_stage,
                    p.area_rai,
                    dd.stress_level,
                    -- Water level adjustment fields
                    dd.original_demand_m3,
                    dd.adjusted_demand_m3,
                    dd.water_level_m,
                    dd.adjustment_factor,
                    dd.adjustment_method,
                    dd.water_level_data_quality
                FROM ros_gis.daily_demands dd
                JOIN ros_gis.plots p ON p.plot_id = dd.plot_id
                WHERE dd.section_id = $1
                    AND dd.date >= $2
                    AND dd.date <= $3
            """
            
            # Add method filter if specified
            if method:
                if method == CalculationMethodEnum.ROS:
                    query += " AND dd.selected_method = 'ros'"
                elif method == CalculationMethodEnum.RID_MS:
                    query += " AND dd.selected_method IN ('aquacrop', 'rid_ms')"
            
            query += " ORDER BY dd.date, dd.plot_id"
            
            result = await conn.fetch(query, section_id, start_date, end_date)
            
            for row in result:
                demands.append(DailyDemandType(
                    date=row['date'],
                    plot_id=row['plot_id'],
                    section_id=row['section_id'],
                    zone=row['zone'],
                    ros_demand_m3=float(row['ros_demand_m3'] or 0),
                    rid_ms_demand_m3=float(row['rid_ms_demand_m3'] or 0),
                    awd_demand_m3=float(row['awd_demand_m3'] or 0),
                    combined_demand_m3=float(row['combined_demand_m3'] or 0),
                    selected_method=row['selected_method'] or 'ros',
                    crop_type=row['crop_type'],
                    growth_stage=row['growth_stage'],
                    area_rai=float(row['area_rai'] or 0),
                    stress_level=row['stress_level'],
                    # Water level adjustment fields
                    original_demand_m3=float(row['original_demand_m3']) if row['original_demand_m3'] else None,
                    adjusted_demand_m3=float(row['adjusted_demand_m3']) if row['adjusted_demand_m3'] else None,
                    water_level_m=float(row['water_level_m']) if row['water_level_m'] else None,
                    adjustment_factor=float(row['adjustment_factor'] or 1.0),
                    adjustment_method=row['adjustment_method'],
                    water_level_data_quality=float(row['water_level_data_quality']) if row['water_level_data_quality'] else None
                ))
        
        return demands
    
    @strawberry.field
    async def get_accumulated_demands(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str,
        control_interval: str,
        start_date: Optional[date] = None,
        limit: int = 10
    ) -> List[AccumulatedDemandType]:
        """
        Get accumulated water demands for a section
        
        Args:
            section_id: Section identifier
            control_interval: Accumulation interval (weekly, biweekly, monthly)
            start_date: Optional start date filter
            limit: Maximum number of records
        """
        db = Database()
        accumulated = []
        
        async with db.get_connection() as conn:
            query = """
                SELECT 
                    ad.*,
                    -- Calculate method breakdowns from daily demands
                    COALESCE(SUM(dd.ros_demand_m3), 0) as total_ros_m3,
                    COALESCE(SUM(dd.aquacrop_demand_m3), 0) as total_rid_ms_m3
                FROM ros_gis.accumulated_demands ad
                LEFT JOIN ros_gis.daily_demands dd ON 
                    dd.section_id = ad.section_id AND
                    dd.date >= ad.start_date AND
                    dd.date <= ad.end_date
                WHERE ad.section_id = $1
                    AND ad.control_interval = $2
            """
            
            params = [section_id, control_interval]
            
            if start_date:
                query += " AND ad.start_date >= $3"
                params.append(start_date)
            
            query += """
                GROUP BY ad.accumulation_id
                ORDER BY ad.start_date DESC
                LIMIT ${}
            """.format(len(params) + 1)
            
            params.append(limit)
            
            result = await conn.fetch(query, *params)
            
            for row in result:
                accumulated.append(AccumulatedDemandType(
                    section_id=row['section_id'],
                    control_interval=row['control_interval'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    total_demand_m3=float(row['total_demand_m3']),
                    plot_count=row['plot_count'],
                    avg_daily_demand_m3=float(row['avg_daily_demand_m3'] or 0),
                    peak_daily_demand_m3=float(row['peak_daily_demand_m3'] or 0),
                    total_ros_m3=float(row['total_ros_m3']),
                    total_rid_ms_m3=float(row['total_rid_ms_m3']),
                    delivery_gate=row['delivery_gate'],
                    irrigation_channel=row['irrigation_channel'],
                    schedule_id=row['schedule_id']
                ))
        
        return accumulated
    
    @strawberry.field
    async def compare_demand_methods(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str,
        start_date: date,
        end_date: date
    ) -> DemandComparisonType:
        """
        Compare ROS vs RID-MS calculation methods for a section
        
        Args:
            section_id: Section identifier
            start_date: Comparison period start
            end_date: Comparison period end
        """
        db = Database()
        
        async with db.get_connection() as conn:
            query = """
                SELECT 
                    COUNT(DISTINCT plot_id) as plot_count,
                    -- ROS metrics
                    SUM(ros_demand_m3) as ros_total,
                    AVG(ros_demand_m3) as ros_avg,
                    MAX(ros_demand_m3) as ros_peak,
                    -- RID-MS metrics
                    SUM(aquacrop_demand_m3) as rid_ms_total,
                    AVG(aquacrop_demand_m3) as rid_ms_avg,
                    MAX(aquacrop_demand_m3) as rid_ms_peak,
                    -- Combined metrics
                    AVG(combined_demand_m3) as combined_avg
                FROM ros_gis.daily_demands
                WHERE section_id = $1
                    AND date >= $2
                    AND date <= $3
            """
            
            result = await conn.fetchrow(query, section_id, start_date, end_date)
            
            if not result or result['plot_count'] == 0:
                # Return empty comparison
                return DemandComparisonType(
                    section_id=section_id,
                    period="custom",
                    start_date=start_date,
                    end_date=end_date,
                    ros_total_m3=0,
                    ros_daily_avg_m3=0,
                    ros_peak_m3=0,
                    rid_ms_total_m3=0,
                    rid_ms_daily_avg_m3=0,
                    rid_ms_peak_m3=0,
                    difference_m3=0,
                    difference_percent=0,
                    recommended_method="ros",
                    recommendation_reason="No data available"
                )
            
            ros_total = float(result['ros_total'] or 0)
            rid_ms_total = float(result['rid_ms_total'] or 0)
            
            # Calculate difference
            difference = rid_ms_total - ros_total
            difference_percent = (difference / ros_total * 100) if ros_total > 0 else 0
            
            # Determine recommendation
            if rid_ms_total > 0 and abs(difference_percent) < 10:
                recommended = "combined"
                reason = "Both methods show similar results (within 10%)"
            elif rid_ms_total > ros_total * 1.2:
                recommended = "rid_ms"
                reason = f"RID-MS shows {difference_percent:.1f}% higher demand, likely more accurate with field data"
            elif ros_total > rid_ms_total * 1.2:
                recommended = "ros"
                reason = f"ROS shows {abs(difference_percent):.1f}% higher demand, RID-MS may have incomplete data"
            else:
                recommended = "combined"
                reason = "Consider using average of both methods"
            
            return DemandComparisonType(
                section_id=section_id,
                period=f"{(end_date - start_date).days} days",
                start_date=start_date,
                end_date=end_date,
                ros_total_m3=ros_total,
                ros_daily_avg_m3=float(result['ros_avg'] or 0),
                ros_peak_m3=float(result['ros_peak'] or 0),
                rid_ms_total_m3=rid_ms_total,
                rid_ms_daily_avg_m3=float(result['rid_ms_avg'] or 0),
                rid_ms_peak_m3=float(result['rid_ms_peak'] or 0),
                difference_m3=difference,
                difference_percent=difference_percent,
                recommended_method=recommended,
                recommendation_reason=reason
            )
    
    @strawberry.field
    async def get_seasonal_demand_summary(
        self,
        info: strawberry.Info[GraphQLContext],
        season_config_id: Optional[str] = None
    ) -> Optional[SeasonalDemandSummaryType]:
        """
        Get seasonal water demand summary
        
        Args:
            season_config_id: Optional season config ID (defaults to active season)
        """
        db = Database()
        
        async with db.get_connection() as conn:
            # Get season config
            if season_config_id:
                config_query = "SELECT * FROM ros_gis.crop_season_config WHERE config_id = $1"
                config = await conn.fetchrow(config_query, season_config_id)
            else:
                config_query = "SELECT * FROM ros_gis.v_active_crop_season"
                config = await conn.fetchrow(config_query)
            
            if not config:
                return None
            
            # Get seasonal totals
            totals_query = """
                SELECT 
                    COUNT(DISTINCT dd.plot_id) as total_plots,
                    SUM(DISTINCT p.area_rai) as total_area,
                    SUM(dd.combined_demand_m3) as total_demand,
                    SUM(dd.ros_demand_m3) as total_ros,
                    SUM(dd.aquacrop_demand_m3) as total_rid_ms
                FROM ros_gis.daily_demands dd
                JOIN ros_gis.plots p ON p.plot_id = dd.plot_id
                WHERE dd.date >= $1 AND dd.date <= $2
            """
            
            totals = await conn.fetchrow(
                totals_query, 
                config['start_date'], 
                config['end_date']
            )
            
            # Get monthly breakdown
            monthly_query = """
                SELECT 
                    DATE_TRUNC('month', dd.date) as month,
                    SUM(dd.combined_demand_m3) as total_demand,
                    SUM(dd.ros_demand_m3) as ros_demand,
                    SUM(dd.aquacrop_demand_m3) as rid_ms_demand,
                    COUNT(DISTINCT dd.plot_id) as plot_count,
                    AVG(dd.combined_demand_m3) as avg_daily
                FROM ros_gis.daily_demands dd
                WHERE dd.date >= $1 AND dd.date <= $2
                GROUP BY DATE_TRUNC('month', dd.date)
                ORDER BY month
            """
            
            monthly_result = await conn.fetch(
                monthly_query,
                config['start_date'],
                config['end_date']
            )
            
            monthly_demands = []
            peak_month = None
            peak_demand = 0
            
            for row in monthly_result:
                month_demand = MonthlyDemandType(
                    month=row['month'].strftime('%Y-%m'),
                    total_demand_m3=float(row['total_demand'] or 0),
                    ros_demand_m3=float(row['ros_demand'] or 0),
                    rid_ms_demand_m3=float(row['rid_ms_demand'] or 0),
                    plot_count=row['plot_count'],
                    avg_daily_m3=float(row['avg_daily'] or 0)
                )
                monthly_demands.append(month_demand)
                
                if month_demand.total_demand_m3 > peak_demand:
                    peak_demand = month_demand.total_demand_m3
                    peak_month = month_demand.month
            
            total_area = float(totals['total_area'] or 1)
            total_demand = float(totals['total_demand'] or 0)
            
            return SeasonalDemandSummaryType(
                season_config_id=str(config['config_id']),
                season_name=config['season_name'],
                total_area_rai=total_area,
                total_plots=totals['total_plots'] or 0,
                total_demand_m3=total_demand,
                total_ros_m3=float(totals['total_ros'] or 0),
                total_rid_ms_m3=float(totals['total_rid_ms'] or 0),
                monthly_demands=monthly_demands,
                peak_month=peak_month or "",
                peak_demand_m3=peak_demand,
                avg_demand_per_rai=total_demand / total_area if total_area > 0 else 0,
                water_use_efficiency=0.85  # Would be calculated from actual vs allocated
            )
    
    @strawberry.field
    async def get_spatial_demands(
        self,
        info: strawberry.Info[GraphQLContext],
        bbox: Optional[List[float]] = None,
        zoom_level: int = 10,
        feature_type: str = "section",  # 'section' or 'zone'
        date: Optional[date] = None
    ) -> List[SpatialDemandType]:
        """
        Get spatial water demand data for map visualization
        
        Args:
            bbox: Bounding box [minLon, minLat, maxLon, maxLat]
            zoom_level: Map zoom level for aggregation
            feature_type: Aggregate by section or zone
            date: Date for demands (defaults to today)
        """
        db = Database()
        spatial_demands = []
        
        if not date:
            date = datetime.now().date()
        
        async with db.get_connection() as conn:
            if feature_type == "zone":
                # Aggregate by zone
                query = """
                    SELECT 
                        z.zone_id::text as feature_id,
                        'zone' as feature_type,
                        ST_AsGeoJSON(z.geometry)::json as geometry,
                        COALESCE(SUM(dd.combined_demand_m3), 0) as current_demand,
                        COALESCE(SUM(dd.ros_demand_m3), 0) as ros_demand,
                        COALESCE(SUM(dd.aquacrop_demand_m3), 0) as rid_ms_demand,
                        SUM(DISTINCT s.area_rai) as area_rai,
                        COUNT(DISTINCT p.crop_type) as crop_diversity,
                        AVG(d.priority_score) as priority_score,
                        z.zone_name as label
                    FROM ros_gis.zones z
                    LEFT JOIN ros_gis.sections s ON s.zone = z.zone_id
                    LEFT JOIN ros_gis.plots p ON p.section_id = s.section_id
                    LEFT JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id AND dd.date = $1
                    LEFT JOIN ros_gis.demands d ON d.section_id = s.section_id
                """
                
                if bbox:
                    query += """
                        WHERE ST_Intersects(
                            z.geometry, 
                            ST_MakeEnvelope($2, $3, $4, $5, 4326)
                        )
                    """
                
                query += " GROUP BY z.zone_id, z.zone_name, z.geometry"
                
            else:  # section level
                query = """
                    SELECT 
                        s.section_id as feature_id,
                        'section' as feature_type,
                        ST_AsGeoJSON(s.geometry)::json as geometry,
                        COALESCE(SUM(dd.combined_demand_m3), 0) as current_demand,
                        COALESCE(SUM(dd.ros_demand_m3), 0) as ros_demand,
                        COALESCE(SUM(dd.aquacrop_demand_m3), 0) as rid_ms_demand,
                        s.area_rai,
                        COUNT(DISTINCT p.crop_type) as crop_diversity,
                        d.priority_score,
                        s.section_name as label
                    FROM ros_gis.sections s
                    LEFT JOIN ros_gis.plots p ON p.section_id = s.section_id
                    LEFT JOIN ros_gis.daily_demands dd ON dd.plot_id = p.plot_id AND dd.date = $1
                    LEFT JOIN ros_gis.demands d ON d.section_id = s.section_id
                """
                
                if bbox:
                    query += """
                        WHERE ST_Intersects(
                            s.geometry, 
                            ST_MakeEnvelope($2, $3, $4, $5, 4326)
                        )
                    """
                
                query += " GROUP BY s.section_id, s.section_name, s.geometry, s.area_rai, d.priority_score"
            
            # Execute query
            if bbox:
                result = await conn.fetch(query, date, *bbox)
            else:
                result = await conn.fetch(query, date)
            
            # Calculate max demand for color scaling
            max_demand = max([float(row['current_demand']) for row in result], default=1)
            
            for row in result:
                current_demand = float(row['current_demand'] or 0)
                area = float(row['area_rai'] or 1)
                
                spatial_demands.append(SpatialDemandType(
                    feature_id=row['feature_id'],
                    feature_type=row['feature_type'],
                    geometry=row['geometry'],
                    current_demand_m3=current_demand,
                    demand_per_rai=current_demand / area if area > 0 else 0,
                    ros_demand_m3=float(row['ros_demand'] or 0),
                    rid_ms_demand_m3=float(row['rid_ms_demand'] or 0),
                    color_value=current_demand / max_demand if max_demand > 0 else 0,
                    label=row['label'],
                    area_rai=area,
                    crop_diversity=row['crop_diversity'] or 0,
                    priority_score=float(row['priority_score']) if row['priority_score'] else None
                ))
        
        return spatial_demands
    
    @strawberry.field
    async def get_demand_time_series(
        self,
        info: strawberry.Info[GraphQLContext],
        section_id: str,
        start_date: date,
        end_date: date,
        interval: str = "daily"  # daily, weekly
    ) -> DemandTimeSeriesType:
        """
        Get time series data for demand visualization
        
        Args:
            section_id: Section identifier
            start_date: Series start date
            end_date: Series end date
            interval: Data point interval
        """
        db = Database()
        
        async with db.get_connection() as conn:
            if interval == "weekly":
                query = """
                    SELECT 
                        DATE_TRUNC('week', date) as period,
                        SUM(ros_demand_m3) as ros_total,
                        SUM(aquacrop_demand_m3) as rid_ms_total,
                        SUM(combined_demand_m3) as combined_total
                    FROM ros_gis.daily_demands
                    WHERE section_id = $1
                        AND date >= $2
                        AND date <= $3
                    GROUP BY DATE_TRUNC('week', date)
                    ORDER BY period
                """
            else:  # daily
                query = """
                    SELECT 
                        date as period,
                        SUM(ros_demand_m3) as ros_total,
                        SUM(aquacrop_demand_m3) as rid_ms_total,
                        SUM(combined_demand_m3) as combined_total
                    FROM ros_gis.daily_demands
                    WHERE section_id = $1
                        AND date >= $2
                        AND date <= $3
                    GROUP BY date
                    ORDER BY date
                """
            
            result = await conn.fetch(query, section_id, start_date, end_date)
            
            dates = []
            ros_values = []
            rid_ms_values = []
            combined_values = []
            
            for row in result:
                dates.append(row['period'].date() if hasattr(row['period'], 'date') else row['period'])
                ros_values.append(float(row['ros_total'] or 0))
                rid_ms_values.append(float(row['rid_ms_total'] or 0))
                combined_values.append(float(row['combined_total'] or 0))
            
            # Calculate statistics
            if combined_values:
                avg_demand = sum(combined_values) / len(combined_values)
                variance = sum((x - avg_demand) ** 2 for x in combined_values) / len(combined_values)
                std_dev = variance ** 0.5
                
                # Determine trend
                if len(combined_values) > 1:
                    first_half_avg = sum(combined_values[:len(combined_values)//2]) / (len(combined_values)//2)
                    second_half_avg = sum(combined_values[len(combined_values)//2:]) / (len(combined_values) - len(combined_values)//2)
                    
                    if second_half_avg > first_half_avg * 1.1:
                        trend = "increasing"
                    elif second_half_avg < first_half_avg * 0.9:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                else:
                    trend = "stable"
            else:
                avg_demand = 0
                std_dev = 0
                trend = "no_data"
            
            return DemandTimeSeriesType(
                section_id=section_id,
                dates=dates,
                ros_values=ros_values,
                rid_ms_values=rid_ms_values,
                combined_values=combined_values,
                trend=trend,
                avg_demand=avg_demand,
                std_deviation=std_dev
            )
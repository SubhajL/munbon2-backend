"""
Query Optimizer Service
Implements database query optimization strategies
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

from sqlalchemy import select, and_, or_, func, Index
from sqlalchemy.orm import selectinload, joinedload, defer
from sqlalchemy.sql import Select
import json

from core import get_logger
from config import settings
from db import DatabaseManager
from db.models import Section, Demand, SectionPerformance, GateMapping
from services.cache_manager import get_cache_manager, cached

logger = get_logger(__name__)


class QueryOptimizer:
    """Optimizes database queries for performance"""
    
    def __init__(self):
        self.logger = logger.bind(service="query_optimizer")
        self.db = DatabaseManager()
        self.cache = None
        self._query_stats = defaultdict(lambda: {"count": 0, "total_time": 0})
    
    async def initialize(self) -> None:
        """Initialize query optimizer"""
        self.cache = await get_cache_manager()
        
        # Create optimized indexes if not exist
        await self._ensure_indexes()
    
    async def _ensure_indexes(self) -> None:
        """Ensure performance indexes exist"""
        try:
            # These would normally be in migrations, but we ensure they exist
            index_definitions = [
                # Demands indexes
                "CREATE INDEX IF NOT EXISTS idx_demands_section_week ON ros_gis.demands(section_id, calendar_week, calendar_year)",
                "CREATE INDEX IF NOT EXISTS idx_demands_zone_week ON ros_gis.demands(zone, calendar_week, calendar_year)",
                "CREATE INDEX IF NOT EXISTS idx_demands_created ON ros_gis.demands(created_at DESC)",
                
                # Section performance indexes
                "CREATE INDEX IF NOT EXISTS idx_performance_section_date ON ros_gis.section_performance(section_id, date DESC)",
                "CREATE INDEX IF NOT EXISTS idx_performance_efficiency ON ros_gis.section_performance(efficiency_percent)",
                
                # Gate mappings indexes
                "CREATE INDEX IF NOT EXISTS idx_gate_mappings_gate ON ros_gis.gate_mappings(gate_id)",
                "CREATE INDEX IF NOT EXISTS idx_gate_mappings_section ON ros_gis.gate_mappings(section_id)",
                
                # Spatial indexes
                "CREATE INDEX IF NOT EXISTS idx_sections_geometry ON ros_gis.sections USING GIST(geometry)",
                "CREATE INDEX IF NOT EXISTS idx_sections_zone_crop ON ros_gis.sections(zone, crop_type)"
            ]
            
            async with self.db.get_connection() as conn:
                for index_sql in index_definitions:
                    await conn.execute(index_sql)
                    
            self.logger.info("Database indexes verified")
            
        except Exception as e:
            self.logger.error("Failed to ensure indexes", error=str(e))
    
    @cached("section_batch", ttl=3600)
    async def get_sections_batch(
        self,
        section_ids: List[str],
        include_geometry: bool = False
    ) -> Dict[str, Dict]:
        """Get multiple sections in a single optimized query"""
        sections = {}
        
        async with self.db.get_section_repository() as repo:
            # Build optimized query
            query = select(Section).where(Section.section_id.in_(section_ids))
            
            if not include_geometry:
                # Defer loading of geometry column if not needed
                query = query.options(defer(Section.geometry))
            
            result = await repo.session.execute(query)
            rows = result.scalars().all()
            
            for row in rows:
                sections[row.section_id] = {
                    "section_id": row.section_id,
                    "zone": row.zone,
                    "area_hectares": float(row.area_hectares),
                    "area_rai": float(row.area_rai),
                    "crop_type": row.crop_type,
                    "soil_type": row.soil_type,
                    "elevation_m": float(row.elevation_m) if row.elevation_m else None,
                    "delivery_gate": row.delivery_gate,
                    "geometry": row.geometry if include_geometry else None
                }
        
        return sections
    
    async def get_zone_demands_optimized(
        self,
        zone: int,
        week: int,
        year: int
    ) -> List[Dict]:
        """Get all demands for a zone with optimized query"""
        # Check cache first
        cache_key = f"zone_{zone}_w{week}_y{year}"
        cached_result = await self.cache.get("zone_demands", cache_key)
        if cached_result:
            return cached_result
        
        demands = []
        
        async with self.db.get_demand_repository() as repo:
            # Single query with all needed data
            query = (
                select(Demand)
                .where(
                    and_(
                        Demand.zone == zone,
                        Demand.calendar_week == week,
                        Demand.calendar_year == year
                    )
                )
                .order_by(Demand.priority_score.desc())
            )
            
            result = await repo.session.execute(query)
            rows = result.scalars().all()
            
            for row in rows:
                demands.append({
                    "demand_id": row.demand_id,
                    "section_id": row.section_id,
                    "zone": row.zone,
                    "crop_type": row.crop_type,
                    "growth_stage": row.growth_stage,
                    "area_rai": float(row.area_rai),
                    "net_demand_m3": float(row.net_demand_m3),
                    "gross_demand_m3": float(row.gross_demand_m3),
                    "priority_score": float(row.priority_score) if row.priority_score else 0,
                    "stress_level": row.stress_level,
                    "created_at": row.created_at.isoformat()
                })
        
        # Cache the result
        await self.cache.set("zone_demands", cache_key, demands, ttl=1800)
        
        return demands
    
    async def get_performance_metrics_batch(
        self,
        section_ids: List[str],
        days: int = 30
    ) -> Dict[str, List[Dict]]:
        """Get performance metrics for multiple sections efficiently"""
        performance_data = defaultdict(list)
        cutoff_date = datetime.utcnow().date() - timedelta(days=days)
        
        async with self.db.get_section_performance_repository() as repo:
            # Single query for all sections
            query = (
                select(SectionPerformance)
                .where(
                    and_(
                        SectionPerformance.section_id.in_(section_ids),
                        SectionPerformance.date >= cutoff_date
                    )
                )
                .order_by(
                    SectionPerformance.section_id,
                    SectionPerformance.date.desc()
                )
            )
            
            result = await repo.session.execute(query)
            rows = result.scalars().all()
            
            for row in rows:
                performance_data[row.section_id].append({
                    "date": row.date.isoformat(),
                    "allocated_m3": float(row.allocated_m3),
                    "delivered_m3": float(row.delivered_m3),
                    "actual_m3": float(row.actual_m3),
                    "efficiency_percent": float(row.efficiency_percent),
                    "loss_percent": float(row.loss_percent)
                })
        
        return dict(performance_data)
    
    async def get_gate_utilization_optimized(self) -> List[Dict]:
        """Get gate utilization with optimized queries"""
        utilization_data = []
        
        async with self.db.get_connection() as conn:
            # Use raw SQL for complex aggregation
            query = """
                SELECT 
                    gm.gate_id,
                    COUNT(DISTINCT gm.section_id) as section_count,
                    SUM(s.area_rai) as total_area_rai,
                    MAX(gm.max_flow_m3s) as max_capacity,
                    AVG(d.gross_demand_m3) as avg_demand_m3,
                    STRING_AGG(DISTINCT s.crop_type, ', ') as crop_types
                FROM ros_gis.gate_mappings gm
                JOIN ros_gis.sections s ON s.section_id = gm.section_id
                LEFT JOIN ros_gis.demands d ON d.section_id = s.section_id
                    AND d.calendar_week = $1
                    AND d.calendar_year = $2
                GROUP BY gm.gate_id
                ORDER BY total_area_rai DESC
            """
            
            current_week = datetime.now().isocalendar()[1]
            current_year = datetime.now().year
            
            result = await conn.fetch(query, current_week, current_year)
            
            for row in result:
                # Estimate utilization
                avg_demand = row['avg_demand_m3'] or 0
                max_capacity = row['max_capacity'] or 10
                flow_hours = 8  # Assume 8 hours operation
                
                daily_capacity = max_capacity * 3600 * flow_hours
                utilization = (avg_demand / daily_capacity * 100) if daily_capacity > 0 else 0
                
                utilization_data.append({
                    "gate_id": row['gate_id'],
                    "section_count": row['section_count'],
                    "total_area_rai": float(row['total_area_rai']),
                    "max_capacity_m3s": float(max_capacity),
                    "avg_demand_m3": float(avg_demand),
                    "utilization_percent": min(utilization, 100),
                    "crop_types": row['crop_types']
                })
        
        return utilization_data
    
    async def bulk_insert_demands(self, demands: List[Dict]) -> bool:
        """Bulk insert demands with optimization"""
        try:
            async with self.db.get_demand_repository() as repo:
                # Prepare demand objects
                demand_objects = []
                for demand in demands:
                    demand_obj = Demand(
                        section_id=demand['section_id'],
                        zone=demand['zone'],
                        calendar_week=demand['calendar_week'],
                        calendar_year=demand['calendar_year'],
                        crop_type=demand.get('crop_type', 'unknown'),
                        growth_stage=demand.get('growth_stage', 'unknown'),
                        crop_week=demand.get('crop_week', 1),
                        area_rai=demand['area_rai'],
                        net_demand_m3=demand['net_demand_m3'],
                        gross_demand_m3=demand['gross_demand_m3'],
                        moisture_deficit_percent=demand.get('moisture_deficit_percent', 0),
                        stress_level=demand.get('stress_level', 'none'),
                        priority_score=demand.get('priority_score', 0),
                        delivery_gate=demand.get('delivery_gate'),
                        amphoe=demand.get('amphoe'),
                        tambon=demand.get('tambon')
                    )
                    demand_objects.append(demand_obj)
                
                # Bulk insert
                repo.session.add_all(demand_objects)
                await repo.session.commit()
                
                # Invalidate relevant caches
                zones = set(d['zone'] for d in demands)
                for zone in zones:
                    await self.cache.invalidate_zone_cache(zone)
                
                self.logger.info(
                    "Bulk inserted demands",
                    count=len(demands),
                    zones=list(zones)
                )
                
                return True
                
        except Exception as e:
            self.logger.error("Failed to bulk insert demands", error=str(e))
            return False
    
    async def get_spatial_sections_optimized(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        zone: Optional[int] = None,
        crop_type: Optional[str] = None
    ) -> List[Dict]:
        """Get sections with spatial filtering optimized"""
        sections = []
        
        async with self.db.get_connection() as conn:
            # Build spatial query
            conditions = []
            params = []
            param_count = 0
            
            if bbox:
                param_count += 4
                conditions.append(f"""
                    geometry && ST_MakeEnvelope(${param_count-3}, ${param_count-2}, ${param_count-1}, ${param_count}, 4326)
                """)
                params.extend(bbox)
            
            if zone is not None:
                param_count += 1
                conditions.append(f"zone = ${param_count}")
                params.append(zone)
            
            if crop_type:
                param_count += 1
                conditions.append(f"crop_type = ${param_count}")
                params.append(crop_type)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            query = f"""
                SELECT 
                    section_id,
                    zone,
                    area_rai,
                    crop_type,
                    elevation_m,
                    delivery_gate,
                    ST_AsGeoJSON(geometry) as geometry_json,
                    ST_X(ST_Centroid(geometry)) as centroid_lon,
                    ST_Y(ST_Centroid(geometry)) as centroid_lat
                FROM ros_gis.sections
                {where_clause}
                ORDER BY zone, section_id
                LIMIT 1000
            """
            
            result = await conn.fetch(query, *params)
            
            for row in result:
                sections.append({
                    "section_id": row['section_id'],
                    "zone": row['zone'],
                    "area_rai": float(row['area_rai']),
                    "crop_type": row['crop_type'],
                    "elevation_m": float(row['elevation_m']) if row['elevation_m'] else None,
                    "delivery_gate": row['delivery_gate'],
                    "geometry": json.loads(row['geometry_json']) if row['geometry_json'] else None,
                    "centroid": {
                        "lat": float(row['centroid_lat']),
                        "lon": float(row['centroid_lon'])
                    }
                })
        
        return sections
    
    async def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze query performance statistics"""
        async with self.db.get_connection() as conn:
            # Get slow queries
            slow_queries_sql = """
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    max_time
                FROM pg_stat_statements
                WHERE query LIKE '%ros_gis%'
                    AND mean_time > 100  -- Queries taking >100ms on average
                ORDER BY mean_time DESC
                LIMIT 10
            """
            
            try:
                slow_queries = await conn.fetch(slow_queries_sql)
                
                return {
                    "slow_queries": [
                        {
                            "query": row['query'][:100] + "...",
                            "calls": row['calls'],
                            "avg_time_ms": float(row['mean_time']),
                            "max_time_ms": float(row['max_time'])
                        }
                        for row in slow_queries
                    ],
                    "cache_stats": await self.cache.get_cache_stats(),
                    "internal_stats": dict(self._query_stats)
                }
            except:
                # pg_stat_statements might not be enabled
                return {
                    "cache_stats": await self.cache.get_cache_stats(),
                    "internal_stats": dict(self._query_stats)
                }
    
    def track_query_time(self, query_name: str, duration_ms: float) -> None:
        """Track query execution time"""
        self._query_stats[query_name]["count"] += 1
        self._query_stats[query_name]["total_time"] += duration_ms
        self._query_stats[query_name]["avg_time"] = (
            self._query_stats[query_name]["total_time"] / 
            self._query_stats[query_name]["count"]
        )
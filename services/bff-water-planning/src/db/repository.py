"""
Database repository for ROS/GIS Integration Service
Handles all database operations using SQLAlchemy + asyncpg
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_AsGeoJSON, ST_Distance, ST_Within
import json

from .models import Section, Demand, SectionPerformance, GateMapping, GateDemand, WeatherAdjustment
from core import get_logger

logger = get_logger(__name__)


class SectionRepository:
    """Repository for section-related database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_section(self, section_id: str) -> Optional[Dict]:
        """Get section by ID"""
        result = await self.session.execute(
            select(Section, ST_AsGeoJSON(Section.geometry).label('geojson'))
            .where(Section.section_id == section_id)
        )
        row = result.first()
        
        if row:
            section = row[0]
            return {
                'section_id': section.section_id,
                'zone': section.zone,
                'area_hectares': float(section.area_hectares) if section.area_hectares else 0,
                'area_rai': float(section.area_rai) if section.area_rai else 0,
                'crop_type': section.crop_type,
                'soil_type': section.soil_type,
                'elevation_m': float(section.elevation_m) if section.elevation_m else 0,
                'delivery_gate': section.delivery_gate,
                'geometry': json.loads(row[1]) if row[1] else None,
                'created_at': section.created_at,
                'updated_at': section.updated_at
            }
        return None
    
    async def get_sections_by_zone(self, zone: int) -> List[Dict]:
        """Get all sections in a zone"""
        result = await self.session.execute(
            select(Section)
            .where(Section.zone == zone)
            .order_by(Section.section_id)
        )
        sections = result.scalars().all()
        
        return [
            {
                'section_id': s.section_id,
                'zone': s.zone,
                'area_hectares': float(s.area_hectares) if s.area_hectares else 0,
                'area_rai': float(s.area_rai) if s.area_rai else 0,
                'crop_type': s.crop_type,
                'soil_type': s.soil_type,
                'elevation_m': float(s.elevation_m) if s.elevation_m else 0,
                'delivery_gate': s.delivery_gate
            }
            for s in sections
        ]
    
    async def create_section(self, section_data: Dict) -> str:
        """Create a new section"""
        section = Section(**section_data)
        self.session.add(section)
        await self.session.commit()
        return section.section_id
    
    async def update_section(self, section_id: str, updates: Dict) -> bool:
        """Update section data"""
        result = await self.session.execute(
            update(Section)
            .where(Section.section_id == section_id)
            .values(**updates)
        )
        await self.session.commit()
        return result.rowcount > 0


class DemandRepository:
    """Repository for demand-related database operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_demand(self, demand_data: Dict) -> int:
        """Create a new demand"""
        demand = Demand(**demand_data)
        self.session.add(demand)
        await self.session.commit()
        return demand.demand_id
    
    async def get_demands_by_week(self, week: str) -> List[Dict]:
        """Get all demands for a specific week"""
        result = await self.session.execute(
            select(Demand)
            .where(Demand.week == week)
            .order_by(Demand.priority.desc())
        )
        demands = result.scalars().all()
        
        return [self._demand_to_dict(d) for d in demands]
    
    async def get_section_demands(self, section_id: str, weeks: int = 4) -> List[Dict]:
        """Get demands for a section over multiple weeks"""
        # Calculate week range
        current_week = datetime.now().strftime('%Y-W%U')
        
        result = await self.session.execute(
            select(Demand)
            .where(
                and_(
                    Demand.section_id == section_id,
                    Demand.week >= current_week
                )
            )
            .order_by(Demand.week)
            .limit(weeks)
        )
        demands = result.scalars().all()
        
        return [self._demand_to_dict(d) for d in demands]
    
    async def update_demand_priority(self, demand_id: int, priority: float, priority_class: str) -> bool:
        """Update demand priority"""
        result = await self.session.execute(
            update(Demand)
            .where(Demand.demand_id == demand_id)
            .values(priority=priority, priority_class=priority_class)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    def _demand_to_dict(self, demand: Demand) -> Dict:
        """Convert demand model to dictionary"""
        return {
            'demand_id': demand.demand_id,
            'section_id': demand.section_id,
            'week': demand.week,
            'volume_m3': float(demand.volume_m3) if demand.volume_m3 else 0,
            'priority': float(demand.priority) if demand.priority else 0,
            'priority_class': demand.priority_class,
            'crop_type': demand.crop_type,
            'growth_stage': demand.growth_stage,
            'moisture_deficit_percent': float(demand.moisture_deficit_percent) if demand.moisture_deficit_percent else None,
            'stress_level': demand.stress_level,
            'delivery_window_start': demand.delivery_window_start,
            'delivery_window_end': demand.delivery_window_end,
            'weather_adjustment_factor': float(demand.weather_adjustment_factor) if demand.weather_adjustment_factor else 1.0
        }


class PerformanceRepository:
    """Repository for performance tracking"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def record_performance(self, performance_data: Dict) -> int:
        """Record section performance"""
        performance = SectionPerformance(**performance_data)
        self.session.add(performance)
        await self.session.commit()
        return performance.performance_id
    
    async def get_section_performance(self, section_id: str, weeks: int = 4) -> List[Dict]:
        """Get performance history for a section"""
        result = await self.session.execute(
            select(SectionPerformance)
            .where(SectionPerformance.section_id == section_id)
            .order_by(SectionPerformance.week.desc())
            .limit(weeks)
        )
        performances = result.scalars().all()
        
        return [
            {
                'week': p.week,
                'planned_m3': float(p.planned_m3) if p.planned_m3 else 0,
                'delivered_m3': float(p.delivered_m3) if p.delivered_m3 else 0,
                'efficiency': float(p.efficiency) if p.efficiency else 0,
                'deficit_m3': float(p.deficit_m3) if p.deficit_m3 else 0,
                'delivery_count': p.delivery_count,
                'average_flow_m3s': float(p.average_flow_m3s) if p.average_flow_m3s else None
            }
            for p in performances
        ]
    
    async def get_weekly_summary(self, week: str) -> Dict:
        """Get aggregated performance for a week"""
        result = await self.session.execute(
            select(
                func.count(SectionPerformance.performance_id).label('total_sections'),
                func.sum(SectionPerformance.planned_m3).label('total_planned'),
                func.sum(SectionPerformance.delivered_m3).label('total_delivered'),
                func.avg(SectionPerformance.efficiency).label('avg_efficiency')
            )
            .where(SectionPerformance.week == week)
        )
        row = result.first()
        
        if row:
            return {
                'week': week,
                'total_sections': row.total_sections or 0,
                'total_planned_m3': float(row.total_planned) if row.total_planned else 0,
                'total_delivered_m3': float(row.total_delivered) if row.total_delivered else 0,
                'average_efficiency': float(row.avg_efficiency) if row.avg_efficiency else 0,
                'total_deficit_m3': float(row.total_planned - row.total_delivered) if row.total_planned and row.total_delivered else 0
            }
        
        return {
            'week': week,
            'total_sections': 0,
            'total_planned_m3': 0,
            'total_delivered_m3': 0,
            'average_efficiency': 0,
            'total_deficit_m3': 0
        }


class GateMappingRepository:
    """Repository for gate mapping operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_section_mapping(self, section_id: str) -> Optional[Dict]:
        """Get gate mapping for a section"""
        result = await self.session.execute(
            select(GateMapping)
            .where(
                and_(
                    GateMapping.section_id == section_id,
                    GateMapping.is_primary == True
                )
            )
        )
        mapping = result.scalar_one_or_none()
        
        if mapping:
            return {
                'section_id': mapping.section_id,
                'gate_id': mapping.gate_id,
                'distance_km': float(mapping.distance_km) if mapping.distance_km else 0,
                'travel_time_hours': float(mapping.travel_time_hours) if mapping.travel_time_hours else 0
            }
        return None
    
    async def get_gate_sections(self, gate_id: str) -> List[str]:
        """Get all sections served by a gate"""
        result = await self.session.execute(
            select(GateMapping.section_id)
            .where(GateMapping.gate_id == gate_id)
        )
        return [row[0] for row in result.all()]
    
    async def create_mapping(self, mapping_data: Dict) -> int:
        """Create a new gate mapping"""
        mapping = GateMapping(**mapping_data)
        self.session.add(mapping)
        await self.session.commit()
        return mapping.mapping_id
    
    async def update_mapping(self, section_id: str, new_gate_id: str) -> bool:
        """Update section's primary gate"""
        # Set current primary to false
        await self.session.execute(
            update(GateMapping)
            .where(
                and_(
                    GateMapping.section_id == section_id,
                    GateMapping.is_primary == True
                )
            )
            .values(is_primary=False)
        )
        
        # Check if new mapping exists
        result = await self.session.execute(
            select(GateMapping)
            .where(
                and_(
                    GateMapping.section_id == section_id,
                    GateMapping.gate_id == new_gate_id
                )
            )
        )
        mapping = result.scalar_one_or_none()
        
        if mapping:
            # Update existing to primary
            await self.session.execute(
                update(GateMapping)
                .where(GateMapping.mapping_id == mapping.mapping_id)
                .values(is_primary=True)
            )
        else:
            # Create new mapping
            new_mapping = GateMapping(
                section_id=section_id,
                gate_id=new_gate_id,
                is_primary=True
            )
            self.session.add(new_mapping)
        
        await self.session.commit()
        return True


class GateDemandRepository:
    """Repository for aggregated gate demands"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_gate_demand(self, gate_demand_data: Dict) -> int:
        """Save aggregated gate demand"""
        # Check if already exists
        result = await self.session.execute(
            select(GateDemand)
            .where(
                and_(
                    GateDemand.gate_id == gate_demand_data['gate_id'],
                    GateDemand.week == gate_demand_data['week']
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            await self.session.execute(
                update(GateDemand)
                .where(GateDemand.gate_demand_id == existing.gate_demand_id)
                .values(**gate_demand_data)
            )
            await self.session.commit()
            return existing.gate_demand_id
        else:
            # Create new
            gate_demand = GateDemand(**gate_demand_data)
            self.session.add(gate_demand)
            await self.session.commit()
            return gate_demand.gate_demand_id
    
    async def get_gate_demands_by_week(self, week: str) -> List[Dict]:
        """Get all gate demands for a week"""
        result = await self.session.execute(
            select(GateDemand)
            .where(GateDemand.week == week)
            .order_by(GateDemand.priority_weighted.desc())
        )
        demands = result.scalars().all()
        
        return [
            {
                'gate_id': d.gate_id,
                'week': d.week,
                'total_volume_m3': float(d.total_volume_m3) if d.total_volume_m3 else 0,
                'section_count': d.section_count,
                'priority_weighted': float(d.priority_weighted) if d.priority_weighted else 0,
                'schedule_id': d.schedule_id,
                'status': d.status
            }
            for d in demands
        ]
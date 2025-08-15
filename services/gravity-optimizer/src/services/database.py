"""Database connection and operations for Gravity Optimizer"""

import asyncio
import asyncpg
from typing import List, Dict, Optional
import logging
from ..config.settings import settings
from ..models.channel import NetworkTopology, HydraulicNode, Channel, Gate
import json

logger = logging.getLogger(__name__)


class DatabaseService:
    """Handle database operations for gravity optimizer"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool created")
            
            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"Connected to PostgreSQL: {version}")
                
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def load_network_topology(self) -> NetworkTopology:
        """Load network topology from database"""
        async with self.pool.acquire() as conn:
            # Load nodes
            nodes_query = """
                SELECT node_id, name, elevation, 
                       ST_X(location) as lon, ST_Y(location) as lat,
                       water_demand, priority
                FROM gravity.hydraulic_nodes
                ORDER BY node_id
            """
            nodes_rows = await conn.fetch(nodes_query)
            
            nodes = []
            for row in nodes_rows:
                node = HydraulicNode(
                    node_id=row['node_id'],
                    name=row['name'],
                    elevation=float(row['elevation']),
                    connected_channels=[],  # Will populate later
                    gates=[],  # Will populate later
                    water_demand=float(row['water_demand']),
                    priority=row['priority']
                )
                nodes.append(node)
            
            # Load channels
            channels_query = """
                SELECT c.channel_id, c.name, c.channel_type, c.upstream_gate_id,
                       c.total_length, c.avg_bed_slope, c.capacity,
                       ST_AsGeoJSON(c.geometry) as geometry
                FROM gravity.channels c
                ORDER BY c.channel_id
            """
            channel_rows = await conn.fetch(channels_query)
            
            channels = []
            for row in channel_rows:
                # Load sections for this channel
                sections_query = """
                    SELECT section_id, start_elevation, end_elevation,
                           length, bed_width, side_slope, manning_n, max_depth,
                           ST_AsGeoJSON(geometry) as geometry
                    FROM gravity.channel_sections
                    WHERE channel_id = $1
                    ORDER BY section_order
                """
                section_rows = await conn.fetch(sections_query, row['channel_id'])
                
                sections = []
                for sec_row in section_rows:
                    geom = json.loads(sec_row['geometry'])
                    coords = geom['coordinates']
                    
                    section = {
                        'section_id': sec_row['section_id'],
                        'channel_id': row['channel_id'],
                        'start_point': {'lat': coords[0][1], 'lon': coords[0][0]},
                        'end_point': {'lat': coords[-1][1], 'lon': coords[-1][0]},
                        'start_elevation': float(sec_row['start_elevation']),
                        'end_elevation': float(sec_row['end_elevation']),
                        'length': float(sec_row['length']),
                        'bed_width': float(sec_row['bed_width']),
                        'side_slope': float(sec_row['side_slope']),
                        'manning_n': float(sec_row['manning_n']),
                        'max_depth': float(sec_row['max_depth'])
                    }
                    sections.append(section)
                
                # Get downstream gates
                gates_query = """
                    SELECT gate_id FROM gravity.gates
                    WHERE upstream_channel_id = $1
                """
                gate_rows = await conn.fetch(gates_query, row['channel_id'])
                downstream_gates = [g['gate_id'] for g in gate_rows]
                
                channel = {
                    'channel_id': row['channel_id'],
                    'name': row['name'],
                    'channel_type': row['channel_type'],
                    'sections': sections,
                    'upstream_gate_id': row['upstream_gate_id'],
                    'downstream_gates': downstream_gates,
                    'total_length': float(row['total_length']),
                    'avg_bed_slope': float(row['avg_bed_slope']),
                    'capacity': float(row['capacity'])
                }
                channels.append(channel)
            
            # Load gates
            gates_query = """
                SELECT gate_id, gate_type, 
                       ST_X(location) as lon, ST_Y(location) as lat,
                       elevation, max_opening, current_opening,
                       upstream_channel_id, downstream_channel_id
                FROM gravity.gates
                ORDER BY gate_id
            """
            gate_rows = await conn.fetch(gates_query)
            
            gates = []
            for row in gate_rows:
                gate = {
                    'gate_id': row['gate_id'],
                    'gate_type': row['gate_type'],
                    'location': {'lat': row['lat'], 'lon': row['lon']},
                    'elevation': float(row['elevation']),
                    'max_opening': float(row['max_opening']),
                    'current_opening': float(row['current_opening']),
                    'upstream_channel_id': row['upstream_channel_id'],
                    'downstream_channel_id': row['downstream_channel_id']
                }
                gates.append(gate)
            
            # Get source node
            source_node = await conn.fetchval(
                "SELECT node_id FROM gravity.hydraulic_nodes WHERE name LIKE '%Source%' LIMIT 1"
            )
            
            return {
                'nodes': nodes,
                'channels': channels,
                'gates': gates,
                'source_node_id': source_node or 'source'
            }
    
    async def save_optimization_result(self, result: Dict) -> str:
        """Save optimization result to database"""
        async with self.pool.acquire() as conn:
            query = """
                INSERT INTO gravity.optimization_results 
                (request_id, objective, source_water_level, 
                 total_delivery_time, overall_efficiency, result_data)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING result_id
            """
            
            result_id = await conn.fetchval(
                query,
                result['request_id'],
                result['objective'],
                result.get('source_water_level'),
                result['total_delivery_time'],
                result['overall_efficiency'],
                json.dumps(result)
            )
            
            # Save gate settings history
            if 'flow_splits' in result and 'gate_settings' in result['flow_splits']:
                for gate_setting in result['flow_splits']['gate_settings']:
                    await conn.execute("""
                        INSERT INTO gravity.gate_settings_history
                        (gate_id, opening_ratio, flow_rate, upstream_head, 
                         downstream_head, optimization_id)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    gate_setting['gate_id'],
                    gate_setting['opening_ratio'],
                    gate_setting['flow_rate'],
                    gate_setting['upstream_head'],
                    gate_setting['downstream_head'],
                    result_id
                    )
            
            return str(result_id)
    
    async def get_optimization_history(self, limit: int = 10) -> List[Dict]:
        """Get recent optimization results"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT request_id, objective, source_water_level,
                       total_delivery_time, overall_efficiency, created_at
                FROM gravity.optimization_results
                ORDER BY created_at DESC
                LIMIT $1
            """
            rows = await conn.fetch(query, limit)
            
            return [
                {
                    'request_id': row['request_id'],
                    'objective': row['objective'],
                    'source_water_level': float(row['source_water_level']) if row['source_water_level'] else None,
                    'total_delivery_time': float(row['total_delivery_time']),
                    'overall_efficiency': float(row['overall_efficiency']),
                    'created_at': row['created_at'].isoformat()
                }
                for row in rows
            ]
    
    async def update_gate_position(self, gate_id: str, opening_ratio: float) -> bool:
        """Update current gate position"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE gravity.gates
                SET current_opening = max_opening * $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE gate_id = $1
            """, gate_id, opening_ratio)
            
            return result.split()[-1] == '1'
    
    async def get_zone_info(self, zone_id: str) -> Optional[Dict]:
        """Get zone information including boundary"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT zone_id, name, min_elevation, max_elevation,
                       area_hectares, ST_AsGeoJSON(boundary) as boundary
                FROM gravity.zones
                WHERE zone_id = $1
            """
            row = await conn.fetchrow(query, zone_id)
            
            if row:
                return {
                    'zone_id': row['zone_id'],
                    'name': row['name'],
                    'min_elevation': float(row['min_elevation']),
                    'max_elevation': float(row['max_elevation']),
                    'area_hectares': float(row['area_hectares']) if row['area_hectares'] else None,
                    'boundary': json.loads(row['boundary'])
                }
            return None
    
    async def find_energy_recovery_sites(self, min_power_kw: float = 50) -> List[Dict]:
        """Get potential energy recovery sites from database"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT site_id, location_id, channel_id,
                       ST_X(location) as lon, ST_Y(location) as lat,
                       available_head, avg_flow_rate, potential_power_kw,
                       annual_energy_mwh, feasibility, estimated_cost, payback_years
                FROM gravity.energy_recovery_sites
                WHERE potential_power_kw >= $1
                ORDER BY potential_power_kw DESC
            """
            rows = await conn.fetch(query, min_power_kw)
            
            return [
                {
                    'site_id': str(row['site_id']),
                    'location_id': row['location_id'],
                    'channel_id': row['channel_id'],
                    'location': {'lat': row['lat'], 'lon': row['lon']},
                    'available_head': float(row['available_head']),
                    'avg_flow_rate': float(row['avg_flow_rate']),
                    'potential_power_kw': float(row['potential_power_kw']),
                    'annual_energy_mwh': float(row['annual_energy_mwh']) if row['annual_energy_mwh'] else None,
                    'feasibility': row['feasibility'],
                    'estimated_cost': float(row['estimated_cost']) if row['estimated_cost'] else None,
                    'payback_years': float(row['payback_years']) if row['payback_years'] else None
                }
                for row in rows
            ]


# Singleton instance
db_service = DatabaseService()
"""GIS Service client for spatial data operations"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel
from .base_client import BaseServiceClient

logger = logging.getLogger(__name__)


class ChannelGeometry(BaseModel):
    """Channel geometry from GIS"""
    channel_id: str
    geometry: Dict  # GeoJSON
    length_m: float
    start_elevation: float
    end_elevation: float
    avg_slope: float


class ZoneBoundary(BaseModel):
    """Zone boundary information"""
    zone_id: str
    name: str
    boundary: Dict  # GeoJSON
    area_hectares: float
    centroid: Tuple[float, float]  # lon, lat
    elevation_range: Tuple[float, float]  # min, max


class GateLocation(BaseModel):
    """Gate location information"""
    gate_id: str
    location: Tuple[float, float]  # lon, lat
    elevation: float
    upstream_channel: Optional[str]
    downstream_channel: Optional[str]


class GISClient(BaseServiceClient):
    """Client for GIS Data Service"""
    
    def __init__(self, base_url: Optional[str] = None):
        # Get URL from service registry if not provided
        if not base_url:
            from .service_registry import service_registry
            service_info = asyncio.run(service_registry.discover('gis'))
            base_url = service_info.url if service_info else 'http://localhost:3007'
        
        super().__init__(
            service_name='GIS Service',
            base_url=base_url,
            timeout=60.0  # Longer timeout for spatial operations
        )
    
    async def get_channel_network(self) -> Dict[str, ChannelGeometry]:
        """Get complete channel network geometry"""
        try:
            response = await self.get('/api/v1/gis/channels/network')
            
            channels = {}
            for channel_data in response.get('channels', []):
                channel = ChannelGeometry(**channel_data)
                channels[channel.channel_id] = channel
            
            logger.info(f"Loaded {len(channels)} channels from GIS")
            return channels
            
        except Exception as e:
            logger.error(f"Failed to get channel network: {e}")
            raise
    
    async def get_channel_geometry(self, channel_id: str) -> Optional[ChannelGeometry]:
        """Get geometry for specific channel"""
        try:
            response = await self.get(f'/api/v1/gis/channels/{channel_id}')
            return ChannelGeometry(**response)
            
        except Exception as e:
            logger.error(f"Failed to get channel {channel_id}: {e}")
            return None
    
    async def get_zone_boundaries(self) -> Dict[str, ZoneBoundary]:
        """Get all irrigation zone boundaries"""
        try:
            response = await self.get('/api/v1/gis/zones')
            
            zones = {}
            for zone_data in response.get('zones', []):
                zone = ZoneBoundary(**zone_data)
                zones[zone.zone_id] = zone
            
            logger.info(f"Loaded {len(zones)} zones from GIS")
            return zones
            
        except Exception as e:
            logger.error(f"Failed to get zone boundaries: {e}")
            raise
    
    async def get_zone_by_location(self, lat: float, lon: float) -> Optional[str]:
        """Find which zone contains a given point"""
        try:
            response = await self.get(
                '/api/v1/gis/zones/locate',
                params={'lat': lat, 'lon': lon}
            )
            return response.get('zone_id')
            
        except Exception as e:
            logger.error(f"Failed to locate zone for ({lat}, {lon}): {e}")
            return None
    
    async def get_gates_in_bbox(
        self, 
        min_lon: float, 
        min_lat: float, 
        max_lon: float, 
        max_lat: float
    ) -> List[GateLocation]:
        """Get all gates within bounding box"""
        try:
            response = await self.get(
                '/api/v1/gis/gates/bbox',
                params={
                    'min_lon': min_lon,
                    'min_lat': min_lat,
                    'max_lon': max_lon,
                    'max_lat': max_lat
                }
            )
            
            gates = []
            for gate_data in response.get('gates', []):
                gates.append(GateLocation(**gate_data))
            
            return gates
            
        except Exception as e:
            logger.error(f"Failed to get gates in bbox: {e}")
            return []
    
    async def calculate_channel_profile(
        self, 
        channel_id: str, 
        sample_interval: float = 100.0
    ) -> List[Dict]:
        """Get elevation profile along channel"""
        try:
            response = await self.post(
                f'/api/v1/gis/channels/{channel_id}/profile',
                data={'sample_interval': sample_interval}
            )
            
            return response.get('profile', [])
            
        except Exception as e:
            logger.error(f"Failed to get channel profile: {e}")
            return []
    
    async def find_path_to_zone(
        self, 
        zone_id: str, 
        source_node: str = 'source'
    ) -> List[str]:
        """Find channel path from source to zone"""
        try:
            response = await self.get(
                f'/api/v1/gis/routing/path',
                params={
                    'from': source_node,
                    'to': zone_id
                }
            )
            
            return response.get('channel_ids', [])
            
        except Exception as e:
            logger.error(f"Failed to find path to zone {zone_id}: {e}")
            return []
    
    async def get_elevation_at_point(self, lat: float, lon: float) -> Optional[float]:
        """Get elevation at specific point from DEM"""
        try:
            response = await self.get(
                '/api/v1/gis/elevation/point',
                params={'lat': lat, 'lon': lon}
            )
            
            return response.get('elevation')
            
        except Exception as e:
            logger.error(f"Failed to get elevation at ({lat}, {lon}): {e}")
            return None
    
    async def update_gate_status(
        self, 
        gate_id: str, 
        opening_ratio: float,
        flow_rate: Optional[float] = None
    ) -> bool:
        """Update gate status in GIS database"""
        try:
            await self.put(
                f'/api/v1/gis/gates/{gate_id}/status',
                data={
                    'opening_ratio': opening_ratio,
                    'flow_rate': flow_rate,
                    'updated_by': 'gravity-optimizer',
                    'timestamp': datetime.now().isoformat()
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to update gate {gate_id} status: {e}")
            return False
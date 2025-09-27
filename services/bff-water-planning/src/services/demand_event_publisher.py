"""Demand event publisher for Redis coordination."""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from src.config.redis import redis_config

logger = logging.getLogger(__name__)


class DemandEventPublisher:
    """Publishes water demand calculation events to Redis."""
    
    def __init__(self):
        self.enabled = True  # Can be toggled via config
        self.channel_prefix = "water:demands:"
        
    async def publish_zone_demand_ready(
        self, 
        zone_id: str, 
        week_start: str, 
        demand_summary: Dict
    ) -> bool:
        """
        Publish event when zone demands are calculated and saved to DB.
        
        Args:
            zone_id: Zone identifier (e.g., '01-02')
            week_start: Week start date in ISO format
            demand_summary: Summary data including total_demand_m3, section_count
            
        Returns:
            bool: True if published successfully
        """
        if not self.enabled or not redis_config.is_connected:
            return False
            
        try:
            event_data = {
                'event_type': 'zone_demand_ready',
                'zone_id': zone_id,
                'week_start': week_start,
                'total_demand_m3': demand_summary.get('total_demand_m3', 0),
                'section_count': demand_summary.get('section_count', 0),
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'water_planning_bff'
            }
            
            channel = f"{self.channel_prefix}updated"
            message = json.dumps(event_data)
            
            if redis_config.publisher:
                await redis_config.publisher.publish(channel, message)
                logger.info(f"Published zone demand event for {zone_id}, week {week_start}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to publish zone demand event: {e}")
            
        return False
    
    async def publish_section_demand_ready(
        self, 
        section_id: str, 
        week_start: str, 
        demand_m3: float
    ) -> bool:
        """
        Publish event for section-level demand updates.
        
        Args:
            section_id: Section identifier (e.g., '01-02-03-04')
            week_start: Week start date in ISO format
            demand_m3: Calculated demand in cubic meters
            
        Returns:
            bool: True if published successfully
        """
        if not self.enabled or not redis_config.is_connected:
            return False
            
        try:
            # Extract zone_id from section_id
            zone_id = section_id[:5] if len(section_id) >= 5 else section_id
            
            event_data = {
                'event_type': 'section_demand_ready',
                'section_id': section_id,
                'zone_id': zone_id,
                'week_start': week_start,
                'demand_m3': demand_m3,
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'water_planning_bff'
            }
            
            channel = f"{self.channel_prefix}updated"
            message = json.dumps(event_data)
            
            if redis_config.publisher:
                await redis_config.publisher.publish(channel, message)
                logger.debug(f"Published section demand event for {section_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to publish section demand event: {e}")
            
        return False
    
    async def publish_batch_demands_ready(
        self, 
        week_start: str, 
        zone_list: List[Dict]
    ) -> bool:
        """
        Publish event when weekly batch calculation completes.
        
        Args:
            week_start: Week start date in ISO format
            zone_list: List of zones with their demand summaries
            
        Returns:
            bool: True if published successfully
        """
        if not self.enabled or not redis_config.is_connected:
            return False
            
        try:
            event_data = {
                'event_type': 'batch_demands_ready',
                'week_start': week_start,
                'zone_count': len(zone_list),
                'zones': [
                    {
                        'zone_id': zone['zone_id'],
                        'total_demand_m3': zone.get('total_demand_m3', 0),
                        'section_count': zone.get('section_count', 0)
                    }
                    for zone in zone_list
                ],
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'water_planning_bff'
            }
            
            channel = f"{self.channel_prefix}batch"
            message = json.dumps(event_data)
            
            if redis_config.publisher:
                await redis_config.publisher.publish(channel, message)
                logger.info(f"Published batch demands event for {len(zone_list)} zones, week {week_start}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to publish batch demands event: {e}")
            
        return False
    
    def set_enabled(self, enabled: bool):
        """Enable or disable event publishing."""
        self.enabled = enabled
        logger.info(f"Demand event publishing {'enabled' if enabled else 'disabled'}")


# Singleton instance
demand_event_publisher = DemandEventPublisher()
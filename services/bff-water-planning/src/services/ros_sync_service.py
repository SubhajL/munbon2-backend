from typing import Dict, List, Optional
import asyncio
import httpx
from datetime import datetime, timedelta
from core import get_logger
from services.integration_client import IntegrationClient
from config import settings

logger = get_logger(__name__)


class RosSyncService:
    """Service to sync ROS calculations to GIS database"""
    
    def __init__(self):
        self.client = IntegrationClient()
        self.logger = logger.bind(service="ros_sync")
        self.sync_interval = 3600  # 1 hour
        self.is_running = False
    
    async def sync_ros_calculations(self, section_ids: List[str]) -> Dict:
        """Sync ROS calculations for given sections to GIS database"""
        
        self.logger.info(
            "Starting ROS sync",
            section_count=len(section_ids)
        )
        
        current_week = datetime.now().isocalendar()[1]
        current_year = datetime.now().year
        
        try:
            # Get ROS calculations
            ros_data = await self.client.get_crop_requirements(section_ids)
            
            # Transform to GIS format
            calculations = []
            for section_id, data in ros_data.items():
                if data.get('crop_type') != 'none':  # Skip fallow sections
                    
                    # Calculate water demands
                    area_rai = data.get('area_rai', 0)
                    et0_mm = data.get('et_mm_day', 5.5) * 7  # Weekly ET0
                    kc_factor = data.get('kc_factor', 1.0)
                    percolation_mm = 14  # Standard percolation
                    
                    # Gross demand calculation
                    gross_demand_mm = (et0_mm * kc_factor) + percolation_mm
                    gross_demand_m3 = gross_demand_mm * area_rai * 1.6
                    
                    # For now, assume no effective rainfall (should come from weather service)
                    effective_rainfall_mm = 0
                    net_demand_mm = gross_demand_mm - effective_rainfall_mm
                    net_demand_m3 = net_demand_mm * area_rai * 1.6
                    
                    calculation = {
                        "sectionId": section_id,
                        "calculationDate": datetime.utcnow().isoformat(),
                        "calendarWeek": current_week,
                        "calendarYear": current_year,
                        
                        # Crop information
                        "cropType": data.get('crop_type'),
                        "cropWeek": data.get('crop_week'),
                        "growthStage": data.get('growth_stage'),
                        "plantingDate": data.get('planting_date'),
                        "harvestDate": data.get('harvest_date'),
                        
                        # Water demand calculation
                        "areaRai": area_rai,
                        "et0Mm": et0_mm,
                        "kcFactor": kc_factor,
                        "percolationMm": percolation_mm,
                        
                        # Results
                        "grossDemandMm": gross_demand_mm,
                        "grossDemandM3": gross_demand_m3,
                        "effectiveRainfallMm": effective_rainfall_mm,
                        "netDemandMm": net_demand_mm,
                        "netDemandM3": net_demand_m3,
                        
                        # Additional metrics
                        "moistureDeficitPercent": 20,  # Should come from sensors
                        "stressLevel": data.get('stress_level', 'none')
                    }
                    
                    calculations.append(calculation)
            
            # Push to GIS
            if calculations:
                success = await self.client.push_ros_calculations_to_gis(calculations)
                
                self.logger.info(
                    "ROS sync completed",
                    success=success,
                    calculations_count=len(calculations)
                )
                
                return {
                    "success": success,
                    "synced_count": len(calculations),
                    "timestamp": datetime.utcnow()
                }
            else:
                self.logger.warning("No active crops to sync")
                return {
                    "success": True,
                    "synced_count": 0,
                    "timestamp": datetime.utcnow()
                }
                
        except Exception as e:
            self.logger.error("ROS sync failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow()
            }
    
    async def sync_all_sections(self) -> Dict:
        """Sync all sections in the system"""
        
        # Get all sections from spatial mapping
        from services.spatial_mapping import SpatialMappingService
        spatial_service = SpatialMappingService()
        
        all_sections = []
        for zone in range(1, 7):  # Zones 1-6
            sections = await spatial_service.get_sections_by_zone(zone)
            all_sections.extend([s['section_id'] for s in sections])
        
        return await self.sync_ros_calculations(all_sections)
    
    async def start_periodic_sync(self):
        """Start periodic sync process"""
        
        if self.is_running:
            self.logger.warning("Sync service already running")
            return
        
        self.is_running = True
        self.logger.info(
            "Starting periodic ROS sync",
            interval_seconds=self.sync_interval
        )
        
        while self.is_running:
            try:
                # Run sync
                result = await self.sync_all_sections()
                
                if not result.get('success'):
                    self.logger.error(
                        "Periodic sync failed",
                        error=result.get('error')
                    )
                
                # Wait for next interval
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                self.logger.error("Error in periodic sync", error=str(e))
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    def stop_periodic_sync(self):
        """Stop periodic sync process"""
        self.is_running = False
        self.logger.info("Stopping periodic ROS sync")
    
    async def get_sync_status(self) -> Dict:
        """Get current sync status"""
        
        # Get latest sync info from GIS
        try:
            async with httpx.AsyncClient(timeout=self.client.timeout) as client:
                response = await client.get(
                    f"{self.client.base_urls['gis']}/api/v1/ros-demands/summary",
                    params={
                        "year": datetime.now().year,
                        "week": datetime.now().isocalendar()[1]
                    },
                    headers={"Authorization": "Bearer mock-token"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    summary = data.get('data', [])
                    
                    total_parcels = sum(s['parcel_count'] for s in summary)
                    total_demand = sum(s['total_net_demand_m3'] for s in summary)
                    
                    return {
                        "is_running": self.is_running,
                        "sync_interval_seconds": self.sync_interval,
                        "last_sync": datetime.utcnow(),  # Should store this properly
                        "current_week": datetime.now().isocalendar()[1],
                        "current_year": datetime.now().year,
                        "synced_parcels": total_parcels,
                        "total_demand_m3": total_demand
                    }
                    
        except Exception as e:
            self.logger.error("Failed to get sync status", error=str(e))
        
        return {
            "is_running": self.is_running,
            "sync_interval_seconds": self.sync_interval,
            "error": "Failed to get sync details"
        }
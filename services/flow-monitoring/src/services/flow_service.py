from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
import structlog

from db import DatabaseManager
from schemas import (
    FlowReading,
    FlowReadingCreate,
    FlowHistory,
    FlowAggregate,
    RealtimeFlowResponse,
    WaterLevel,
    MonitoringLocation
)
from core.metrics import current_flow_rate, water_level as water_level_metric

logger = structlog.get_logger()


class FlowService:
    """Service for flow data operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def get_realtime_flow(self, location_ids: List[UUID]) -> List[RealtimeFlowResponse]:
        """Get real-time flow data for multiple locations"""
        try:
            # Get latest readings from cache/InfluxDB
            latest_readings = await self.db.influxdb.get_latest_readings(
                [str(loc_id) for loc_id in location_ids]
            )
            
            responses = []
            for location_id in location_ids:
                location_id_str = str(location_id)
                
                # Get location details
                location = await self.db.postgres.get_monitoring_location(location_id)
                if not location:
                    continue
                
                # Get latest data
                if location_id_str in latest_readings:
                    flow_data = latest_readings[location_id_str]
                    
                    # Create flow reading
                    flow_reading = FlowReading(
                        sensor_id=location_id,  # Simplified for now
                        location_id=location_id,
                        channel_id=location.get("channel_id", "main"),
                        timestamp=flow_data["timestamp"],
                        flow_rate=flow_data["flow_rate"],
                        velocity=flow_data.get("velocity", 0),
                        water_level=flow_data.get("water_level", 0),
                        pressure=flow_data.get("pressure", 0),
                        quality_flag=1,
                        sensor_type="unknown"  # Would get from sensor config
                    )
                    
                    # Create water level
                    water_level = WaterLevel(
                        location_id=location_id,
                        channel_id=location.get("channel_id", "main"),
                        timestamp=flow_data["timestamp"],
                        water_level=flow_data.get("water_level", 0),
                        reference_level=location.get("elevation", 0),
                        alert_level=location.get("alert_thresholds", {}).get("water_level_alert"),
                        critical_level=location.get("alert_thresholds", {}).get("water_level_critical")
                    )
                    
                    # Check for anomalies
                    anomalies = await self.db.redis.get_active_anomalies(location_id_str)
                    anomaly_types = [a["type"] for a in anomalies]
                    
                    # Update metrics
                    current_flow_rate.labels(
                        location_id=location_id_str,
                        channel_id=location.get("channel_id", "main")
                    ).set(flow_data["flow_rate"])
                    
                    water_level_metric.labels(
                        location_id=location_id_str
                    ).set(flow_data.get("water_level", 0))
                    
                    # Create response
                    response = RealtimeFlowResponse(
                        location_id=location_id,
                        location_name=location["location_name"],
                        timestamp=flow_data["timestamp"],
                        flow_data=flow_reading,
                        water_level=water_level,
                        status="operational" if not anomalies else "warning",
                        anomalies=anomaly_types,
                        quality_score=1.0  # Would calculate based on data quality
                    )
                    
                    responses.append(response)
            
            return responses
            
        except Exception as e:
            logger.error("Failed to get real-time flow data", error=str(e))
            raise
    
    async def get_flow_history(
        self,
        location_id: UUID,
        start_time: datetime,
        end_time: datetime,
        interval: str,
        aggregation: str
    ) -> FlowHistory:
        """Get historical flow data with aggregation"""
        try:
            # Get aggregated data from TimescaleDB
            data = await self.db.timescale.get_flow_history(
                location_id=str(location_id),
                start_time=start_time,
                end_time=end_time,
                interval=interval
            )
            
            # Convert to FlowAggregate objects
            aggregates = []
            for record in data:
                aggregate = FlowAggregate(
                    time=record["bucket"],
                    location_id=location_id,
                    channel_id=record["channel_id"],
                    avg_flow_rate=float(record["avg_flow_rate"] or 0),
                    max_flow_rate=float(record["max_flow_rate"] or 0),
                    min_flow_rate=float(record["min_flow_rate"] or 0),
                    total_volume=float(record["total_volume"] or 0),
                    avg_water_level=float(record["avg_water_level"] or 0),
                    quality_score=1.0
                )
                aggregates.append(aggregate)
            
            # Calculate statistics
            if aggregates:
                flow_rates = [a.avg_flow_rate for a in aggregates]
                volumes = [a.total_volume for a in aggregates]
                
                statistics = {
                    "avg_flow_rate": sum(flow_rates) / len(flow_rates),
                    "max_flow_rate": max([a.max_flow_rate for a in aggregates]),
                    "min_flow_rate": min([a.min_flow_rate for a in aggregates]),
                    "total_volume": sum(volumes),
                    "data_points": len(aggregates)
                }
            else:
                statistics = {
                    "avg_flow_rate": 0,
                    "max_flow_rate": 0,
                    "min_flow_rate": 0,
                    "total_volume": 0,
                    "data_points": 0
                }
            
            return FlowHistory(
                location_id=location_id,
                channel_id=aggregates[0].channel_id if aggregates else "main",
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                data=aggregates,
                statistics=statistics
            )
            
        except Exception as e:
            logger.error("Failed to get flow history", error=str(e))
            raise
    
    async def ingest_flow_data(self, readings: List[FlowReadingCreate]) -> int:
        """Ingest flow sensor readings"""
        try:
            # Convert to format for InfluxDB
            data_points = []
            for reading in readings:
                data_point = {
                    "sensor_id": str(reading.sensor_id),
                    "sensor_type": reading.sensor_type,
                    "location_id": str(reading.location_id),
                    "channel_id": reading.channel_id,
                    "timestamp": reading.timestamp,
                    "flow_rate": reading.flow_rate,
                    "velocity": reading.velocity,
                    "water_level": reading.water_level,
                    "pressure": reading.pressure,
                    "quality_flag": reading.quality_flag
                }
                data_points.append(data_point)
            
            # Write to InfluxDB
            await self.db.influxdb.write_flow_data(data_points)
            
            # Update cache for latest readings
            for reading in readings:
                await self.db.redis.set_latest_flow_data(
                    location_id=str(reading.location_id),
                    data={
                        "timestamp": reading.timestamp.isoformat(),
                        "flow_rate": reading.flow_rate,
                        "water_level": reading.water_level,
                        "velocity": reading.velocity,
                        "pressure": reading.pressure
                    }
                )
            
            return len(readings)
            
        except Exception as e:
            logger.error("Failed to ingest flow data", error=str(e))
            raise
    
    async def get_latest_reading(
        self,
        location_id: UUID,
        channel_id: str
    ) -> Optional[FlowReading]:
        """Get the latest flow reading for a location"""
        try:
            # Try cache first
            cached_data = await self.db.redis.get_latest_flow_data(str(location_id))
            
            if cached_data:
                # Get sensor info
                sensors = await self.db.postgres.get_location_sensors(location_id)
                sensor = next(
                    (s for s in sensors if s["channel_id"] == channel_id),
                    sensors[0] if sensors else None
                )
                
                if sensor:
                    return FlowReading(
                        sensor_id=sensor["sensor_id"],
                        location_id=location_id,
                        channel_id=channel_id,
                        timestamp=datetime.fromisoformat(cached_data["timestamp"]),
                        flow_rate=cached_data["flow_rate"],
                        velocity=cached_data.get("velocity", 0),
                        water_level=cached_data.get("water_level", 0),
                        pressure=cached_data.get("pressure", 0),
                        quality_flag=1,
                        sensor_type=sensor["sensor_type"]
                    )
            
            # If not in cache, query InfluxDB
            latest = await self.db.influxdb.get_latest_readings([str(location_id)])
            if str(location_id) in latest:
                data = latest[str(location_id)]
                return FlowReading(
                    sensor_id=location_id,  # Simplified
                    location_id=location_id,
                    channel_id=channel_id,
                    timestamp=data["timestamp"],
                    flow_rate=data["flow_rate"],
                    velocity=data.get("velocity", 0),
                    water_level=data.get("water_level", 0),
                    pressure=data.get("pressure", 0),
                    quality_flag=1,
                    sensor_type="unknown"
                )
            
            return None
            
        except Exception as e:
            logger.error("Failed to get latest reading", error=str(e))
            raise
    
    async def get_flow_statistics(
        self,
        location_id: UUID,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """Calculate flow statistics for a location"""
        try:
            # Get data from InfluxDB
            data = await self.db.influxdb.query_flow_data(
                location_id=str(location_id),
                start_time=start_time,
                end_time=end_time,
                aggregation="mean",
                interval="5m"
            )
            
            if not data:
                return {
                    "location_id": location_id,
                    "period": {
                        "start": start_time.isoformat(),
                        "end": end_time.isoformat()
                    },
                    "statistics": {
                        "mean_flow_rate": 0,
                        "max_flow_rate": 0,
                        "min_flow_rate": 0,
                        "std_deviation": 0,
                        "total_volume": 0,
                        "data_points": 0
                    }
                }
            
            # Extract flow rates
            flow_rates = [d["value"] for d in data if d["field"] == "flow_rate"]
            
            if flow_rates:
                import numpy as np
                
                stats = {
                    "mean_flow_rate": float(np.mean(flow_rates)),
                    "max_flow_rate": float(np.max(flow_rates)),
                    "min_flow_rate": float(np.min(flow_rates)),
                    "std_deviation": float(np.std(flow_rates)),
                    "total_volume": float(np.sum(flow_rates) * 300),  # 5-minute intervals
                    "data_points": len(flow_rates)
                }
            else:
                stats = {
                    "mean_flow_rate": 0,
                    "max_flow_rate": 0,
                    "min_flow_rate": 0,
                    "std_deviation": 0,
                    "total_volume": 0,
                    "data_points": 0
                }
            
            return {
                "location_id": location_id,
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "statistics": stats
            }
            
        except Exception as e:
            logger.error("Failed to calculate flow statistics", error=str(e))
            raise
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import structlog
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client.client.write_api_async import WriteApiAsync
from influxdb_client.client.query_api_async import QueryApiAsync

from config import settings
from core.metrics import db_operations_total, db_operation_duration_seconds

logger = structlog.get_logger()


class InfluxDBClient:
    """Async InfluxDB client for time-series data"""
    
    def __init__(self):
        self.url = settings.influxdb_url
        self.token = settings.influxdb_token
        self.org = settings.influxdb_org
        self.bucket = settings.influxdb_bucket
        self.client: Optional[InfluxDBClientAsync] = None
        self.write_api: Optional[WriteApiAsync] = None
        self.query_api: Optional[QueryApiAsync] = None
    
    async def connect(self) -> None:
        """Connect to InfluxDB"""
        try:
            self.client = InfluxDBClientAsync(
                url=self.url,
                token=self.token,
                org=self.org
            )
            self.write_api = self.client.write_api()
            self.query_api = self.client.query_api()
            
            # Test connection
            await self.ping()
            
        except Exception as e:
            logger.error("Failed to connect to InfluxDB", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from InfluxDB"""
        if self.client:
            await self.client.close()
    
    async def ping(self) -> bool:
        """Check if InfluxDB is reachable"""
        try:
            ready = await self.client.ping()
            return ready
        except Exception as e:
            logger.error("InfluxDB ping failed", error=str(e))
            return False
    
    async def write_flow_data(self, data: List[Dict[str, Any]]) -> None:
        """Write flow sensor data to InfluxDB"""
        with db_operation_duration_seconds.labels(operation="write", database="influxdb").time():
            try:
                points = []
                for record in data:
                    point = {
                        "measurement": "flow_data",
                        "tags": {
                            "sensor_id": record["sensor_id"],
                            "sensor_type": record["sensor_type"],
                            "location_id": record["location_id"],
                            "channel_id": record.get("channel_id", "main")
                        },
                        "fields": {
                            "flow_rate": float(record["flow_rate"]),
                            "velocity": float(record.get("velocity", 0)),
                            "water_level": float(record.get("water_level", 0)),
                            "pressure": float(record.get("pressure", 0)),
                            "quality_flag": int(record.get("quality_flag", 1))
                        },
                        "time": record.get("timestamp", datetime.utcnow())
                    }
                    points.append(point)
                
                await self.write_api.write(bucket=self.bucket, record=points)
                db_operations_total.labels(operation="write", database="influxdb", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to write flow data", error=str(e))
                db_operations_total.labels(operation="write", database="influxdb", status="error").inc()
                raise
    
    async def query_flow_data(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: str = "mean",
        interval: str = "1m"
    ) -> List[Dict[str, Any]]:
        """Query flow data with aggregation"""
        with db_operation_duration_seconds.labels(operation="query", database="influxdb").time():
            try:
                query = f'''
                from(bucket: "{self.bucket}")
                |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
                |> filter(fn: (r) => r["_measurement"] == "flow_data")
                |> filter(fn: (r) => r["location_id"] == "{location_id}")
                |> filter(fn: (r) => r["_field"] == "flow_rate" or r["_field"] == "water_level")
                |> aggregateWindow(every: {interval}, fn: {aggregation})
                |> yield(name: "result")
                '''
                
                result = await self.query_api.query(query=query)
                
                data = []
                for table in result:
                    for record in table.records:
                        data.append({
                            "time": record.get_time(),
                            "field": record.get_field(),
                            "value": record.get_value(),
                            "location_id": record.values.get("location_id")
                        })
                
                db_operations_total.labels(operation="query", database="influxdb", status="success").inc()
                return data
                
            except Exception as e:
                logger.error("Failed to query flow data", error=str(e))
                db_operations_total.labels(operation="query", database="influxdb", status="error").inc()
                raise
    
    async def get_latest_readings(self, location_ids: List[str]) -> Dict[str, Any]:
        """Get latest readings for multiple locations"""
        with db_operation_duration_seconds.labels(operation="query", database="influxdb").time():
            try:
                location_filter = " or ".join([f'r["location_id"] == "{loc}"' for loc in location_ids])
                
                query = f'''
                from(bucket: "{self.bucket}")
                |> range(start: -5m)
                |> filter(fn: (r) => r["_measurement"] == "flow_data")
                |> filter(fn: (r) => {location_filter})
                |> last()
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                '''
                
                result = await self.query_api.query(query=query)
                
                latest_data = {}
                for table in result:
                    for record in table.records:
                        location_id = record.values.get("location_id")
                        latest_data[location_id] = {
                            "timestamp": record.get_time(),
                            "flow_rate": record.values.get("flow_rate", 0),
                            "water_level": record.values.get("water_level", 0),
                            "velocity": record.values.get("velocity", 0),
                            "pressure": record.values.get("pressure", 0)
                        }
                
                db_operations_total.labels(operation="query", database="influxdb", status="success").inc()
                return latest_data
                
            except Exception as e:
                logger.error("Failed to get latest readings", error=str(e))
                db_operations_total.labels(operation="query", database="influxdb", status="error").inc()
                raise
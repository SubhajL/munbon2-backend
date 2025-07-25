import os
from datetime import datetime
from typing import List, Dict, Optional
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

load_dotenv()

client = None
write_api = None
query_api = None

def get_influx_client():
    """Get or create InfluxDB client"""
    global client, write_api, query_api
    
    if client is None:
        client = InfluxDBClient(
            url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            token=os.getenv("INFLUXDB_TOKEN"),
            org=os.getenv("INFLUXDB_ORG", "munbon")
        )
        write_api = client.write_api(write_options=SYNCHRONOUS)
        query_api = client.query_api()
    
    return client

async def write_sensor_reading(sensor_id: str, sensor_type: str, value: float, 
                              unit: str, quality: float, battery: float,
                              lat: float, lon: float, section_id: Optional[str] = None):
    """Write sensor reading to InfluxDB"""
    get_influx_client()
    
    point = Point("sensor_reading") \
        .tag("sensor_id", sensor_id) \
        .tag("sensor_type", sensor_type) \
        .tag("section_id", section_id or "unknown") \
        .field("value", value) \
        .field("unit", unit) \
        .field("quality", quality) \
        .field("battery_level", battery) \
        .field("latitude", lat) \
        .field("longitude", lon) \
        .time(datetime.utcnow())
    
    write_api.write(
        bucket=os.getenv("INFLUXDB_BUCKET", "sensor_data"),
        org=os.getenv("INFLUXDB_ORG", "munbon"),
        record=point
    )

async def query_sensor_data(sensor_id: str, start_time: str, end_time: str, 
                           aggregation: str = "mean") -> List[Dict]:
    """Query sensor data from InfluxDB"""
    get_influx_client()
    
    query = f'''
    from(bucket: "{os.getenv("INFLUXDB_BUCKET", "sensor_data")}")
        |> range(start: {start_time}, stop: {end_time})
        |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
        |> filter(fn: (r) => r["_measurement"] == "sensor_reading")
        |> filter(fn: (r) => r["_field"] == "value")
        |> aggregateWindow(every: 1h, fn: {aggregation}, createEmpty: false)
        |> yield(name: "{aggregation}")
    '''
    
    result = query_api.query(org=os.getenv("INFLUXDB_ORG", "munbon"), query=query)
    
    data = []
    for table in result:
        for record in table.records:
            data.append({
                "time": record.get_time(),
                "value": record.get_value(),
                "sensor_id": record.values.get("sensor_id"),
                "section_id": record.values.get("section_id")
            })
    
    return data
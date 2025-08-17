# Service Ports Reference

## Correct Port Assignments

| Service | Port | Description |
|---------|------|-------------|
| Sensor Data Service | 3003 | MQTT, time-series data ingestion |
| GIS Service | 3007 | PostGIS spatial operations, RID Plan API |
| Flow Monitoring (Instance 16) | 3011 | Core monitoring and network model |
| Scheduler (Instance 17) | 3021 | Field operations scheduling |
| ROS-GIS Integration (Instance 18) | 3022 | This service - GraphQL API |
| ROS Service | 3047 | Water demand calculation, crop calendars |

## Port Corrections Made
- GIS Service: Correctly set to **3007** (not 3003)
- ROS Service: Correctly set to **3047** (not 3041)

## Configuration
In `src/config/settings.py`:
```python
ros_service_url: str = Field(
    default="http://localhost:3047",  # ROS service
    env="ROS_SERVICE_URL"
)
gis_service_url: str = Field(
    default="http://localhost:3007",  # GIS service
    env="GIS_SERVICE_URL"
)
```
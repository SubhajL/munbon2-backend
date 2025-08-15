# Water Accounting Service Integration Guide

## Overview

This guide explains how to integrate the Water Accounting Service with other services in the Munbon system.

## Integration Points

### 1. Sensor Data Service (Port 3003)
The Water Accounting Service needs flow measurement data from sensors.

**Required Integration:**
- Pull flow readings for delivery volume calculations
- Subscribe to real-time flow updates during deliveries

**Example Request:**
```python
# Get flow readings for a specific gate
response = await httpx.get(
    f"{SENSOR_DATA_URL}/api/v1/flow/{gate_id}",
    params={
        "start_time": delivery_start,
        "end_time": delivery_end
    }
)
```

### 2. GIS Service (Port 3007)
Provides section boundaries and canal characteristics.

**Required Integration:**
- Get section details (area, canal length, type)
- Update deficit status for spatial analysis

**Example Request:**
```python
# Get section characteristics
response = await httpx.get(
    f"{GIS_SERVICE_URL}/api/v1/sections/{section_id}"
)
section_data = response.json()
canal_length = section_data["canal_length_km"]
```

### 3. Weather Service (Port 3008)
Provides environmental data for evaporation calculations.

**Required Integration:**
- Get temperature, humidity, wind speed
- Get solar radiation for Penman equation

**Example Request:**
```python
# Get weather conditions
response = await httpx.get(
    f"{WEATHER_SERVICE_URL}/api/v1/conditions",
    params={
        "location": section_location,
        "time": measurement_time
    }
)
```

### 4. SCADA Service (Port 3023)
Provides gate operation data.

**Required Integration:**
- Get gate status (open/closed)
- Get operational losses from gate leakage

**Example Request:**
```python
# Get gate operational data
response = await httpx.get(
    f"{SCADA_SERVICE_URL}/api/v1/gates/{gate_id}/status"
)
```

## Data Flow

### Delivery Completion Workflow

1. **Scheduler Service** triggers delivery completion
2. **Water Accounting** fetches flow data from **Sensor Data Service**
3. **Water Accounting** gets environmental conditions from **Weather Service**
4. **Water Accounting** calculates:
   - Volume using integration
   - Losses (seepage, evaporation)
   - Efficiency metrics
   - Deficit tracking
5. **Water Accounting** stores results and notifies other services

### Weekly Reconciliation Workflow

1. **Automated Gates** (20 gates):
   - Direct flow measurements
   - High confidence calculations
   
2. **Manual Gates** (remaining gates):
   - Estimate based on:
     - Gate opening duration
     - Head difference
     - Historical patterns
   - Lower confidence level

3. **Reconciliation Process**:
   - Compare total outflow vs total inflow
   - Identify discrepancies
   - Adjust manual gate estimates
   - Generate weekly report

## Implementation Examples

### 1. Complete Delivery Integration

```python
async def complete_delivery_with_integrations(delivery_id: str):
    # 1. Get delivery schedule
    delivery = await get_delivery_details(delivery_id)
    
    # 2. Fetch flow data from Sensor Service
    flow_data = await fetch_flow_readings(
        delivery.gate_id,
        delivery.start_time,
        delivery.end_time
    )
    
    # 3. Get weather conditions
    weather = await get_weather_conditions(
        delivery.section_location,
        delivery.start_time,
        delivery.end_time
    )
    
    # 4. Get canal characteristics from GIS
    canal_info = await get_canal_characteristics(delivery.section_id)
    
    # 5. Process delivery completion
    result = await water_accounting_service.complete_delivery({
        "delivery_id": delivery_id,
        "section_id": delivery.section_id,
        "flow_readings": flow_data,
        "environmental_conditions": weather,
        "canal_characteristics": canal_info
    })
    
    # 6. Update other services
    await notify_completion(result)
    
    return result
```

### 2. Deficit Recovery Integration

```python
async def plan_deficit_recovery(section_id: str):
    # 1. Get current deficit status
    deficit_status = await water_accounting_service.get_carry_forward_status(section_id)
    
    # 2. Check available capacity
    available_capacity = await scheduler_service.get_available_capacity(
        section_id,
        weeks_ahead=4
    )
    
    # 3. Generate recovery plan
    recovery_plan = await water_accounting_service.generate_recovery_plan(
        section_id,
        available_capacity
    )
    
    # 4. Schedule additional deliveries
    for compensation in recovery_plan["compensation_schedule"]:
        await scheduler_service.schedule_delivery({
            "section_id": section_id,
            "volume_m3": compensation["compensation_m3"],
            "week_offset": compensation["week_offset"],
            "priority": "deficit_recovery"
        })
    
    return recovery_plan
```

## Error Handling

### Service Unavailable
```python
try:
    weather_data = await get_weather_conditions()
except httpx.ConnectError:
    # Use default environmental conditions
    weather_data = {
        "temperature_c": 30,
        "humidity_percent": 60,
        "wind_speed_ms": 2
    }
    logger.warning("Weather service unavailable, using defaults")
```

### Data Quality Issues
```python
# Validate flow readings
validation_result = await water_accounting_service.validate_flow_data(flow_readings)
if not validation_result["is_valid"]:
    # Handle gaps or outliers
    flow_readings = interpolate_missing_data(flow_readings)
```

## Monitoring Integration

### Metrics to Share
- Delivery completion rate
- Average efficiency by zone
- Active deficits count
- System-wide stress level

### Alerts to Generate
- Efficiency below threshold
- Severe water stress detected
- Large discrepancy in reconciliation
- Service integration failures

## Testing Integration

Use the provided `test_api.py` script to verify integration endpoints:

```bash
# Test individual integration
python test_api.py

# Run full integration test
python test_integration.py
```

## Security Considerations

1. **Service-to-Service Authentication**:
   - Use JWT tokens for service authentication
   - Implement mutual TLS for production

2. **Rate Limiting**:
   - Limit API calls to prevent overload
   - Implement circuit breakers

3. **Data Validation**:
   - Validate all incoming data
   - Sanitize before storage

## Performance Optimization

1. **Batch Operations**:
   - Process multiple deliveries together
   - Aggregate queries where possible

2. **Caching**:
   - Cache section characteristics
   - Cache weather data (15-minute TTL)

3. **Async Processing**:
   - Use background tasks for notifications
   - Process reconciliation asynchronously
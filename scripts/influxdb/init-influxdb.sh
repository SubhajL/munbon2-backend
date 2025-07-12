#!/bin/bash

# InfluxDB initialization script for Munbon Irrigation System
# This script sets up buckets, retention policies, and initial dashboards

INFLUX_HOST=${INFLUX_HOST:-localhost}
INFLUX_PORT=${INFLUX_PORT:-8086}
INFLUX_TOKEN=${INFLUX_TOKEN:-"local-dev-token"}
INFLUX_ORG=${INFLUX_ORG:-"munbon"}

# Function to run influx commands
influx_exec() {
    influx "$@" --host http://${INFLUX_HOST}:${INFLUX_PORT} --token ${INFLUX_TOKEN}
}

echo "Initializing InfluxDB for Munbon Irrigation System..."

# Test connection
influx_exec ping
if [ $? -ne 0 ]; then
    echo "Failed to connect to InfluxDB"
    exit 1
fi

# Create buckets with retention policies
echo "Creating buckets..."

# System metrics (30 days retention)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name system-metrics \
    --retention 720h \
    --description "System performance and health metrics"

# Sensor data (90 days retention for raw, 1 year for downsampled)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name sensor-data \
    --retention 2160h \
    --description "Raw sensor readings"

influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name sensor-data-hourly \
    --retention 8760h \
    --description "Hourly aggregated sensor data"

# Water usage metrics (5 years retention)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name water-usage \
    --retention 43800h \
    --description "Water consumption and distribution metrics"

# Control system metrics (90 days retention)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name control-metrics \
    --retention 2160h \
    --description "Gate, pump, and valve operation metrics"

# API metrics (7 days retention)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name api-metrics \
    --retention 168h \
    --description "API performance and usage metrics"

# Alert metrics (30 days retention)
influx_exec bucket create \
    --org ${INFLUX_ORG} \
    --name alert-metrics \
    --retention 720h \
    --description "System alerts and notifications"

# Create continuous queries for downsampling
echo "Setting up continuous queries..."

# Create Flux tasks for downsampling
cat > /tmp/downsample-sensors.flux << 'EOF'
import "influxdata/influxdb/tasks"

option task = {
    name: "Downsample Sensor Data",
    every: 1h,
}

from(bucket: "sensor-data")
    |> range(start: -1h)
    |> filter(fn: (r) => r._measurement == "sensor_reading")
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    |> to(bucket: "sensor-data-hourly", org: "munbon")
EOF

cat > /tmp/calculate-water-usage.flux << 'EOF'
import "influxdata/influxdb/tasks"

option task = {
    name: "Calculate Water Usage",
    every: 5m,
}

from(bucket: "sensor-data")
    |> range(start: -5m)
    |> filter(fn: (r) => r._measurement == "flow_rate")
    |> integral(unit: 1m)
    |> map(fn: (r) => ({r with _measurement: "water_volume", _field: "volume_m3"}))
    |> to(bucket: "water-usage", org: "munbon")
EOF

# Create tasks
influx_exec task create --org ${INFLUX_ORG} --file /tmp/downsample-sensors.flux
influx_exec task create --org ${INFLUX_ORG} --file /tmp/calculate-water-usage.flux

# Create alert checks
echo "Setting up alert checks..."

# High water level alert
cat > /tmp/high-water-level.flux << 'EOF'
import "influxdata/influxdb/monitor"
import "influxdata/influxdb/v1"

data = from(bucket: "sensor-data")
    |> range(start: -5m)
    |> filter(fn: (r) => r._measurement == "water_level" and r._field == "level_cm")

option task = {
    name: "High Water Level Alert",
    every: 1m,
    offset: 0s,
}

check = {
    _check_id: "high_water_level",
    _check_name: "High Water Level Alert",
    _type: "threshold",
    tags: {},
}

crit = (r) => r.level_cm > 25.0
warn = (r) => r.level_cm > 20.0

data
    |> v1.fieldsAsCols()
    |> monitor.check(data: check, messageFn: (r) => "Water level critical: ${r.level_cm}cm at sensor ${r.sensor_id}", crit: crit, warn: warn)
EOF

# Low moisture alert
cat > /tmp/low-moisture.flux << 'EOF'
import "influxdata/influxdb/monitor"
import "influxdata/influxdb/v1"

data = from(bucket: "sensor-data")
    |> range(start: -15m)
    |> filter(fn: (r) => r._measurement == "soil_moisture" and r._field == "moisture_percent")

option task = {
    name: "Low Soil Moisture Alert",
    every: 5m,
    offset: 0s,
}

check = {
    _check_id: "low_soil_moisture",
    _check_name: "Low Soil Moisture Alert",
    _type: "threshold",
    tags: {},
}

crit = (r) => r.moisture_percent < 20.0
warn = (r) => r.moisture_percent < 30.0

data
    |> v1.fieldsAsCols()
    |> monitor.check(data: check, messageFn: (r) => "Soil moisture low: ${r.moisture_percent}% at zone ${r.zone_id}", crit: crit, warn: warn)
EOF

# Create checks
influx_exec task create --org ${INFLUX_ORG} --file /tmp/high-water-level.flux
influx_exec task create --org ${INFLUX_ORG} --file /tmp/low-moisture.flux

# Initialize with sample dashboard templates
echo "Creating dashboard templates..."

cat > /tmp/system-overview-dashboard.json << 'EOF'
{
  "name": "System Overview",
  "description": "Munbon Irrigation System Overview Dashboard",
  "cells": [
    {
      "name": "Active Sensors",
      "x": 0,
      "y": 0,
      "w": 4,
      "h": 3,
      "queries": [
        {
          "text": "from(bucket: \"system-metrics\")\n  |> range(start: -1h)\n  |> filter(fn: (r) => r._measurement == \"sensors\" and r._field == \"active_count\")\n  |> last()"
        }
      ]
    },
    {
      "name": "Water Flow Rate",
      "x": 4,
      "y": 0,
      "w": 4,
      "h": 3,
      "queries": [
        {
          "text": "from(bucket: \"sensor-data\")\n  |> range(start: -1h)\n  |> filter(fn: (r) => r._measurement == \"flow_rate\")\n  |> aggregateWindow(every: 1m, fn: mean)"
        }
      ]
    },
    {
      "name": "API Response Time",
      "x": 8,
      "y": 0,
      "w": 4,
      "h": 3,
      "queries": [
        {
          "text": "from(bucket: \"api-metrics\")\n  |> range(start: -1h)\n  |> filter(fn: (r) => r._measurement == \"http_request_duration\" and r._field == \"p95\")"
        }
      ]
    }
  ]
}
EOF

# Write initial data points for testing
echo "Writing initial test data..."

# System metrics
influx_exec write \
    --org ${INFLUX_ORG} \
    --bucket system-metrics \
    --precision s \
    "cpu_usage,host=api-server usage=15.5
memory_usage,host=api-server usage_percent=45.2
disk_usage,host=api-server,path=/data usage_percent=23.1"

# Sensor data
influx_exec write \
    --org ${INFLUX_ORG} \
    --bucket sensor-data \
    --precision s \
    "water_level,sensor_id=WL001,zone_id=zone1 level_cm=12.5
soil_moisture,sensor_id=SM001,zone_id=zone1 moisture_percent=65.3
flow_rate,gate_id=G001 rate_lps=125.7"

echo "InfluxDB initialization completed!"

# Display summary
echo -e "\nBuckets created:"
influx_exec bucket list --org ${INFLUX_ORG} --limit 20

echo -e "\nTasks created:"
influx_exec task list --org ${INFLUX_ORG} --limit 20

# Cleanup
rm -f /tmp/*.flux /tmp/*.json
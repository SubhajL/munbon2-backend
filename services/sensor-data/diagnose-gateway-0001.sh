#!/bin/bash

echo "=================================================="
echo "Gateway 0001 Diagnostic Report"
echo "=================================================="
echo ""

echo "1. DATABASE CHECK - Last 7 days of moisture data by gateway"
echo "-----------------------------------------------------------"
PGPASSWORD='P@ssw0rd123!' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  LEFT(sensor_id, 4) as gateway,
  COUNT(*) as total_records,
  MIN(time) as first_reading,
  MAX(time) as last_reading,
  COUNT(DISTINCT sensor_id) as unique_sensors,
  ROUND(AVG(CASE WHEN moisture_surface_pct IS NOT NULL THEN moisture_surface_pct END)::numeric, 2) as avg_surface,
  ROUND(AVG(CASE WHEN moisture_deep_pct IS NOT NULL THEN moisture_deep_pct END)::numeric, 2) as avg_deep
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY LEFT(sensor_id, 4)
ORDER BY last_reading DESC;
"

echo ""
echo "2. GATEWAY 0001 - Detailed sensor breakdown"
echo "-----------------------------------------------------------"
PGPASSWORD='P@ssw0rd123!' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  COUNT(*) as records,
  MAX(time) as last_seen,
  ROUND(AVG(moisture_surface_pct)::numeric, 2) as avg_surface,
  ROUND(AVG(moisture_deep_pct)::numeric, 2) as avg_deep
FROM moisture_readings 
WHERE sensor_id LIKE '0001-%'
  AND time > NOW() - INTERVAL '7 days'
GROUP BY sensor_id
ORDER BY last_seen DESC;
"

echo ""
echo "3. GATEWAY 0002 - Detailed sensor breakdown"
echo "-----------------------------------------------------------"
PGPASSWORD='P@ssw0rd123!' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  COUNT(*) as records,
  MAX(time) as last_seen,
  ROUND(AVG(CASE WHEN moisture_surface_pct IS NOT NULL THEN moisture_surface_pct END)::numeric, 2) as avg_surface,
  ROUND(AVG(CASE WHEN moisture_deep_pct IS NOT NULL THEN moisture_deep_pct END)::numeric, 2) as avg_deep
FROM moisture_readings 
WHERE sensor_id LIKE '0002-%'
  AND time > NOW() - INTERVAL '7 days'
GROUP BY sensor_id
ORDER BY last_seen DESC;
"

echo ""
echo "4. CODE CHECK - Verify no filtering on gateway 0001"
echo "-----------------------------------------------------------"
echo "Searching for any hardcoded filters on gateway IDs..."
grep -rn "0001" services/sensor-data/src/*.js services/sensor-data/src/*.ts 2>/dev/null | grep -i "skip\|filter\|exclude\|!=" | head -5 || echo "✓ No hardcoded gateway filters found"

echo ""
echo "5. CODE CHECK - Sensor ID validation logic"
echo "-----------------------------------------------------------"
grep -A 5 "Skip.*sensor" services/sensor-data/src/simple-http-server-fixed.js

echo ""
echo "6. SENSOR REGISTRY CHECK - Gateway 0001 status"
echo "-----------------------------------------------------------"
PGPASSWORD='P@ssw0rd123!' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  sensor_type,
  manufacturer,
  last_seen,
  is_active,
  location_lat,
  location_lng
FROM sensor_registry 
WHERE sensor_id LIKE '0001%'
ORDER BY last_seen DESC
LIMIT 10;
"

echo ""
echo "7. TIMELINE ANALYSIS - When did gateway 0001 stop?"
echo "-----------------------------------------------------------"
PGPASSWORD='P@ssw0rd123!' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  DATE(time) as date,
  LEFT(sensor_id, 4) as gateway,
  COUNT(*) as records
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY DATE(time), LEFT(sensor_id, 4)
ORDER BY date DESC, gateway;
"

echo ""
echo "=================================================="
echo "SUMMARY"
echo "=================================================="
echo ""
echo "If gateway 0001 shows no recent data (last 3-4 days),"
echo "this indicates a HARDWARE/NETWORK issue, not code filtering."
echo ""
echo "Check:"
echo "  - Gateway 0001 power supply and battery"
echo "  - Network connectivity (WiFi/cellular signal)"
echo "  - Gateway configuration (endpoint URL, auth token)"
echo "  - Physical sensor connections"
echo ""
